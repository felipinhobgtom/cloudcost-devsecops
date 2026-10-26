#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
fail() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
evidence=${AZURE_EVIDENCE_DIR:-azure-evidence}
mkdir -p "$evidence"
[[ $# -ge 1 ]] || fail 'Uso: azure-deploy.sh prepare DIRETORIO SHA | deploy LOADED_IMAGE_ID CONFIG_DIGEST SHA CI_RUN_ID | rollback ACR/cloudcost@sha256:DIGEST | rescan'
operation=$1
shift
for cmd in docker jq python3; do command -v "$cmd" >/dev/null || fail "Pré-requisito ausente: $cmd"; done

if [[ $operation == prepare ]]; then
  [[ $# == 2 && $2 =~ ^[0-9a-f]{40}$ ]] || fail 'prepare exige diretório do artefato e commit SHA completo.'
  # Apenas leitura de metadados e hashes. Nunca extrair/executar conteúdo do artefato.
  python3 - "$1" "$2" "$evidence" <<'PY'
import gzip
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tarfile
import tempfile

base, revision, evidence = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
digest_pattern = r"sha256:[0-9a-f]{64}"
index_types = {"application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"}
manifest_types = {"application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"}

def require(condition, message):
    if not condition:
        raise SystemExit(message)

def read_json(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 8 * 1024 * 1024, f"Metadado inválido: {path}")
    return json.loads(path.read_bytes())

def inspect_archive(path, reported_id):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 1024 ** 3, "Docker archive ausente ou maior que 1 GiB")
    with tarfile.open(path, mode="r:") as archive:
        members = archive.getmembers()
        require(0 < len(members) <= 256, "Número inesperado de membros no Docker archive")
        names = set()
        for member in members:
            name = member.name
            require(name not in names and not name.startswith("/") and ".." not in pathlib.PurePosixPath(name).parts, "Caminho duplicado/inseguro no Docker archive")
            require(re.fullmatch(r"[A-Za-z0-9_./-]+", name) and (member.isfile() or member.isdir()), "Links/dispositivos não são aceitos no Docker archive")
            names.add(name)
            if member.isfile() and re.fullmatch(r"blobs/sha256/[0-9a-f]{64}", name):
                with archive.extractfile(member) as stream:
                    require(hashlib.file_digest(stream, "sha256").hexdigest() == name.rsplit("/", 1)[1], "Blob OCI corrompido")
        def metadata(name):
            member = archive.getmember(name)
            require(member.isfile() and member.size <= 8 * 1024 * 1024, "Metadado Docker inválido")
            with archive.extractfile(member) as stream:
                return stream.read()
        def descriptor_path(descriptor):
            digest = descriptor.get("digest", "")
            require(re.fullmatch(digest_pattern, digest), "Digest de descriptor inválido")
            name = "blobs/sha256/" + digest.split(":", 1)[1]
            require(name in names and archive.getmember(name).isfile() and archive.getmember(name).size == descriptor.get("size"), "Descriptor OCI ausente ou tamanho divergente")
            return name
        docker_manifest = json.loads(metadata("manifest.json"))
        require(isinstance(docker_manifest, list) and len(docker_manifest) == 1, "Exige uma única imagem executável")
        entry = docker_manifest[0]
        require(entry.get("RepoTags") in (None, []), "Archive deve ser salvo por Image ID, sem tags")
        config_bytes = metadata(entry["Config"])
        config_digest = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
        config = json.loads(config_bytes)
        require(config.get("os") == "linux" and config.get("architecture") == "amd64", "Exige Linux/amd64")
        settings = config.get("config", {})
        require(settings.get("User") == "65532:65532" and settings.get("Entrypoint") == ["/cloudcost"], "Usuário/entrypoint inesperado")
        require(not settings.get("OnBuild") and not settings.get("Volumes"), "Hooks/volumes inesperados")
        require(settings.get("Labels", {}).get("org.opencontainers.image.revision") == revision, "Revision label não coincide com commit do CI")
        layers = entry.get("Layers", [])
        diff_ids = config.get("rootfs", {}).get("diff_ids", [])
        require(0 < len(layers) <= 16 and len(diff_ids) == len(layers), "Camadas/rootfs inválidos")
        for layer, expected_diff_id in zip(layers, diff_ids):
            require(re.fullmatch(digest_pattern, expected_diff_id) and layer in names and archive.getmember(layer).isfile(), "Camada/diff ID inválido")
            with archive.extractfile(layer) as raw:
                magic = raw.read(2)
                raw.seek(0)
                stream = gzip.GzipFile(fileobj=raw) if magic == b"\x1f\x8b" else raw
                digest, size = hashlib.sha256(), 0
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    require(size <= 1024 ** 3, "Camada descomprimida excede 1 GiB")
                    digest.update(chunk)
                require("sha256:" + digest.hexdigest() == expected_diff_id, "Bytes da camada não correspondem ao rootfs aprovado")
        root_digest = runtime_digest = None
        if "index.json" in names:
            require(json.loads(metadata("oci-layout")).get("imageLayoutVersion") == "1.0.0", "OCI layout inválido")
            index = json.loads(metadata("index.json"))
            require(index.get("schemaVersion") == 2 and len(index.get("manifests", [])) == 1, "OCI archive exige um único descriptor raiz")
            root = index["manifests"][0]
            root_digest = root.get("digest")
            def runtime_manifest(descriptor, depth=0):
                require(depth <= 4, "Índice OCI excessivamente aninhado")
                document = json.loads(metadata(descriptor_path(descriptor)))
                media_type = descriptor.get("mediaType")
                require(document.get("schemaVersion") == 2 and document.get("mediaType", media_type) == media_type, "Schema/media type OCI divergente")
                if media_type in index_types:
                    children = document.get("manifests", [])
                    require(0 < len(children) <= 16, "Índice OCI vazio/excessivo")
                    attestations = [child for child in children if child.get("annotations", {}).get("vnd.docker.reference.type") == "attestation-manifest"]
                    runnable = [child for child in children if child not in attestations]
                    require(len(runnable) == 1, "Índice deve conter uma única imagem executável")
                    platform = runnable[0].get("platform")
                    require(platform is None or (platform.get("os") == "linux" and platform.get("architecture") == "amd64"), "Plataforma OCI inesperada")
                    runtime = runtime_manifest(runnable[0], depth + 1)
                    for attestation in attestations:
                        require(attestation.get("mediaType") in manifest_types and attestation.get("platform") == {"architecture": "unknown", "os": "unknown"}, "Descriptor de attestation inválido")
                        require(attestation["annotations"].get("vnd.docker.reference.digest") == runtime, "Attestation não pertence à imagem executável")
                        statement = json.loads(metadata(descriptor_path(attestation)))
                        require(statement.get("schemaVersion") == 2, "Manifesto de attestation inválido")
                        require(statement.get("subject", {}).get("digest", runtime) == runtime, "Subject da attestation divergente")
                        descriptor_path(statement["config"])
                        for layer in statement.get("layers", []):
                            descriptor_path(layer)
                    return runtime
                require(media_type in manifest_types and document.get("config", {}).get("digest") == config_digest, "Manifesto OCI não aponta ao config aprovado")
                require(descriptor_path(document["config"]) == entry["Config"], "Config Docker/OCI divergente")
                require([descriptor_path(layer) for layer in document.get("layers", [])] == layers, "Camadas Docker/OCI divergentes")
                return descriptor["digest"]
            runtime_digest = runtime_manifest(root)
        require(reported_id in {config_digest, root_digest, runtime_digest}, "Image ID não pertence ao grafo config/manifest/index do archive")
        return {"config_digest": config_digest, "rootfs_diff_ids": diff_ids, "descriptor_digest": root_digest, "runtime_manifest_digest": runtime_digest}

identity = read_json(base / "image-identity.json")
summary = read_json(base / "summary.json")
source_image_id = identity.get("image_id", "")
require(re.fullmatch(digest_pattern, source_image_id), "Image ID de origem inválido")
require(summary.get("status") == "passed" and summary.get("image_id") == source_image_id, "Gate/identidade do artefato divergente")
archive_path = base / "image.tar"
checksum_path = base / "image.tar.sha256"
require(checksum_path.is_file() and not checksum_path.is_symlink() and checksum_path.stat().st_size < 256, "Checksum ausente/inválido")
checksum = re.fullmatch(r"([0-9a-f]{64})  image\.tar\n?", checksum_path.read_text())
require(checksum is not None, "Formato do checksum inválido")
require(archive_path.is_file() and not archive_path.is_symlink(), "Archive inválido")
with archive_path.open("rb") as stream:
    archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
require(archive_hash == checksum[1], "Checksum do Docker archive divergente")
source = inspect_archive(archive_path, source_image_id)
with (evidence / "docker-load.txt").open("w") as log:
    subprocess.run(["docker", "load", "--input", str(archive_path)], check=True, stdout=log)
loaded_ids = re.findall(r"^Loaded image ID: (sha256:[0-9a-f]{64})$", (evidence / "docker-load.txt").read_text(), re.MULTILINE)
require(len(loaded_ids) == 1, "docker load não retornou uma única identidade imutável")
inspection_bytes = subprocess.check_output(["docker", "image", "inspect", loaded_ids[0]])
(evidence / "loaded-image.json").write_bytes(inspection_bytes)
inspection = json.loads(inspection_bytes)
require(len(inspection) == 1, "Inspect carregado ambíguo")
loaded_image_id = inspection[0].get("Id", "")
require(re.fullmatch(digest_pattern, loaded_image_id), "Image ID carregado inválido")
require(inspection[0].get("RootFS", {}).get("Layers") == source["rootfs_diff_ids"], "Rootfs carregado diverge do artefato")
# Stores clássicos usam config ID; containerd pode usar manifest/index ID.
# Reexportar por ID prova os bytes do config/rootfs sem rebuild nem execução.
with tempfile.TemporaryDirectory(prefix="azure-loaded-", dir=evidence) as directory:
    loaded_archive = pathlib.Path(directory) / "image.tar"
    subprocess.run(["docker", "image", "save", "--output", str(loaded_archive), loaded_image_id], check=True)
    loaded = inspect_archive(loaded_archive, loaded_image_id)
require(loaded["config_digest"] == source["config_digest"] and loaded["rootfs_diff_ids"] == source["rootfs_diff_ids"], "Imagem carregada difere dos bytes aprovados")
prepared = {"source_image_id": source_image_id, "loaded_image_id": loaded_image_id, "config_digest": source["config_digest"], "source_descriptor_digest": source["descriptor_digest"], "loaded_descriptor_digest": loaded["descriptor_digest"], "loaded_runtime_manifest_digest": loaded["runtime_manifest_digest"], "rootfs_diff_ids": source["rootfs_diff_ids"], "source_sha": revision, "archive_sha256": archive_hash}
(evidence / "prepared-image.json").write_text(json.dumps(prepared, indent=2) + "\n")
outputs = f"loaded_image_id={loaded_image_id}\nconfig_digest={source['config_digest']}\n"
print(outputs, end="")
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(outputs)
PY
  exit 0
fi

for cmd in az curl; do command -v "$cmd" >/dev/null || fail "Pré-requisito ausente: $cmd"; done
for name in AZURE_SUBSCRIPTION_ID AZURE_RESOURCE_GROUP AZURE_LOCATION AZURE_ACR_NAME AZURE_ACR_LOGIN_SERVER AZURE_CONTAINER_APP_NAME AZURE_ENVIRONMENT_NAME AZURE_PULL_IDENTITY_NAME; do
  [[ -n ${!name:-} ]] || fail "Variável necessária: $name (outputs do bootstrap/environment)."
done
[[ $AZURE_SUBSCRIPTION_ID =~ ^[a-fA-F0-9-]{36}$ ]] || fail 'Assinatura inválida.'
[[ $AZURE_ACR_LOGIN_SERVER =~ ^[a-z0-9]+\.azurecr\.io$ ]] || fail 'Endpoint ACR inválido.'
[[ $(az account show --query id --output tsv) == "$AZURE_SUBSCRIPTION_ID" ]] || fail 'Assinatura ativa diferente da autorizada.'
[[ $(az acr show --name "$AZURE_ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query loginServer --output tsv) == "$AZURE_ACR_LOGIN_SERVER" ]] || fail 'ACR não pertence ao resource group configurado.'
app_id="/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$AZURE_RESOURCE_GROUP/providers/Microsoft.App/containerApps/$AZURE_CONTAINER_APP_NAME"
registry_login() {
  local token
  token=$(az acr login --name "$AZURE_ACR_NAME" --expose-token --query accessToken --output tsv)
  [[ -n $token ]] || fail 'Não foi possível obter token temporário ACR.'
  printf '%s' "$token" | docker login "$AZURE_ACR_LOGIN_SERVER" --username 00000000-0000-0000-0000-000000000000 --password-stdin
  unset token
}
trap 'docker logout "$AZURE_ACR_LOGIN_SERVER" >/dev/null 2>&1 || true' EXIT
registry_login

read_revision() {
  local revision=$1 destination=$2
  [[ $revision =~ ^[a-z0-9-]+$ ]] || fail 'Nome de revisão ACA inválido.'
  az rest --method GET --url "https://management.azure.com${app_id}/revisions/${revision}?api-version=2025-07-01" --output json > "$destination"
}

# Prova observável de Single-mode; não depende de latestReadyRevisionName,
# omitido pelo ambiente Express. O digest, não o slot "--latest", é a identidade.
read_serving_revision() {
  local revision=$1 app_file=$2 revision_file=$3
  az resource show --ids "$app_id" --api-version 2025-07-01 --output json > "$app_file"
  read_revision "$revision" "$revision_file"
  serving=false
  if jq -e --arg revision "$revision" --arg image "$image" '
    .properties.provisioningState == "Succeeded" and .properties.latestRevisionName == $revision and
    .properties.configuration.activeRevisionsMode == "Single" and
    .properties.configuration.ingress.allowInsecure == false and .properties.configuration.ingress.targetPort == 8080 and
    (.properties.template.containers | length) == 1 and .properties.template.containers[0].image == $image
  ' "$app_file" >/dev/null && jq -e --arg revision "$revision" --arg image "$image" '
    .name == $revision and .properties.active == true and .properties.provisioningState == "Provisioned" and
    .properties.trafficWeight == 100 and (.properties.template.containers | length) == 1 and
    .properties.template.containers[0].image == $image
  ' "$revision_file" >/dev/null; then
    serving=true
  fi
}

capture_active_revision() {
  local prefix=$1 destination=$2 next page revisions='[]' candidate
  active_revision=''
  rm -f -- "$destination"
  az resource show --ids "$app_id" --api-version 2025-07-01 --output json > "$evidence/$prefix-app.json"
  next="https://management.azure.com${app_id}/revisions?api-version=2025-07-01"
  while [[ -n $next ]]; do
    [[ $next == "https://management.azure.com${app_id}/revisions?"* ]] || fail 'Link de paginação de revisões inesperado.'
    page=$(az rest --method GET --url "$next" --output json)
    jq -e '.value | type == "array"' <<<"$page" >/dev/null || fail 'Resposta de revisões inválida.'
    revisions=$(jq -nc --argjson existing "$revisions" --argjson page "$page" '$existing + $page.value')
    next=$(jq -r '.nextLink // empty' <<<"$page")
  done
  printf '%s\n' "$revisions" > "$evidence/$prefix-revisions.json"
  if jq -e '.properties.configuration.activeRevisionsMode == "Single"' "$evidence/$prefix-app.json" >/dev/null &&
    jq -e '[.[] | select(.properties.active == true)] as $active |
      ($active | length) == 1 and $active[0].properties.provisioningState == "Provisioned" and
      $active[0].properties.trafficWeight == 100' <<<"$revisions" >/dev/null; then
    candidate=$(jq -er '.[] | select(.properties.active == true) | .name' <<<"$revisions")
    read_revision "$candidate" "$destination"
    if jq -e --arg revision "$candidate" '.name == $revision and .properties.active == true and
      .properties.provisioningState == "Provisioned" and .properties.trafficWeight == 100 and
      (.properties.template.containers | length) == 1' "$destination" >/dev/null; then
      active_revision=$candidate
    else
      rm -f -- "$destination"
    fi
  fi
}

inspect_registry_image() {
  local current=$digest depth path
  for ((depth=0; depth<=4; depth++)); do
    path="$evidence/registry-manifest${depth:+-$depth}.json"
    docker manifest inspect "$AZURE_ACR_LOGIN_SERVER/cloudcost@$current" > "$path"
    if jq -e '.schemaVersion == 2 and (.mediaType == "application/vnd.oci.image.manifest.v1+json" or .mediaType == "application/vnd.docker.distribution.manifest.v2+json") and (.config.digest | test("^sha256:[0-9a-f]{64}$"))' "$path" >/dev/null; then
      runtime_digest=$current
      runtime_config_digest=$(jq -er '.config.digest' "$path")
      return
    fi
    jq -e '
      [.manifests[] | select(.annotations["vnd.docker.reference.type"] != "attestation-manifest")] as $runtime |
      .schemaVersion == 2 and (.mediaType == "application/vnd.oci.image.index.v1+json" or .mediaType == "application/vnd.docker.distribution.manifest.list.v2+json") and
      ($runtime | length) == 1 and
      ($runtime[0].platform == null or ($runtime[0].platform.os == "linux" and $runtime[0].platform.architecture == "amd64")) and
      ($runtime[0].digest | test("^sha256:[0-9a-f]{64}$")) and
      all(.manifests[]; if .annotations["vnd.docker.reference.type"] == "attestation-manifest" then
        .platform.os == "unknown" and .platform.architecture == "unknown" and .annotations["vnd.docker.reference.digest"] == $runtime[0].digest
        else .digest == $runtime[0].digest end)
    ' "$path" >/dev/null || fail 'Índice remoto ambíguo ou attestation não associada à imagem executável.'
    current=$(jq -er '.manifests[] | select(.annotations["vnd.docker.reference.type"] != "attestation-manifest") | .digest' "$path")
  done
  fail 'Índice remoto excessivamente aninhado.'
}

case "$operation" in
  deploy)
    [[ $# == 4 && $1 =~ ^sha256:[0-9a-f]{64}$ && $2 =~ ^sha256:[0-9a-f]{64}$ && $3 =~ ^[0-9a-f]{40}$ && $4 =~ ^[1-9][0-9]*$ ]] || fail 'deploy exige Loaded Image ID, config digest, commit SHA e CI_RUN_ID aprovados.'
    loaded_image_id=$1 config_digest=$2 source_sha=$3 source_run=$4
    jq -e --arg id "$loaded_image_id" --arg config "$config_digest" --arg sha "$source_sha" '.loaded_image_id == $id and .config_digest == $config and .source_sha == $sha and (.source_image_id | test("^sha256:[0-9a-f]{64}$"))' "$evidence/prepared-image.json" >/dev/null || fail 'Metadados preparados não correspondem à entrega.'
    source_image_id=$(jq -er '.source_image_id' "$evidence/prepared-image.json")
    docker image inspect "$loaded_image_id" | jq -e --arg id "$loaded_image_id" --arg sha "$source_sha" --slurpfile prepared "$evidence/prepared-image.json" 'length == 1 and .[0].Id == $id and .[0].RootFS.Layers == $prepared[0].rootfs_diff_ids and .[0].Config.Labels["org.opencontainers.image.revision"] == $sha' >/dev/null || fail 'Imagem preparada não corresponde ao CI.'
    tag="sha-$source_sha-run-$source_run"
    reference="$AZURE_ACR_LOGIN_SERVER/cloudcost:$tag"
    docker tag "$loaded_image_id" "$reference"
    docker push "$reference" | tee "$evidence/docker-push.txt"
    digest=$(az acr repository show --name "$AZURE_ACR_NAME" --image "cloudcost:$tag" --query digest --output tsv)
    [[ $digest =~ ^sha256:[0-9a-f]{64}$ ]] || fail 'ACR não retornou digest válido.'
    image="$AZURE_ACR_LOGIN_SERVER/cloudcost@$digest"
    expected_descriptor=$(jq -r 'if .loaded_image_id != .config_digest then .loaded_descriptor_digest // empty else empty end' "$evidence/prepared-image.json")
    [[ -z $expected_descriptor || $digest == "$expected_descriptor" ]] || fail 'Digest remoto difere do descriptor carregado e validado.'
    inspect_registry_image
    [[ $runtime_config_digest == "$config_digest" ]] || fail 'Config digest remoto difere dos bytes aprovados.'
    expected_runtime=$(jq -r '.loaded_runtime_manifest_digest // empty' "$evidence/prepared-image.json")
    [[ -z $expected_descriptor || -z $expected_runtime || $runtime_digest == "$expected_runtime" ]] || fail 'Manifesto executável remoto difere do archive validado.'
    ;;
  rollback)
    [[ $# == 1 ]] || fail 'rollback exige referência ACR/cloudcost@sha256 completa de uma entrega anterior aprovada.'
    image=$1
    [[ $image == "$AZURE_ACR_LOGIN_SERVER/cloudcost@"* ]] || fail 'Rollback restrito ao repositório cloudcost deste ACR.'
    digest=${image##*@}
    [[ $digest =~ ^sha256:[0-9a-f]{64}$ ]] || fail 'Rollback por tag é proibido.'
    docker pull "$image" | tee "$evidence/docker-pull.txt"
    loaded_image_id=$(docker image inspect "$image" --format '{{.Id}}')
    [[ $loaded_image_id =~ ^sha256:[0-9a-f]{64}$ ]] || fail 'Imagem de rollback sem ID imutável.'
    source_image_id=''
    inspect_registry_image
    config_digest=$runtime_config_digest
    source_sha=$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')
    [[ $source_sha =~ ^[0-9a-f]{40}$ ]] || fail 'Imagem de rollback sem commit rastreável.'
    source_run='rollback-operador'
    ;;
  rescan)
    [[ $# == 0 ]] || fail 'rescan não aceita imagem arbitrária; usa o digest implantado.'
    capture_active_revision deployed "$evidence/ready-revision.json"
    [[ -n $active_revision ]] || fail 'Rescan exige exatamente uma revisão ativa, Provisioned e com 100% do tráfego em Single-mode.'
    image=$(jq -er '.properties.template.containers | select(length == 1) | .[0].image' "$evidence/ready-revision.json")
    [[ $image == "$AZURE_ACR_LOGIN_SERVER/cloudcost@"* && ${image##*@} =~ ^sha256:[0-9a-f]{64}$ ]] || fail 'Revisão ativa não está fixada ao digest privado esperado.'
    printf '%s\n' "$image" > "$evidence/rescanned-image.txt"
    bash "$root/scripts/security-checks.sh" --rescan "$image"
    capture_active_revision rescan-after "$evidence/rescanned-revision-after.json"
    [[ -n $active_revision ]] || fail 'Roteamento mudou durante o rescan.'
    jq -e --arg image "$image" '.properties.template.containers[0].image == $image' "$evidence/rescanned-revision-after.json" >/dev/null || fail 'Imagem ativa mudou durante o rescan; relatório não comprova o novo digest.'
    exit 0
    ;;
  *) fail "Operação desconhecida: $operation" ;;
esac

existing=$(az resource list --resource-group "$AZURE_RESOURCE_GROUP" --resource-type Microsoft.App/containerApps --query "[?name=='$AZURE_CONTAINER_APP_NAME'].id" --output tsv)
if [[ -n $existing ]]; then
  capture_active_revision previous "$evidence/previous-ready-revision.json"
fi
jq -n --arg image "$image" --arg source "$source_image_id" --arg loaded "$loaded_image_id" --arg config "$config_digest" --arg runtime "$runtime_digest" --arg sha "$source_sha" --arg run "$source_run" --arg operation "$operation" '{operation:$operation,image:$image,source_image_id:(if $source == "" then null else $source end),loaded_image_id:$loaded,config_digest:$config,runtime_manifest_digest:$runtime,source_sha:$sha,source_run_id:$run}' > "$evidence/release.json"
az deployment group create --subscription "$AZURE_SUBSCRIPTION_ID" --resource-group "$AZURE_RESOURCE_GROUP" --name "cloudcost-app-${GITHUB_RUN_ID:-$(date -u +%Y%m%d%H%M%S)}" --mode Incremental --template-file "$root/infra/azure/main.bicep" --parameters "location=$AZURE_LOCATION" "registryName=$AZURE_ACR_NAME" "environmentName=$AZURE_ENVIRONMENT_NAME" "pullIdentityName=$AZURE_PULL_IDENTITY_NAME" "containerAppName=$AZURE_CONTAINER_APP_NAME" "imageDigest=$digest" "sourceRevision=$source_sha" --output json > "$evidence/deployment.json"
endpoint=$(jq -er '.properties.outputs.endpoint.value' "$evidence/deployment.json")
[[ $endpoint =~ ^https://[a-z0-9.-]+\.azurecontainerapps\.io$ ]] || fail 'Endpoint HTTPS ACA inesperado.'
requested_revision=$(jq -er '.properties.outputs.revisionName.value' "$evidence/deployment.json")
[[ $requested_revision =~ ^[a-z0-9-]+$ ]] || fail 'Deployment não retornou a revisão solicitada.'
for ((attempt=0; attempt<60; attempt++)); do
  read_serving_revision "$requested_revision" "$evidence/deployed-app.json" "$evidence/ready-revision.json"
  if $serving; then break; fi
  sleep 10
done
$serving || fail 'Revisão solicitada não comprovou estado Provisioned, tráfego 100% e digest exato em 60 consultas com intervalo de 10s; smoke de outra revisão não seria prova de entrega.'
curl --fail --silent --show-error --proto '=https' --tlsv1.2 --connect-timeout 10 --max-time 20 --retry 12 --retry-all-errors --retry-delay 5 "$endpoint/healthz" > "$evidence/healthz.json"
jq -e '. == {status:"ok"}' "$evidence/healthz.json" >/dev/null || fail 'Healthcheck HTTPS inválido.'
curl --fail --silent --show-error --proto '=https' --tlsv1.2 --connect-timeout 10 --max-time 20 --header 'Content-Type: application/json' --data '{"instances":1,"hours_per_month":720,"hourly_rate":0.1,"storage_gb":100,"storage_rate":0.1,"egress_gb":50,"egress_rate":0.1}' "$endpoint/api/estimate" > "$evidence/estimate.json"
jq -e '.compute == 72 and .storage == 10 and .egress == 5 and .total == 87 and .currency == "USD"' "$evidence/estimate.json" >/dev/null || fail 'Contrato do estimador HTTPS inválido.'
# O smoke acorda réplicas em scale-to-zero; releia o estado efetivo para detectar
# atualização concorrente, inclusive quando Express reutiliza o nome "--latest".
read_serving_revision "$requested_revision" "$evidence/post-smoke-app.json" "$evidence/served-revision.json"
$serving || fail 'App, roteamento ou digest mudou durante o smoke HTTPS.'
jq -n --arg endpoint "$endpoint" --arg image "$image" --arg revision "$requested_revision" '{endpoint:$endpoint,image:$image,revision:$revision,smoke:"passed"}' > "$evidence/endpoint.json"
printf 'Endpoint: %s\nImagem: %s\n' "$endpoint" "$image"
if [[ -n ${GITHUB_OUTPUT:-} ]]; then printf 'endpoint=%s\nimage=%s\n' "$endpoint" "$image" >> "$GITHUB_OUTPUT"; fi
