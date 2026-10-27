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
DOCKER_HUB_REGISTRIES = ("docker.io", "index.docker.io", "registry-1.docker.io")
MANIFEST_TYPES = (
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)
INDEX_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
)


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
        self.requested_reference = None
        self.remote_reference = None
        self.registry_auth = None
        self.manifest_resolution = None
        self.scan_source = "registry" if mode == "rescan" else "archive"
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

    def docker_tool(self, image, source, report_directory=None, registry_auth=None):
        args = [
            "docker", "run", "--rm", "--user", str(os.getuid()) + ":" + str(os.getgid()),
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=1g", "--env", "HOME=/tmp",
            "--mount", "type=bind,src=" + str(source) + ",dst=/src,readonly",
            "--mount", "type=bind,src=" + str(report_directory or self.directory) + ",dst=/reports",
            "--mount", "type=bind,src=" + str(ROOT / ".cache/trivy") + ",dst=/cache",
            "--workdir", "/src",
        ]
        if registry_auth is not None:
            args += [
                "--mount", "type=bind,src=" + str(registry_auth) + ",dst=/registry-auth,readonly",
                "--env", "DOCKER_CONFIG=/registry-auth",
            ]
        return args + [image]

    def trivy(self, *args):
        return self.docker_tool(self.pins["trivy"], self.source or ROOT, registry_auth=self.registry_auth) + [
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

    def prepare_registry_auth(self, reference, directory):
        registry = reference.split("/", 1)[0]
        source = Path(self.env.get("DOCKER_CONFIG") or Path.home() / ".docker") / "config.json"
        config = load_json(source) if source.exists() else {}
        require(isinstance(config, dict), "Configuração Docker inválida para autenticação de registry")
        helpers = config.get("credHelpers", {})
        auths = config.get("auths", {})
        require(isinstance(helpers, dict) and isinstance(auths, dict), "Configuração Docker de credenciais inválida")
        auth_key, candidates = registry_auth_scope(registry)
        require(not config.get("credsStore") and not any(helpers.get(key) for key in candidates),
                "Credential helper Docker não suportado no rescan; use DOCKER_CONFIG temporário com login restrito ao registry")
        entries = [auths[key] for key in candidates if key in auths]
        require(all(isinstance(entry, dict) for entry in entries), "Credencial Docker do registry tem formato inválido")
        entry = next((entry for entry in entries if entry), {})
        selected = {key: entry[key] for key in ("auth", "identitytoken", "registrytoken") if entry.get(key)}
        require(all(isinstance(value, str) for value in selected.values()),
                "Credencial Docker do registry deve conter valores textuais")
        require(not entry or selected, "Credencial Docker do registry não tem formato suportado; autentique novamente")
        directory.mkdir(mode=0o700)
        credential_file = directory / "config.json"
        descriptor = os.open(credential_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"auths": {auth_key: selected} if selected else {}}, stream)
        self.registry_auth = directory
        json_file(self.directory / "registry-access.json", {
            "registry": registry,
            "auth_key": auth_key,
            "authentication": "scoped-docker-config" if selected else "anonymous",
            "credentials_in_reports": False,
        })

    def resolve_remote_reference(self, requested):
        registry, repository = requested.split("/", 1)
        # As três autoridades são o mesmo Docker Hub; preserve a entrada original na evidência.
        current = ("docker.io/" + repository) if registry in DOCKER_HUB_REGISTRIES else requested
        repository = current.rsplit("@", 1)[0]
        chain = []
        # Mesmo limite de profundidade de azure-deploy.sh; o rescan seleciona somente Linux/amd64.
        for depth in range(5):
            name = "registry-manifest-" + str(depth)
            path = self.directory / (name + ".json")
            if not self.command(name, ["docker", "manifest", "inspect", current], output=path.name):
                raise ValueError("Não foi possível obter o manifesto remoto por digest")
            document = load_json(path)
            child = select_runtime_descriptor(document)
            chain.append({
                "reference": current, "media_type": document["mediaType"],
                "selected_child": child, "evidence": path.name,
            })
            if child is None:
                self.remote_reference = current
                self.manifest_resolution = {
                    "requested_reference": requested,
                    "runtime_reference": current,
                    "runtime_manifest_digest": current.rsplit("@", 1)[1],
                    "runtime_config_digest": document["config"]["digest"],
                    "required_platform": "linux/amd64",
                    "chain": chain,
                }
                json_file(self.directory / "manifest-resolution.json", self.manifest_resolution)
                return
            current = repository + "@" + child["digest"]
        raise ValueError("Índice remoto excessivamente aninhado; resolução bloqueada")

    def acquire_image(self, remote, auth_directory=None):
        if remote:
            require(re.fullmatch(r"[a-z0-9][a-z0-9./_-]*@sha256:[0-9a-f]{64}", remote),
                    "Rescan exige referência imutável de registry com @sha256:<64 hex minúsculos>; tags não são aceitas")
            require("/" in remote.partition("@")[0], "Rescan exige registry/repository@sha256:digest")
            require(auth_directory is not None, "Diretório temporário privado de autenticação ausente")
            self.requested_reference = remote
            if not self.action("registry-auth", lambda: self.prepare_registry_auth(remote, auth_directory)):
                return False
            if not self.action("registry-manifest-resolution", lambda: self.resolve_remote_reference(remote)):
                return False
            reference = self.remote_reference
            acquired = self.command("image-pull", ["docker", "pull", "--platform", "linux/amd64", reference])
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
            self.requested_reference = reference
        if not acquired:
            self.blocked("image-inspect", "Aquisição da imagem falhou; imagem antiga não é usada")
            return False
        if not self.command("image-inspect", ["docker", "image", "inspect", reference],
                            output="image-inspect.json", validate=lambda path: check_image(path, self.remote_reference)):
            return False
        self.image_id = load_json(self.directory / "image-inspect.json")[0]["Id"]
        json_file(self.directory / "image-identity.json", {
            "image_id": self.image_id, "requested_reference": self.requested_reference,
            "repo_digests": load_json(self.directory / "image-inspect.json")[0].get("RepoDigests", []),
            "scan_source": self.scan_source,
            "scan_reference": self.remote_reference if remote else "image.tar",
            "scan_platform": "linux/amd64" if remote else None,
            "manifest_resolution": "manifest-resolution.json" if remote else None,
        })
        if remote:
            # O registry é a fonte canônica: snapshots locais podem funcionar sem todos os blobs exportáveis.
            return True
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
        scan_input = (["--image-src", "remote", "--platform", "linux/amd64", self.remote_reference]
                      if self.remote_reference else ["--input", "/reports/image.tar"])
        self.command("trivy-image", self.trivy(
            "image", *scan_input, "--scanners", "vuln",
            "--severity", "HIGH,CRITICAL", "--ignore-unfixed=false", "--exit-code", "1",
            "--format", "json", "--output", "/reports/trivy-image.json", "--no-progress",
        ), validate=lambda _: check_trivy_image(self.directory / "trivy-image.json"))
        self.command("sbom", self.trivy(
            "image", *scan_input, "--format", "cyclonedx",
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
            "requested_reference": self.requested_reference,
            "scan_source": self.scan_source,
            "scan_reference": self.remote_reference if self.scan_source == "registry" else "image.tar",
            "manifest_resolution": "manifest-resolution.json" if self.manifest_resolution else None,
            "report_directory": str(self.directory.relative_to(ROOT)), "steps": self.steps,
        }
        json_file(self.directory / "summary.json", report)
        json_file(ROOT / "reports/latest.json", report)
        print("Resultado: " + report["status"] + "; " + str(self.directory / "summary.json"), flush=True)
        return 1 if failed else 0


def registry_auth_scope(registry):
    """Retorna (chave de saída, aliases aceitos) sem consultar ou expor credenciais."""
    if registry in DOCKER_HUB_REGISTRIES:
        key = "https://index.docker.io/v1/"
        aliases = [key]
        for host in DOCKER_HUB_REGISTRIES:
            aliases.extend((host, "https://" + host, "https://" + host + "/v1/"))
        return key, tuple(dict.fromkeys(aliases))
    return registry, (registry, "https://" + registry, "https://" + registry + "/v1/")


def select_runtime_descriptor(document):
    """Retorna o único candidato Linux/amd64 de um índice, ou None para manifesto final."""
    require(isinstance(document, dict) and document.get("schemaVersion") == 2, "Manifesto remoto inválido")
    media_type = document.get("mediaType")
    if media_type in MANIFEST_TYPES:
        config = document.get("config")
        require(isinstance(config, dict) and isinstance(config.get("digest"), str)
                and re.fullmatch(r"sha256:[0-9a-f]{64}", config["digest"]), "Config digest remoto inválido")
        return None
    require(media_type in INDEX_TYPES, "Tipo de manifesto remoto não suportado")
    children = document.get("manifests")
    require(isinstance(children, list) and children, "Índice remoto vazio ou inválido")
    candidates = []
    for child in children:
        require(isinstance(child, dict) and isinstance(child.get("digest"), str)
                and re.fullmatch(r"sha256:[0-9a-f]{64}", child["digest"]), "Descriptor remoto inválido")
        annotations = child.get("annotations", {})
        require(isinstance(annotations, dict), "Anotações de descriptor remoto inválidas")
        if annotations.get("vnd.docker.reference.type") == "attestation-manifest":
            require(child.get("mediaType") in MANIFEST_TYPES
                    and child.get("platform") == {"os": "unknown", "architecture": "unknown"},
                    "Descriptor de attestation remoto inválido")
            continue
        require(child.get("mediaType") in MANIFEST_TYPES + INDEX_TYPES, "Descriptor executável não suportado")
        platform = child.get("platform")
        if platform is None:
            # Sem plataforma, é candidato potencial, nunca uma suposição de AMD64.
            candidates.append(child)
        else:
            require(isinstance(platform, dict) and isinstance(platform.get("os"), str)
                    and platform["os"] and isinstance(platform.get("architecture"), str)
                    and platform["architecture"], "Plataforma de descriptor remoto incompleta")
            if platform["os"] == "linux" and platform["architecture"] == "amd64":
                candidates.append(child)
    require(len(candidates) == 1,
            "Índice remoto exige exatamente um candidato Linux/amd64; variantes/metadados ambíguos bloqueiam")
    return candidates[0]


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


def check_image(path, remote=None):
    image = load_json(path)[0]
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", image["Id"]), "Image ID inválido")
    require(image["Config"]["User"] == "65532:65532", "Imagem não usa UID/GID 65532")
    require(image["Config"]["Entrypoint"] == ["/cloudcost"], "Entrypoint divergente")
    require(image["Config"].get("Healthcheck", {}).get("Test") == ["CMD", "/cloudcost", "healthcheck"],
            "Imagem sem healthcheck nativo")
    if remote:
        require(image.get("Os") == "linux" and image.get("Architecture") == "amd64",
                "Rescan remoto exige a mesma plataforma linux/amd64 no Docker e no Trivy")
        digest = remote.rsplit("@", 1)[1]
        require(any(value.rsplit("@", 1)[-1] == digest for value in image.get("RepoDigests", [])),
                "Imagem local não comprova o digest imutável solicitado ao registry")


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
    parser.add_argument("--rescan", metavar="IMAGE@sha256:DIGEST", help="Examina diretamente o registry por digest e executa a mesma imagem linux/amd64 via Docker; sem tags, rebuild ou reexportação")
    args = parser.parse_args()
    audit = Audit("rescan" if args.rescan else "full")
    try:
        with tempfile.TemporaryDirectory(prefix="cloudcost-source-") as directory:
            if not args.rescan:
                audit.source_checks(Path(directory))
            if audit.acquire_image(args.rescan, Path(directory) / "registry-auth"):
                audit.image_checks()
            else:
                for gate in ("trivy-image", "sbom", "http-dast"):
                    audit.blocked(gate, "Não há entrada de scan autenticada/adquirida nesta execução")
    except KeyboardInterrupt:
        audit.record("interrupted", "failed", error="Execução interrompida; resultado não pode aprovar publicação")
    except Exception as exc:
        audit.record("orchestration", "failed", error=str(exc))
    finally:
        exit_code = audit.finish()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
