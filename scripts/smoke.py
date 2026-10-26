#!/usr/bin/env python3
"""Smoke/DAST dirigido, sem dependências externas; não é um pentest completo."""

import argparse
import datetime as dt
from html.parser import HTMLParser
import http.client
import json
from pathlib import Path
import ssl
import sys
import time
from urllib.parse import urljoin, urlsplit

EXAMPLE = {
    "instances": 1, "hours_per_month": 720, "hourly_rate": 0.1,
    "storage_gb": 100, "storage_rate": 0.1, "egress_gb": 50, "egress_rate": 0.1,
}
LIMITS = {
    "instances": 10000, "hours_per_month": 744, "hourly_rate": 1000,
    "storage_gb": 1000000, "storage_rate": 1000, "egress_gb": 1000000, "egress_rate": 1000,
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.styles = []
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        require(not any(name.lower().startswith("on") for name in attributes), "Handler inline no HTML")
        require("style" not in attributes and tag != "style", "Estilo inline no HTML")
        if tag == "script":
            require(attributes.get("src"), "Script sem arquivo externo local")
            self.scripts.append(attributes["src"])
            self.in_script = True
        elif tag == "link" and "stylesheet" in attributes.get("rel", "").split():
            require(attributes.get("href"), "Stylesheet sem href")
            self.styles.append(attributes["href"])

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        require(not self.in_script or not data.strip(), "Código inline no HTML")


class Suite:
    def __init__(self, base_url):
        self.base = urlsplit(base_url)
        require(self.base.scheme in ("http", "https") and self.base.hostname, "URL deve usar HTTP ou HTTPS")
        require(not self.base.username and not self.base.password and not self.base.query and not self.base.fragment,
                "URL base não deve conter credenciais, query ou fragmento")
        self.prefix = self.base.path.rstrip("/")
        self.base_url = base_url.rstrip("/")
        self.results = []

    def run(self, name, case):
        start = time.monotonic()
        try:
            case()
            result = {"name": name, "status": "passed"}
        except Exception as exc:
            result = {"name": name, "status": "failed", "error": str(exc)}
        result["duration_seconds"] = round(time.monotonic() - start, 4)
        self.results.append(result)
        print(name + ": " + result["status"], flush=True)

    def request(self, method, path, body=None, media="application/json"):
        headers = {}
        if body is not None:
            if isinstance(body, dict):
                body = json.dumps(body, separators=(",", ":")).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            if media is not None:
                headers["Content-Type"] = media
        if self.base.scheme == "https":
            connection = http.client.HTTPSConnection(self.base.hostname, self.base.port, timeout=5,
                                                     context=ssl.create_default_context())
        else:
            connection = http.client.HTTPConnection(self.base.hostname, self.base.port, timeout=5)
        try:
            connection.request(method, self.prefix + path, body=body, headers=headers)
            response = connection.getresponse()
            response_headers = {key.lower(): value for key, value in response.getheaders()}
            payload = response.read(262145)
            require(len(payload) <= 262144, "Resposta inesperadamente grande")
            check_headers(response_headers)
            return response.status, response_headers, payload
        finally:
            connection.close()

    def json_request(self, method, path, expected_status, body=None, media="application/json"):
        status, headers, payload = self.request(method, path, body, media)
        require(status == expected_status, "HTTP esperado " + str(expected_status) + ", recebido " + str(status))
        require(headers.get("content-type", "").split(";", 1)[0].strip() == "application/json",
                "Resposta da API deve ser application/json")
        parsed = json.loads(payload)
        if status >= 400:
            require(isinstance(parsed, dict) and set(parsed) == {"error"}
                    and isinstance(parsed["error"], str) and parsed["error"], "Envelope de erro inválido")
        return parsed

    def health(self):
        require(self.json_request("GET", "/healthz", 200) == {"status": "ok"}, "Healthcheck inválido")

    def estimate(self, body, expected):
        parsed = self.json_request("POST", "/api/estimate", 200, body)
        require(parsed == expected, "Estimativa retornou valores divergentes: " + json.dumps(parsed))

    def homepage(self):
        status, headers, payload = self.request("GET", "/")
        require(status == 200 and headers.get("content-type", "").startswith("text/html"), "Página inicial ausente")
        html = payload.decode("utf-8")
        require("cloudcost" in html.lower(), "Identidade CloudCost ausente")
        parser = Assets()
        parser.feed(html)
        parser.close()
        require(parser.scripts and parser.styles, "HTML precisa de JavaScript e CSS locais")
        for reference, types in [(s, ("text/javascript", "application/javascript")) for s in parser.scripts] + [
            (s, ("text/css",)) for s in parser.styles
        ]:
            resolved = urlsplit(urljoin(self.base_url + "/", reference))
            require((resolved.scheme, resolved.netloc) == (self.base.scheme, self.base.netloc), "Asset externo/CDN")
            require(resolved.path.startswith(self.prefix + "/"), "Asset fora da URL base")
            relative = resolved.path[len(self.prefix):]
            if resolved.query:
                relative += "?" + resolved.query
            code, asset_headers, asset = self.request("GET", relative)
            require(code == 200 and asset, "Asset local indisponível")
            require(asset_headers.get("content-type", "").split(";", 1)[0].strip() in types, "MIME incorreto no asset")

    def rejected(self, body, status=400, media="application/json"):
        self.json_request("POST", "/api/estimate", status, body, media)

    def method(self, method):
        status, headers, body = self.request(method, "/api/estimate")
        require(status == 405, "Método não permitido deve retornar 405")
        if method == "HEAD":
            require(not body, "HEAD deve retornar 405 sem corpo")
        else:
            require(headers.get("content-type", "").startswith("application/json"), "Erro deve ser JSON")
            parsed = json.loads(body)
            require(isinstance(parsed, dict) and set(parsed) == {"error"} and parsed["error"], "Envelope de erro inválido")
        require("POST" in headers.get("allow", ""), "405 precisa anunciar Allow: POST")


def check_headers(headers):
    require(headers.get("x-content-type-options") == "nosniff", "nosniff ausente")
    require(headers.get("referrer-policy") == "no-referrer", "Referrer-Policy insegura")
    require("set-cookie" not in headers, "A aplicação stateless não deve definir cookies")
    require("access-control-allow-origin" not in headers, "CORS inesperado")
    policy = headers.get("content-security-policy", "")
    directives = {}
    for item in policy.split(";"):
        pieces = item.split()
        if pieces:
            directives[pieces[0]] = pieces[1:]
    require(directives.get("frame-ancestors") == ["'none'"], "CSP permite enquadramento")
    require("'unsafe-inline'" not in policy and "'unsafe-eval'" not in policy, "CSP permite execução inline/eval")
    for kind in ("script-src", "style-src"):
        require(directives.get(kind, directives.get("default-src")) == ["'self'"], "CSP deve restringir " + kind + " a self")
    permissions = headers.get("permissions-policy", "").replace(" ", "")
    for feature in ("camera=()", "microphone=()", "geolocation=()"):
        require(feature in permissions, "Permissions-Policy não restringe " + feature)


def main():
    parser = argparse.ArgumentParser(description="Smoke/DAST CloudCost contra uma URL autorizada; Python3 stdlib.")
    parser.add_argument("base_url", help="Exemplo: http://127.0.0.1:8080")
    parser.add_argument("--report", type=Path, help="Grava relatório JSON, inclusive quando há falhas")
    args = parser.parse_args()
    suite = Suite(args.base_url)
    suite.run("health-inicial", suite.health)
    suite.run("html-assets-csp-sem-inline", suite.homepage)
    suite.run("estimativa-exemplo-87-usd", lambda: suite.estimate(EXAMPLE, {
        "compute": 72, "storage": 10, "egress": 5, "total": 87, "currency": "USD",
    }))
    suite.run("estimativa-zero", lambda: suite.estimate(dict.fromkeys(EXAMPLE, 0), {
        "compute": 0, "storage": 0, "egress": 0, "total": 0, "currency": "USD",
    }))
    suite.run("limites-superiores-validos", lambda: suite.estimate(LIMITS, {
        "compute": 7440000000, "storage": 1000000000, "egress": 1000000000,
        "total": 9440000000, "currency": "USD",
    }))
    suite.run("arredondamento-em-centavos", lambda: suite.estimate({
        **dict.fromkeys(EXAMPLE, 0), "instances": 1, "hours_per_month": 1, "hourly_rate": 0.005,
    }, {"compute": 0.01, "storage": 0, "egress": 0, "total": 0.01, "currency": "USD"}))
    for field in EXAMPLE:
        absent = {key: value for key, value in EXAMPLE.items() if key != field}
        suite.run("campo-ausente-" + field, lambda body=absent: suite.rejected(body))
        suite.run("campo-null-" + field, lambda key=field: suite.rejected({**EXAMPLE, key: None}))
        suite.run("campo-negativo-" + field, lambda key=field: suite.rejected({**EXAMPLE, key: -1}))
        suite.run("campo-acima-limite-" + field,
                  lambda key=field: suite.rejected({**EXAMPLE, key: LIMITS[key] + 1}))
    invalid = {
        "campo-desconhecido": {**EXAMPLE, "unexpected": 1},
        "instancias-fracionarias": {**EXAMPLE, "instances": 1.5},
        "numero-como-string": {**EXAMPLE, "hourly_rate": "0.1"},
        "booleano-como-numero": {**EXAMPLE, "instances": True},
        "json-malformado": '{"instances":',
        "json-array": "[]",
        "json-null": "null",
        "json-vazio": "",
        "json-objeto-vazio": "{}",
        "json-trailing": json.dumps(EXAMPLE) + " {}",
        "json-nao-finito": json.dumps(EXAMPLE).replace('"hourly_rate": 0.1', '"hourly_rate": NaN'),
        "expoente-curto-dos": json.dumps(EXAMPLE).replace('"hourly_rate": 0.1', '"hourly_rate": 1e-999999999'),
        "texto-injecao": {**EXAMPLE, "hourly_rate": "<script>alert(1)</script>"},
    }
    for name, body in invalid.items():
        suite.run(name, lambda payload=body: suite.rejected(payload))
    suite.run("corpo-acima-4096", lambda: suite.rejected(" " * 4097 + json.dumps(EXAMPLE), 413))
    suite.run("trailing-acima-4096", lambda: suite.rejected(json.dumps(EXAMPLE) + " " * 4097, 413))
    suite.run("media-texto-rejeitada", lambda: suite.rejected(EXAMPLE, 415, "text/plain"))
    suite.run("media-ausente-rejeitada", lambda: suite.rejected(EXAMPLE, 415, None))
    suite.run("media-json-utf8", lambda: suite.json_request("POST", "/api/estimate", 200, EXAMPLE, "application/json; charset=utf-8"))
    for method in ("GET", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
        suite.run("metodo-rejeitado-" + method, lambda verb=method: suite.method(verb))
    suite.run("health-metodo-rejeitado", lambda: suite.json_request("POST", "/healthz", 405))
    suite.run("rota-inexistente", lambda: require(suite.request("GET", "/does-not-exist")[0] == 404, "Rota desconhecida não retornou 404"))
    suite.run("health-apos-rejeicoes", suite.health)
    failed = sum(item["status"] == "failed" for item in suite.results)
    report = {
        "scope": "Smoke/DAST dirigido; não substitui pentest ou revisão manual",
        "base_url": args.base_url, "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "failed" if failed else "passed", "total": len(suite.results),
        "failed": failed, "cases": suite.results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(len(suite.results)) + " casos; " + str(failed) + " falhas.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
