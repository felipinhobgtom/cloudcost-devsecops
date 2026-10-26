#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

fail() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }
usage() {
  printf '%s\n' 'Uso: azure-bootstrap.sh --subscription UUID --resource-group NOME --location REGIAO --repository OWNER/REPO --accept-costs [--allow-no-reviewers]'
}
subscription='' resource_group='' location='' repository='' accept_costs=false allow_no_reviewers=false
while (($#)); do
  case "$1" in
    --subscription|--resource-group|--location|--repository)
      (($# >= 2)) || fail "Falta valor para $1"
      case "$1" in
        --subscription) subscription=$2 ;;
        --resource-group) resource_group=$2 ;;
        --location) location=$2 ;;
        --repository) repository=$2 ;;
      esac
      shift 2 ;;
    --accept-costs) accept_costs=true; shift ;;
    --allow-no-reviewers) allow_no_reviewers=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage; fail "Argumento desconhecido: $1" ;;
  esac
done
[[ $subscription =~ ^[a-fA-F0-9-]{36}$ ]] || fail 'Informe o UUID da assinatura explicitamente.'
[[ $resource_group =~ ^[a-zA-Z0-9_-]{1,80}$ ]] || fail 'Use um RG exclusivo com nome alfanumérico, hífen ou underscore.'
[[ $location =~ ^[a-z0-9]+$ ]] || fail 'Informe a região Azure, por exemplo eastus.'
[[ $repository =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || fail 'Informe owner/repo.'
$accept_costs || fail 'Provisionamento cobrado exige --accept-costs; consulte docs/azure.md.'
for cmd in az gh jq python3; do command -v "$cmd" >/dev/null || fail "Pré-requisito ausente: $cmd"; done
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
account=$(az account show --output json)
jq -e --arg sub "$subscription" '.id == $sub and .state == "Enabled" and .environmentName == "AzureCloud"' <<<"$account" >/dev/null || fail 'A assinatura ativa não coincide, está desabilitada ou não é AzureCloud. Execute az account set antes.'
tenant=$(jq -er '.tenantId' <<<"$account")
printf 'Assinatura ativa: %s; tenant: %s; RG: %s; região: %s\n' "$subscription" "$tenant" "$resource_group" "$location"
gh auth status --hostname github.com
repo=$(gh api "repos/$repository")
jq -e '.permissions.admin == true and .default_branch == "main"' <<<"$repo" >/dev/null || fail 'Exige administrador do repositório e branch default main já publicada.'
repository=$(jq -er '.full_name' <<<"$repo")
oidc=$(gh api -H 'X-GitHub-Api-Version: 2026-03-10' "repos/$repository/actions/oidc/customization/sub")
jq -e '.use_default == true and ((.include_claim_keys // []) | length) == 0 and (.sub_claim_prefix | type == "string" and test("^repo:[A-Za-z0-9_.@/-]+$"))' <<<"$oidc" >/dev/null || fail 'Template OIDC customizado/prefixo ausente não suportado; não alterarei as claims do repositório.'
subject="$(jq -er '.sub_claim_prefix' <<<"$oidc"):environment:azure-production"
printf 'Subject OIDC autoritativo: %s\n' "$subject"

# Verifique o plano antes de criar recursos faturáveis. Não remover regras existentes.
environment_api="repos/$repository/environments/azure-production"
environments=$(gh api "repos/$repository/environments?per_page=100")
environment=$(jq -c '[.environments[] | select(.name == "azure-production")][0] // null' <<<"$environments")
if [[ $environment == null ]]; then
  environment=$(gh api --method PUT "$environment_api" --input - <<'JSON'
{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
JSON
  )
fi
jq -e '.deployment_branch_policy.custom_branch_policies == true and .deployment_branch_policy.protected_branches == false' <<<"$environment" >/dev/null || fail 'Em Settings > Environments > azure-production selecione Deployment branches and tags > Selected branches and tags.'
policies=$(gh api "$environment_api/deployment-branch-policies?per_page=100")
if [[ $(jq -r '.total_count' <<<"$policies") == 0 ]]; then
  gh api --method POST "$environment_api/deployment-branch-policies" -f name=main -f type=branch >/dev/null
else
  jq -e '.total_count == 1 and .branch_policies[0].name == "main" and .branch_policies[0].type == "branch"' <<<"$policies" >/dev/null || fail 'O environment deve permitir somente a branch main, sem regras adicionais nem tags.'
fi
if jq -e 'any(.protection_rules[]?; .type == "required_reviewers" and (.reviewers | length) > 0 and .prevent_self_review == true)' <<<"$environment" >/dev/null; then
  printf '%s\n' 'Environment tem required reviewers e prevenção de autoaprovação.'
else
  $allow_no_reviewers || fail 'Configure required reviewers + Prevent self-review no environment e execute novamente. Se o plano privado não permite isso, documente o risco e use --allow-no-reviewers conscientemente.'
  printf '%s\n' 'AVISO: aprovação independente não verificada. Dispatch manual NÃO equivale a required reviewers.' >&2
fi
for provider in Microsoft.App Microsoft.ContainerRegistry Microsoft.ManagedIdentity; do
  [[ $(az provider show --namespace "$provider" --query registrationState --output tsv) == Registered ]] || fail "Provider $provider não registrado. Um administrador da assinatura deve registrá-lo antes (docs/azure.md)."
done

rg_id="/subscriptions/$subscription/resourceGroups/$resource_group"
if [[ $(az group exists --name "$resource_group" --subscription "$subscription" --output tsv) == true ]]; then
  group=$(az group show --name "$resource_group" --subscription "$subscription" --output json)
  jq -e --arg repo "$repository" --arg location "$location" '.tags.project == "CloudCost" and .tags.repository == $repo and .tags.managedBy == "cloudcost-bootstrap" and .location == $location' <<<"$group" >/dev/null || fail 'Recuso reutilizar RG sem as tags exclusivas CloudCost/repository/managedBy ou de outra região.'
else
  az group create --name "$resource_group" --location "$location" --subscription "$subscription" --tags project=CloudCost "repository=$repository" managedBy=cloudcost-bootstrap --output none
fi

# Sem create-for-rbac, client secret, senha de registro ou arquivo de credenciais.
app_name="cloudcost-github-$resource_group-${subscription:0:8}"
marker="cloudcost:$repository:$rg_id"
apps=$(az ad app list --display-name "$app_name" --output json)
apps=$(jq -c --arg name "$app_name" '[.[] | select(.displayName == $name)]' <<<"$apps")
case $(jq 'length' <<<"$apps") in
  0) app_body=$(jq -nc --arg name "$app_name" --arg marker "$marker" '{displayName:$name,signInAudience:"AzureADMyOrg",notes:$marker}')
     app=$(az rest --method POST --url https://graph.microsoft.com/v1.0/applications --body "$app_body" --output json) ;;
  1) app=$(jq -c '.[0]' <<<"$apps")
     jq -e --arg marker "$marker" '.notes == $marker and (.passwordCredentials | length) == 0 and (.keyCredentials | length) == 0' <<<"$app" >/dev/null || fail 'Aplicação Entra existente não pertence a este projeto ou contém credenciais persistentes.' ;;
  *) fail 'Mais de uma aplicação Entra corresponde ao nome; resolva a ambiguidade manualmente.' ;;
esac
client_id=$(jq -er '.appId' <<<"$app")
object_id=$(jq -er '.id' <<<"$app")
principals=$(az ad sp list --filter "appId eq '$client_id'" --output json)
case $(jq 'length' <<<"$principals") in
  0) principal_id=$(az ad sp create --id "$client_id" --query id --output tsv) ;;
  1) principal_id=$(jq -er '.[0].id' <<<"$principals") ;;
  *) fail 'Service principal ambíguo.' ;;
esac
federation=$(az ad app federated-credential list --id "$object_id" --output json)
parameters=$(jq -nc --arg subject "$subject" '{name:"github-azure-production",issuer:"https://token.actions.githubusercontent.com",subject:$subject,audiences:["api://AzureADTokenExchange"]}')
if [[ $(jq 'length' <<<"$federation") == 0 ]]; then
  az ad app federated-credential create --id "$object_id" --parameters "$parameters" --output none
else
  jq -e --arg subject "$subject" 'length == 1 and .[0].name == "github-azure-production" and .[0].issuer == "https://token.actions.githubusercontent.com" and .[0].subject == $subject and .[0].audiences == ["api://AzureADTokenExchange"]' <<<"$federation" >/dev/null || fail 'Federação existente divergente; não ampliarei confiança automaticamente.'
fi

outputs=$(az deployment group create --subscription "$subscription" --resource-group "$resource_group" --name cloudcost-foundation --mode Incremental --template-file "$root/infra/azure/foundation.bicep" --parameters "location=$location" "repository=$repository" --query properties.outputs --output json)
registry_id=$(jq -er '.registryId.value' <<<"$outputs")
assign_role() {
  local scope=$1 role=$2 assignment
  assignment=$(python3 - "$scope" "$principal_id" "$role" <<'PY'
import sys, uuid
print(uuid.uuid5(uuid.NAMESPACE_URL, "|".join(sys.argv[1:]).lower()))
PY
  )
  az role assignment create --name "$assignment" --assignee-object-id "$principal_id" --assignee-principal-type ServicePrincipal --role "$role" --scope "$scope" --output none
}
assign_role "$rg_id" b24988ac-6180-42a0-ab88-20f7382dd24c
assign_role "$registry_id" 8311e382-0749-4cb8-b61a-304f252e45ec
az group update --name "$resource_group" --subscription "$subscription" --set "tags.oidcClientId=$client_id" "tags.oidcObjectId=$object_id" --output none

set_var() { gh variable set "$1" --repo "$repository" --env azure-production --body "$2"; }
set_var AZURE_CLIENT_ID "$client_id"
set_var AZURE_TENANT_ID "$tenant"
set_var AZURE_SUBSCRIPTION_ID "$subscription"
set_var AZURE_RESOURCE_GROUP "$resource_group"
set_var AZURE_LOCATION "$(jq -er '.location.value' <<<"$outputs")"
set_var AZURE_ACR_NAME "$(jq -er '.registryName.value' <<<"$outputs")"
set_var AZURE_ACR_LOGIN_SERVER "$(jq -er '.registryLoginServer.value' <<<"$outputs")"
set_var AZURE_CONTAINER_APP_NAME "$(jq -er '.containerAppName.value' <<<"$outputs")"
set_var AZURE_ENVIRONMENT_NAME "$(jq -er '.environmentName.value' <<<"$outputs")"
set_var AZURE_PULL_IDENTITY_NAME "$(jq -er '.pullIdentityName.value' <<<"$outputs")"
printf '%s\n' 'Fundação e federação configuradas com outputs reais. Nenhum app foi criado nem imagem construída.'
printf '%s\n' 'Próximo passo: push main, aguardar CloudCost CI/security-gate e executar deploy-azure.yml com run_id aprovado.'
