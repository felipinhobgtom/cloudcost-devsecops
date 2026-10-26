#!/usr/bin/env python3
"""Executa gates reais; códigos de saída e relatórios nunca são substituídos por sucesso."""

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_file(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class Audit:
    def __init__(self, mode):
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.directory = ROOT / "reports" / (stamp + "-" + uuid.uuid4().hex[:8])
        self.directory.mkdir(parents=True)
        self.steps = []
        self.mode = mode
        self.pins = load_json(ROOT / "security/toolchain.json")
        self.env = os.environ.copy()
        self.env.update({
            "GOTOOLCHAIN": "go" + self.pins["go"],
            "GOWORK": "off",
            "GOPROXY": "https://proxy.golang.org",
            "GOSUMDB": "sum.golang.org",
            "GONOSUMDB": "",
            "GONOPROXY": "",
            "GOPRIVATE": "",
            "CGO_ENABLED": "0",
            "GOFLAGS": "-mod=readonly",
            "GOBIN": str(ROOT / ".tools/bin"),
            "CLOUDCOST_IMAGE": "cloudcost:local",
        })
        (ROOT / ".tools/bin").mkdir(parents=True, exist_ok=True)
        (ROOT / ".cache/trivy").mkdir(parents=True, exist_ok=True)
        json_file(self.directory / "toolchain.json", self.pins)
        self.image_id = None
        self.container = None
        self.source = None
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                output.write("report-dir=" + str(self.directory.relative_to(ROOT)) + "\n")
        print("Evidências: " + str(self.directory), flush=True)

    def record(self, name, status, **details):
        self.steps.append({"name": name, "status": status, **details})
        print(name + ": " + status, flush=True)

    def command(self, name, args, output=None, validate=None, after=None, private_logs=False):
        target = self.directory / (output or (name + ".stdout.log"))
        error_log = self.directory / (name + ".stderr.log")
        started = time.monotonic()
        code = None
        error = None
        try:
            with (tempfile.TemporaryFile() if private_logs else target.open("wb")) as stdout, \
                    (tempfile.TemporaryFile() if private_logs else error_log.open("wb")) as stderr:
                result = subprocess.run(args, cwd=ROOT, env=self.env, stdout=stdout,
                                        stderr=stderr, check=False)
            code = result.returncode
            # Sanitização deve ocorrer também quando o scanner encontrou segredos e retornou != 0.
            if after is not None:
                after()
            require(code == 0, "processo retornou " + str(code))
            if validate is not None:
                validate(target)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            error = str(exc)
        finally:
            if private_logs:
                notice = "Saída textual bruta do Gitleaks não publicada para proteger metadados; consulte o JSON sanitizado e o exit_code em summary.json.\n"
                target.write_text(notice, encoding="utf-8")
                error_log.write_text(notice, encoding="utf-8")
        self.record(name, "failed" if error else "passed", command=args, exit_code=code,
                    stdout=target.name, stderr=error_log.name,
                    duration_seconds=round(time.monotonic() - started, 3), error=error)
        return error is None

    def action(self, name, action):
        try:
            action()
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            self.record(name, "failed", error=str(exc))
            return False
        self.record(name, "passed")
        return True

    def blocked(self, name, reason):
        self.record(name, "blocked", error=reason)

    def docker_tool(self, image, source, report_directory=None):
        return [
            "docker", "run", "--rm", "--user", str(os.getuid()) + ":" + str(os.getgid()),
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=1g", "--env", "HOME=/tmp",
            "--mount", "type=bind,src=" + str(source) + ",dst=/src,readonly",
            "--mount", "type=bind,src=" + str(report_directory or self.directory) + ",dst=/reports",
            "--mount", "type=bind,src=" + str(ROOT / ".cache/trivy") + ",dst=/cache",
            "--workdir", "/src", image,
        ]

    def trivy(self, *args):
        return self.docker_tool(self.pins["trivy"], self.source or ROOT) + [
            "--config=", "--cache-dir", "/cache", "--timeout", "10m", *args,
            "--ignorefile=", "--disable-telemetry", "--skip-version-check",
        ]

    def gitleaks(self, name, source, mode, *options):
        if not self.action(name + "-configuration", lambda: reject_gitleaks_configuration(
                ROOT, self.source or source, source)):
            self.blocked(name, "Configuração/ignore automático do Gitleaks não é permitido")
            return
        # O scanner nunca escreve conteúdo bruto dentro de reports/, nem durante uma falha/interrupção.
        with tempfile.TemporaryDirectory(prefix="cloudcost-gitleaks-") as temporary:
            private_directory = Path(temporary)
            report = self.directory / (name + ".json")
            args = self.docker_tool(self.pins["gitleaks"], source, private_directory) + [
                mode, "/src", *options, "--redact=100", "--no-banner", "--no-color",
                "--ignore-gitleaks-allow", "--report-format", "json",
                "--report-path", "/reports/findings.json", "--exit-code", "1",
            ]
            self.command(name, args, private_logs=True,
                         after=lambda: sanitize_gitleaks(private_directory / "findings.json", report),
                         validate=lambda _: require(not load_json(report), "Gitleaks reportou segredos"))

    def snapshot(self, destination):
        listing = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                 cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        paths = sorted(set(os.fsdecode(p) for p in listing.stdout.split(b"\0") if p))
        copied = []
        for name in paths:
            source = ROOT / name
            if not source.exists():
                continue  # Uma remoção no worktree também deve desaparecer do snapshot.
            require(source.is_file() and not source.is_symlink(),
                    "Snapshot exige arquivo regular, sem submódulos/symlinks: " + name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(name)
        require("Dockerfile" in copied and "go.mod" in copied, "Snapshot incompleto")
        json_file(self.directory / "source-files.json", copied)
        self.source = destination

    def source_checks(self, snapshot):
        self.command("go-version", ["go", "version"], validate=lambda p: require(
            "go" + self.pins["go"] + " " in p.read_text(), "Toolchain Go divergente"))
        self.command("go-vet", ["go", "vet", "./..."])
        self.command("go-test", ["go", "test", "-count=1", "-json",
                                 "-coverprofile=" + str(self.directory / "coverage.out"), "./..."],
                     output="go-test.jsonl")
        for tool in ("gosec", "govulncheck"):
            installed = self.command("install-" + tool, ["go", "install", self.pins[tool]])
            executable = str(ROOT / ".tools/bin" / tool)
            if not installed:
                self.blocked(tool, "Instalação da versão fixada falhou; binário antigo não é usado")
            elif tool == "gosec":
                self.command("gosec", [executable, "-tests", "-nosec=true", "-fmt=json",
                                       "-out=" + str(self.directory / "gosec.json"), "./..."],
                             validate=lambda _: require(isinstance(load_json(self.directory / "gosec.json"), dict),
                                                        "Relatório gosec ausente/inválido"))
            else:
                self.command("govulncheck", [executable, "-json", "-test", "./..."],
                             output="govulncheck.json", validate=check_govulncheck)
        snapshot_ok = self.action("source-snapshot", lambda: self.snapshot(snapshot))
        if snapshot_ok:
            self.gitleaks("gitleaks-worktree", snapshot, "dir")
            self.command("trivy-config", self.trivy(
                "config", "--exit-code", "1", "--severity", "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL",
                "--include-non-failures", "--format", "json", "--output", "/reports/trivy-config.json", "/src",
            ), validate=lambda _: check_trivy_config(self.directory / "trivy-config.json"))
        else:
            self.blocked("gitleaks-worktree", "Snapshot incompleto")
            self.blocked("trivy-config", "Snapshot incompleto")
        head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if head.returncode == 0:
            self.gitleaks("gitleaks-history", ROOT, "git", "--log-opts=--all")
        elif os.environ.get("GITHUB_ACTIONS") == "true":
            self.blocked("gitleaks-history", "Checkout CI sem HEAD válido")
        else:
            self.record("gitleaks-history", "not-applicable", reason="Repositório local ainda sem commits; worktree é examinado")
        self.command("compose-config", ["docker", "compose", "--project-directory", str(ROOT),
                                       "-f", str(ROOT / "compose.yaml"), "config", "--format", "json"],
                     output="compose.resolved.json", validate=check_compose)

    def acquire_image(self, remote):
        if remote:
            require(re.fullmatch(r"[a-z0-9][a-z0-9./_-]*@sha256:[0-9a-f]{64}", remote),
                    "Rescan exige referência imutável de registry com @sha256:<64 hex minúsculos>; tags não são aceitas")
            acquired = self.command("image-pull", ["docker", "pull", remote])
            reference = remote
        else:
            commit = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            revision = commit.stdout.decode().strip() if commit.returncode == 0 else "uncommitted"
            epoch = "0"
            if commit.returncode == 0:
                epoch = subprocess.check_output(["git", "show", "-s", "--format=%ct", "HEAD"], cwd=ROOT).decode().strip()
            json_file(self.directory / "source-revision.json", {"revision": revision, "source_date_epoch": epoch})
            acquired = self.command("image-build", ["docker", "build", "--pull", "--build-arg", "VCS_REF=" + revision,
                                                    "--build-arg", "SOURCE_DATE_EPOCH=" + epoch,
                                                    "--tag", "cloudcost:local", "."])
            reference = "cloudcost:local"
        if not acquired:
            self.blocked("image-inspect", "Aquisição da imagem falhou; imagem antiga não é usada")
            return False
        if not self.command("image-inspect", ["docker", "image", "inspect", reference],
                            output="image-inspect.json", validate=check_image):
            return False
        self.image_id = load_json(self.directory / "image-inspect.json")[0]["Id"]
        json_file(self.directory / "image-identity.json", {
            "image_id": self.image_id, "requested_reference": reference,
            "repo_digests": load_json(self.directory / "image-inspect.json")[0].get("RepoDigests", []),
        })
        if not self.command("image-save", ["docker", "image", "save", "--output",
                                           str(self.directory / "image.tar"), self.image_id]):
            return False
        return self.action("image-archive-checksum", self.archive_checksum)

    def archive_checksum(self):
        digest = hashlib.sha256()
        with (self.directory / "image.tar").open("rb") as archive:
            for chunk in iter(lambda: archive.read(1024 * 1024), b""):
                digest.update(chunk)
        (self.directory / "image.tar.sha256").write_text(digest.hexdigest() + "  image.tar\n", encoding="ascii")

    def image_checks(self):
        self.command("trivy-image", self.trivy(
            "image", "--input", "/reports/image.tar", "--scanners", "vuln",
            "--severity", "HIGH,CRITICAL", "--ignore-unfixed=false", "--exit-code", "1",
            "--format", "json", "--output", "/reports/trivy-image.json", "--no-progress",
        ), validate=lambda _: check_trivy_image(self.directory / "trivy-image.json"))
        self.command("sbom", self.trivy(
            "image", "--input", "/reports/image.tar", "--format", "cyclonedx",
            "--output", "/reports/sbom.cdx.json", "--no-progress",
        ), validate=lambda _: check_sbom(self.directory / "sbom.cdx.json"))
        self.runtime_checks()

    def runtime_checks(self):
        self.container = "cloudcost-audit-" + uuid.uuid4().hex[:12]
        started = self.command("container-start", [
            "docker", "run", "--detach", "--name", self.container,
            "--read-only", "--user", "65532:65532", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--pids-limit", "64",
            "--memory", "128m", "--cpus", "0.5", "--publish", "127.0.0.1::8080",
            "--health-interval", "1s", "--health-timeout", "3s", "--health-start-period", "1s",
            "--health-retries", "10", self.image_id,
        ])
        if not started:
            self.blocked("http-dast", "Contêiner não iniciou")
            return
        if not self.action("container-health-hardening", self.wait_healthy):
            self.blocked("http-dast", "Healthcheck/hardening falhou")
            return
        inspected = load_json(self.directory / "container-inspect.json")[0]
        port = inspected["NetworkSettings"]["Ports"]["8080/tcp"][0]["HostPort"]
        self.command("http-dast", [sys.executable, str(ROOT / "scripts/smoke.py"),
                                   "http://127.0.0.1:" + port, "--report", str(self.directory / "dast.json")])

    def wait_healthy(self):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            raw = subprocess.check_output(["docker", "inspect", self.container], cwd=ROOT)
            inspected = json.loads(raw)
            json_file(self.directory / "container-inspect.json", inspected)
            container = inspected[0]
            require(container["State"]["Running"], "Contêiner encerrou antes de ficar saudável")
            health = container["State"].get("Health", {}).get("Status")
            require(health != "unhealthy", "Healthcheck Docker falhou")
            if health == "healthy":
                host = container["HostConfig"]
                require(container["Image"] == self.image_id, "Imagem executada diverge da imagem examinada")
                require(container["Config"]["User"] == "65532:65532", "UID/GID divergentes")
                require(host["ReadonlyRootfs"], "Rootfs gravável")
                require("ALL" in host["CapDrop"] and not host.get("CapAdd"), "Capabilities inseguras")
                require(any(x.startswith("no-new-privileges") for x in host["SecurityOpt"]), "Escalada de privilégios permitida")
                require(not host["Privileged"], "Modo privilegiado")
                require(host["Memory"] == 128 * 1024 * 1024 and host["PidsLimit"] == 64,
                        "Limites de memória/processos não aplicados")
                require(host["NanoCpus"] == 500000000, "Limite de CPU não aplicado")
                bindings = container["NetworkSettings"]["Ports"]["8080/tcp"]
                require(all(p["HostIp"] == "127.0.0.1" for p in bindings), "Porta exposta fora do loopback")
                return
            time.sleep(1)
        raise ValueError("Contêiner não ficou saudável em 60 segundos")

    def finish(self):
        if self.container:
            self.command("container-logs", ["docker", "logs", self.container])
            self.command("container-remove", ["docker", "rm", "--force", self.container])
        failed = any(s["status"] not in ("passed", "not-applicable") for s in self.steps)
        report = {
            "schema_version": 1, "mode": self.mode,
            "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "status": "failed" if failed else "passed", "image_id": self.image_id,
            "report_directory": str(self.directory.relative_to(ROOT)), "steps": self.steps,
        }
        json_file(self.directory / "summary.json", report)
        json_file(ROOT / "reports/latest.json", report)
        print("Resultado: " + report["status"] + "; " + str(self.directory / "summary.json"), flush=True)
        return 1 if failed else 0


def reject_gitleaks_configuration(*directories):
    for directory in set(map(Path, directories)):
        for name in (".gitleaks.toml", ".gitleaksignore"):
            candidate = directory / name
            require(not candidate.exists() and not candidate.is_symlink(),
                    "Arquivo automático de configuração/supressão Gitleaks não permitido: " + str(candidate))


def sanitize_gitleaks(source, destination):
    findings = load_json(source)
    require(isinstance(findings, list), "Relatório Gitleaks inválido; nenhuma evidência bruta será publicada")
    sanitized = []
    for finding in findings:
        require(isinstance(finding, dict), "Finding Gitleaks inválido; sanitização bloqueada")
        # Message não é redigido nativamente; Fragment pode carregar conteúdo/metadados originais.
        sanitized.append({key: value for key, value in finding.items() if key not in ("Message", "Fragment")})
    json_file(destination, sanitized)


def check_govulncheck(path):
    # O modo JSON do govulncheck retorna 0 MESMO com vulnerabilidades; avaliar o stream é obrigatório.
    text = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    offset = 0
    messages = []
    while offset < len(text):
        while offset < len(text) and text[offset].isspace():
            offset += 1
        if offset == len(text):
            break
        message, offset = decoder.raw_decode(text, offset)
        require(isinstance(message, dict), "Mensagem govulncheck inválida")
        messages.append(message)
    require(any("config" in m for m in messages), "Stream govulncheck vazio/incompleto")
    findings = [m["finding"] for m in messages if "finding" in m]
    require(not findings, "govulncheck reportou " + str(len(findings)) + " finding(s), inclusive stdlib/não alcançáveis")


def check_trivy_config(path):
    diagnostic = Path(path).with_name("trivy-config.stderr.log").read_text(encoding="utf-8", errors="replace")
    require("Falling back to embedded checks" not in diagnostic,
            "Trivy não obteve/carregou o bundle de checks; fallback embutido não aprova o gate")
    report = load_json(path)
    results = report.get("Results") or []
    require(any(r.get("Type") == "dockerfile" for r in results), "Trivy não examinou Dockerfile")
    findings = [m for result in results for m in (result.get("Misconfigurations") or [])]
    require(all(m.get("Status") == "PASS" for m in findings), "Trivy reportou falhas/exceções de configuração")


def check_trivy_image(path):
    report = load_json(path)
    require(report.get("ArtifactType") == "container_image", "Relatório Trivy não descreve imagem")
    results = report.get("Results") or []
    require(any(r.get("Type") == "gobinary" for r in results), "Trivy não reconheceu o binário Go/stdlib")
    require(not any(r.get("Vulnerabilities") for r in results), "Trivy reportou vulnerabilidades HIGH/CRITICAL")


def check_sbom(path):
    report = load_json(path)
    require(report.get("bomFormat") == "CycloneDX" and report.get("components"), "SBOM CycloneDX vazio/inválido")
    require(any(c.get("name") == "stdlib" for c in report["components"]), "SBOM não contém a biblioteca padrão Go")


def check_image(path):
    image = load_json(path)[0]
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", image["Id"]), "Image ID inválido")
    require(image["Config"]["User"] == "65532:65532", "Imagem não usa UID/GID 65532")
    require(image["Config"]["Entrypoint"] == ["/cloudcost"], "Entrypoint divergente")
    require(image["Config"].get("Healthcheck", {}).get("Test") == ["CMD", "/cloudcost", "healthcheck"],
            "Imagem sem healthcheck nativo")


def check_compose(path):
    app = load_json(path)["services"]["app"]
    require(app["image"] == "cloudcost:local", "Imagem local padrão divergente")
    require(app["user"] == "65532:65532" and app["read_only"], "Compose permite root/escrita")
    require("ALL" in app["cap_drop"] and not app.get("cap_add"), "Capabilities inseguras")
    require(any(x.startswith("no-new-privileges") for x in app["security_opt"]), "Compose sem no-new-privileges")
    require(not app.get("privileged", False) and not app.get("volumes"), "Compose privilegiado ou com montagem desnecessária")
    # Compose pode serializar limites inteiros como strings decimais; não arredondar/truncar valores.
    require(str(app["pids_limit"]) == "64" and str(app["mem_limit"]) == "134217728"
            and float(app["cpus"]) == 0.5, "Limites Compose divergentes")
    require(app["healthcheck"]["test"] == ["CMD", "/cloudcost", "healthcheck"], "Healthcheck Compose divergente")
    require(len(app["ports"]) == 1 and app["ports"][0]["host_ip"] == "127.0.0.1"
            and app["ports"][0]["target"] == 8080 and str(app["ports"][0]["published"]) == "8080",
            "Compose deve expor somente 127.0.0.1:8080")


def main():
    parser = argparse.ArgumentParser(description="Gates CloudCost: Docker + Go + Python3 + Git; evidências em reports/.")
    parser.add_argument("--rescan", metavar="IMAGE@sha256:DIGEST", help="Puxa imagem já publicada somente por digest imutável; não aceita tags nem reconstrói")
    args = parser.parse_args()
    audit = Audit("rescan" if args.rescan else "full")
    try:
        with tempfile.TemporaryDirectory(prefix="cloudcost-source-") as directory:
            if not args.rescan:
                audit.source_checks(Path(directory))
            if audit.acquire_image(args.rescan):
                audit.image_checks()
            else:
                for gate in ("trivy-image", "sbom", "http-dast"):
                    audit.blocked(gate, "Não há artefato adquirido/exportado nesta execução")
    except KeyboardInterrupt:
        audit.record("interrupted", "failed", error="Execução interrompida; resultado não pode aprovar publicação")
    except Exception as exc:
        audit.record("orchestration", "failed", error=str(exc))
    finally:
        exit_code = audit.finish()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
