#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
fail() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }
[[ $# == 1 && $1 =~ ^[1-9][0-9]*$ ]] || fail 'Uso: azure-source-run.sh CI_RUN_ID'
: "${GITHUB_REPOSITORY:?Informe GITHUB_REPOSITORY=owner/repo}"
[[ $GITHUB_REPOSITORY =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || fail 'Repositório inválido.'
for cmd in gh jq; do command -v "$cmd" >/dev/null || fail "Pré-requisito ausente: $cmd"; done
run_id=$1
evidence=${AZURE_EVIDENCE_DIR:-azure-evidence}
mkdir -p "$evidence"
workflow=$(gh api "repos/$GITHUB_REPOSITORY/actions/workflows/ci.yml")
jq -e '.path == ".github/workflows/ci.yml" and .name == "CloudCost CI" and .state == "active"' <<<"$workflow" >/dev/null || fail 'Workflow CI inesperado/inativo.'
workflow_id=$(jq -er '.id' <<<"$workflow")
gh api "repos/$GITHUB_REPOSITORY/actions/runs/$run_id" > "$evidence/source-run.json"
jq -e --arg repo "$GITHUB_REPOSITORY" --argjson workflow "$workflow_id" --argjson run "$run_id" '
  .id == $run and .workflow_id == $workflow and .path == ".github/workflows/ci.yml" and
  .repository.full_name == $repo and .head_repository.full_name == $repo and
  .head_repository.fork == false and .head_branch == "main" and .event == "push" and
  .status == "completed" and .conclusion == "success" and (.head_sha | test("^[0-9a-f]{40}$"))
' "$evidence/source-run.json" >/dev/null || fail 'Aceito somente CI deste repositório, push main, sem fork/PR, concluída com sucesso.'
source_sha=$(jq -er '.head_sha' "$evidence/source-run.json")
repo_id=$(jq -er '.repository.id' "$evidence/source-run.json")
gh api --paginate "repos/$GITHUB_REPOSITORY/actions/runs/$run_id/jobs?filter=latest&per_page=100" --jq '.jobs[]' | jq -s '.' > "$evidence/source-jobs.json"
jq -e 'any(.[]; .name == "security-gate" and .status == "completed" and .conclusion == "success")' "$evidence/source-jobs.json" >/dev/null || fail 'security-gate não foi aprovado.'
gh api --paginate "repos/$GITHUB_REPOSITORY/actions/runs/$run_id/artifacts?per_page=100" --jq '.artifacts[]' | jq -s '[.[] | select(.name == "cloudcost-image")]' > "$evidence/source-artifact.json"
jq -e --argjson run "$run_id" --argjson repo "$repo_id" --arg sha "$source_sha" '
  length == 1 and .[0].expired == false and .[0].size_in_bytes > 0 and
  .[0].workflow_run.id == $run and .[0].workflow_run.head_sha == $sha and
  .[0].workflow_run.head_branch == "main" and
  .[0].workflow_run.repository_id == $repo and .[0].workflow_run.head_repository_id == $repo and
  (.[0].digest | test("^sha256:[0-9a-f]{64}$"))
' "$evidence/source-artifact.json" >/dev/null || fail 'Artefato ausente, ambíguo, expirado ou não associado ao run/commit/repositório autorizado.'
artifact_id=$(jq -er '.[0].id' "$evidence/source-artifact.json")
printf 'source_sha=%s\nartifact_id=%s\nrun_id=%s\n' "$source_sha" "$artifact_id" "$run_id"
if [[ -n ${GITHUB_OUTPUT:-} ]]; then
  printf 'source_sha=%s\nartifact_id=%s\nrun_id=%s\n' "$source_sha" "$artifact_id" "$run_id" >> "$GITHUB_OUTPUT"
fi
