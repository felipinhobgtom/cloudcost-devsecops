# Azure: infraestrutura e entrega por digest

Este guia descreve a execução real, não certifica que o provisionamento ocorreu. A comprovação é o run de entrega concluído, o digest no recurso Azure e o smoke HTTPS arquivado. `foundation.bicep` não cria aplicação de exemplo; o primeiro app só nasce depois de existir a imagem privada aprovada. CloudCost é um estimador Go stateless, não um consumidor de IA.

## Arquitetura e limites

- `infra/azure/foundation.bicep`: ACR **Basic**, admin e pull anônimo desabilitados; environment Azure Container Apps (ACA) com perfil **Consumption**; identidade gerenciada de pull; `AcrPull` restrito ao ACR. Não cria banco, disco persistente, VNet, Private Link ou workspace Log Analytics.
- `infra/azure/main.bicep` + `app.bicep`: app com imagem `ACR/cloudcost@sha256:…`, 0,25 vCPU, 0,5 GiB, mínimo zero e máximo duas réplicas. Ingress externo HTTPS no domínio padrão `azurecontainerapps.io`, `allowInsecure: false`, porta de destino 8080 e probes HTTP `/healthz`. A imagem preserva o usuário `65532:65532` e o executável `/cloudcost`.
- ACR **privado significa acesso autenticado às imagens**, não rede privada: o endpoint de Basic é público. A plataforma faz pull usando a identidade gerenciada com `AcrPull` restrito a esse ACR. O ambiente Express efetivamente provisionado recusou `ManagedIdentitySettings` com `ExpressEnvironmentFeatureNotSupported`; por isso `configuration.identitySettings` não é declarado. **Não há isolamento do token em relação ao processo por `lifecycle: None` neste ambiente:** a identidade pode estar disponível à aplicação. Uma eventual execução de código comprometido pode usar suas permissões de pull; o escopo restrito ao ACR limita, mas não elimina, esse risco. Não foi criado ambiente mais caro, VNet ou serviço adicional para contornar a limitação.
- A fundação administra RBAC; a entrega do app **não** cria role assignments. GitHub usa OIDC, sem `AZURE_CREDENTIALS`, client secret, senha do ACR ou PAT armazenado no workflow.
- `activeRevisionsMode: Single` envia tráfego à revisão pronta mais recente. Escalar a zero pode introduzir cold start. Máximo de réplicas limita capacidade, **não** impõe teto financeiro ou proteção global contra abuso.

O ambiente deixa a exportação de logs **não configurada** (sem bloco `appLogsConfiguration` e sem workspace): não há retenção/pesquisa centralizada de logs de aplicação em Log Analytics. O serviço recusou o literal `destination: 'none'` durante o preflight, embora a referência de schema o mencione; omitir a configuração evita depender desse valor. Evidências Actions, Azure Activity Log de gerenciamento e, quando há réplica ativa, diagnóstico/log stream da plataforma têm funções distintas. Não anunciar monitoramento centralizado ou alertas que não foram configurados. Ativar exportação/retention exige decisão de custo e alteração explícita da IaC.

A regra `concurrentRequests: 20` é um **gatilho de escala**, não rate limit. Sem gateway/WAF neste desenho mínimo, não há quota distribuída por cliente; limites HTTP locais da aplicação não viram limite global com duas réplicas. A API é pública e calcula estimativas a partir dos valores fornecidos, sem consultar contas de nuvem. Isso não implica que a identidade gerenciada esteja inacessível ao processo. Não enviar dados pessoais ou segredos nas estimativas.

ACA administra o host e não oferece equivalência automática às opções Docker Compose `read_only`, `cap_drop`, `pids_limit`, `no-new-privileges` e isolamento de rede local. Não transportar essas alegações do sandbox para a nuvem. CPU/memória, imagem não root, HTTPS, identidade e probes estão declarados na IaC; restrições adicionais do runtime precisam ser comprovadas na plataforma, não inferidas.

## Pré-requisitos reais e autorização

1. Bash, Azure CLI, GitHub CLI (`gh`), `jq`, Python **3.11+**, Docker Engine/CLI e `curl`. Azure CLI pode ser executada em contêiner oficial, mas Docker deve operar no host. O script usa `az acr login --expose-token` e entrega o token temporário a `docker login --password-stdin`, sem depender de Docker dentro da imagem Azure CLI. Monte o checkout no mesmo caminho absoluto se usar um wrapper `az` em Docker.
2. Compilador **Bicep v0.48.1**, versão confirmada na [release oficial](https://github.com/Azure/bicep/releases/tag/v0.48.1). Instalação: `az bicep install --version v0.48.1`. Os workflows de entrega fixam essa versão.
3. Assinatura Azure ativa, região permitida por Azure Policy e quota/capacidade Consumption disponíveis. `eastus` é uma sugestão inicial, **não um requisito nem região garantida**. Nesta preparação a política da assinatura recusou East US; a região escolhida para a execução autorizada é **`southcentralus`**. Isso não significa que o deployment já concluiu.
4. Permissão para criar o RG dedicado, ou um RG previamente criado pelo administrador com tags `project=CloudCost`, `repository=felipinhobgtom/cloudcost-devsecops`, `managedBy=cloudcost-bootstrap`. Para a fundação: Contributor e permissão `Microsoft.Authorization/roleAssignments/write` **no RG do projeto** (por exemplo Role Based Access Control Administrator nesse RG). Não conceder Owner de assinatura ao CI.
5. No Entra, permissão para registrar aplicações/service principals e gerenciar a própria federação. O padrão do tenant pode permitir registro por usuários; se bloqueado, um administrador deve conceder os direitos adequados, como Application Developer. Permissões Azure RBAC não substituem permissões de diretório. O bootstrap cria a aplicação pelo Microsoft Graph, sem credencial persistente.
6. Repositório privado já publicado, branch default `main`, Actions habilitado, permissões administrativas para environment e variables. Sessões `az login` e `gh auth login` do operador não são copiadas para o repositório.
7. Aprovar o custo/região **antes** do bootstrap; `--accept-costs` é obrigatório. ACR Basic continua cobrado mesmo quando ACA escala a zero. Budget é alerta, não limite rígido.

Um administrador registra os providers se ainda não estiverem registrados; o bootstrap verifica e não solicita elevação automática:

```bash
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.ContainerRegistry --wait
az provider register --namespace Microsoft.ManagedIdentity --wait
```

### GitHub privado: proteção e limitações do plano

A [documentação GitHub de environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments) distingue:

- Environments/variables e deployment branch policies em repositórios privados exigem plano compatível (Pro, Team ou Enterprise); GitHub Free privado não oferece essas proteções. Se a API negar acesso, **parar**: usar plano compatível/solução aprovada, não remover o environment nem transformar falha em sucesso.
- Required reviewers/wait timers em repositórios privados não estão disponíveis nos planos Free/Pro/Team; conferir a disponibilidade Enterprise. **Dispatch manual não é aprovação independente.**
- Onde disponível, antes do provisionamento: **Settings → Environments → azure-production → Required reviewers**, escolher pessoa/equipe com acesso ao repositório, habilitar **Prevent self-review** e salvar. Em **Deployment branches and tags**, escolher **Selected branches and tags**, apenas a branch `main`, nenhuma tag. O bootstrap cria environment/policy se ausentes, mas não escolhe revisores por você nem apaga regras existentes para enfraquecê-las.
- Por padrão o bootstrap exige reviewer configurado e prevenção de autoaprovação. Para a demonstração com mantenedor único/plano sem esse recurso, `--allow-no-reviewers` reconhece explicitamente a ausência. Registrar isso como **aprovação independente não implementada**, não como controle atendido. Branch `main`, origem CI e dispatch continuam obrigatórios.
- Recomenda-se proteger `main` exigindo `security-gate` e revisão de mudanças em workflows/IaC. A configuração do repositório depende do plano e de administrador; um arquivo YAML não prova branch protection habilitada.

O subject OIDC usa o environment, não contém a branch. Por isso a restrição do environment a `main` é parte da fronteira de confiança. Administradores capazes de modificar workflows/environment/RBAC continuam privilegiados.

## Bootstrap da fundação e da federação

A partir da raiz do checkout, selecione a assinatura sem colocar identificadores reais em arquivos versionados:

```bash
az login
az account list --output table
read -r -p 'UUID da assinatura autorizada: ' AZURE_SUBSCRIPTION_ID
export AZURE_SUBSCRIPTION_ID
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az account show --query '{name:name,id:id,tenant:tenantId,state:state}' --output table
gh auth login --hostname github.com
gh auth status
az bicep install --version v0.48.1

./scripts/azure-bootstrap.sh \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --resource-group rg-cloudcost-devsecops \
  --location southcentralus \
  --repository felipinhobgtom/cloudcost-devsecops \
  --accept-costs
```

Se a ausência de revisão independente foi explicitamente aceita, acrescente **`--allow-no-reviewers`** ao mesmo comando. Nunca acrescente a opção silenciosamente apenas para contornar uma falha. O script exige que a assinatura já selecionada coincida com o UUID informado, rejeita reutilização de RG sem as tags do projeto/região correta e pode ser reexecutado com os mesmos parâmetros após resolver um erro. Recursos parcialmente criados não são apagados automaticamente.

A federação criada obtém o prefixo autoritativo do GitHub, incluindo IDs imutáveis quando habilitados:

```text
issuer:   https://token.actions.githubusercontent.com
subject:  <sub_claim_prefix retornado pela API>:environment:azure-production
audience: api://AzureADTokenExchange
```

O bootstrap consulta `GET /repos/OWNER/REPO/actions/oidc/customization/sub` com `X-GitHub-Api-Version: 2026-03-10` e usa `sub_claim_prefix`. Repositórios novos podem emitir `repo:OWNER@OWNER_ID/REPO@REPO_ID`, não o antigo prefixo somente por nomes. A resposta real deste repositório habilita `use_immutable_subject`. O script exige o template padrão; se houver customização de claims, interrompe explicitamente sem alterar a configuração GitHub. Uma federação existente precisa coincidir exatamente com o subject atual, issuer e audience; não mantém confiança paralela em formatos antigos.

A aplicação Entra/service principal recebe **Contributor somente no RG** e **AcrPush somente no ACR**. A identidade gerenciada separada recebe **AcrPull somente no ACR**. O bootstrap é a operação administrativa responsável pelas atribuições; o job de deployment não tem direito de administrar RBAC. Contributor no RG ainda permite gerenciar os recursos do projeto: isso é um limite de escopo, não um papel customizado de privilégios mínimos por verbo.

O bootstrap grava **variables do environment** a partir dos IDs/outputs reais, não valores fictícios:

| Variable | Origem |
| --- | --- |
| `AZURE_CLIENT_ID` | Aplicação Entra de OIDC |
| `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | Contexto Azure conferido |
| `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION` | RG autorizado/output da fundação |
| `AZURE_ACR_NAME`, `AZURE_ACR_LOGIN_SERVER` | ACR realmente criado |
| `AZURE_CONTAINER_APP_NAME` | Nome determinístico definido pela fundação; o bootstrap não cria o app |
| `AZURE_ENVIRONMENT_NAME`, `AZURE_PULL_IDENTITY_NAME` | Outputs do Bicep |

`gh variable list --repo felipinhobgtom/cloudcost-devsecops --env azure-production` inspeciona as variables. São identificadores, não senhas. Não utilizar `az ad sp create-for-rbac --sdk-auth`, JSON de credenciais ou credenciais admin do ACR. Propagação de Entra/RBAC pode demorar; em falha de permissão, verificar atribuições/tenant e repetir conscientemente, sem conceder Owner por conveniência.

## Primeira entrega e entregas seguintes

O caminho autorizado é **push main → CloudCost CI → security-gate aprovado → artefato imutável → dispatch manual → ACR → digest → ACA → smoke HTTPS**. Não há build no bootstrap ou workflow Azure e não há imagem pública substituta.

```bash
gh run list --repo felipinhobgtom/cloudcost-devsecops \
  --workflow ci.yml --branch main --event push --status success
read -r -p 'ID do run CI aprovado: ' CI_RUN_ID
gh workflow run deploy-azure.yml --repo felipinhobgtom/cloudcost-devsecops \
  --ref main -f run_id="$CI_RUN_ID"
gh run list --repo felipinhobgtom/cloudcost-devsecops --workflow deploy-azure.yml
# Escolha o run de entrega retornado, não confunda com CI_RUN_ID:
read -r -p 'ID do run de entrega: ' DEPLOY_RUN_ID
gh run watch "$DEPLOY_RUN_ID" --repo felipinhobgtom/cloudcost-devsecops --exit-status
```

Quando configurado, o reviewer precisa aprovar o job `deploy` no environment. O workflow é somente manual para entrega; o evento `schedule` não entra nos jobs `source`/`deploy`.

`scripts/azure-source-run.sh` valida pela API o ID/path/name do workflow `.github/workflows/ci.yml` (`CloudCost CI`), mesmo repositório, `push` em `main`, ausência de fork, conclusão `success`, job `security-gate` aprovado e associação artefato/run/commit. Recusa PR, fork, run falho, schedule, workflow_dispatch como origem, artefato ausente/expirado/ambíguo e digest de artefato inválido. A validação é repetida após a espera pelo environment, conservando o mesmo artifact ID.

O artefato CI **`cloudcost-image`** contém na raiz `image.tar`, `image.tar.sha256`, `image-identity.json`, `summary.json` e relatórios da imagem. `download-artifact` está fixado por SHA, seleciona o **artifact ID e run ID exatos**, e falha em divergência do digest do artifact. O tar vai para diretório temporário fora do checkout. `prepare` confere status `passed`, checksum, caminhos/tipos seguros, Linux/amd64, não root, entrypoint e revision label. Valida o grafo OCI índice → manifesto executável → config/camadas; permite attestations somente quando associadas à única imagem executável. Verifica os hashes dos blobs e das camadas descomprimidas contra `rootfs.diff_ids`. Não extrai scripts nem executa a imagem.

**Image ID Docker, config digest e digest de manifesto/índice não são sinônimos.** Stores clássicos normalmente identificam a imagem pelo config, enquanto containerd pode retornar o digest de manifesto/índice. `prepare` registra `source_image_id`, `config_digest` e `loaded_image_id` separadamente. Depois de `docker load`, inspeciona a imagem e a reexporta temporariamente por ID para provar igualdade criptográfica do config e do rootfs com o archive aprovado, mesmo que o ID mude entre stores. Essa reexportação não faz build nem execução e o tar temporário é removido. Somente o `loaded_image_id` comprovado recebe a tag para push.

O push usa tag `sha-COMMIT-run-CI_RUN_ID`, mas **a implantação não usa essa tag**: o script resolve o digest remoto, percorre índice/manifesto até a imagem executável e compara o `config_digest` aprovado. Quando o store preserva o descriptor OCI, também exige igualdade dos digests raiz e executável. Só então chama Bicep com `ACR/cloudcost@sha256:…`. Tags podem mudar; o digest identifica os bytes.

A entrega aplica um único contrato observável de **Single-mode**, sem inferir o tipo do ambiente pela ausência de campos. Após obter a revisão solicitada do deployment, consulta no máximo 60 vezes, com intervalo de dez segundos mais o tempo das chamadas Azure, exigindo todas estas condições: app `Succeeded`, `latestRevisionName` igual à revisão solicitada, template desejado com o digest exato; e GET dessa revisão com `active: true`, `provisioningState: Provisioned`, `trafficWeight: 100` e template efetivo com o mesmo digest. Metadados faltantes ou divergentes não aprovam a entrega. O ambiente Express observado omite `latestReadyRevisionName`, portanto esse campo não é pré-requisito nem substituto da prova de roteamento.

O smoke HTTPS acorda a aplicação se estiver em scale-to-zero e exige `/healthz` com `{"status":"ok"}` e `/api/estimate` com total **87 USD**, validando TLS sem `-k`. **Depois** das requisições, o script relê app e revisão e repete todas as verificações de estado, tráfego e imagem para detectar alterações concorrentes. Não exige `runningState: Running`, health state fixo ou réplicas permanentemente ativas. No Express, o nome `--latest` pode ser reutilizado: a identidade da entrega e do rollback é o **digest registrado**, não o nome da revisão. Um app apenas com template desejado atualizado, ainda servindo outro digest, não passa.

### Evidências e inspeção independente

```bash
gh run download "$DEPLOY_RUN_ID" --repo felipinhobgtom/cloudcost-devsecops \
  --pattern 'azure-deployment-*' --dir azure-evidence/downloaded
```

Artefatos Actions `azure-source-RUN-ATTEMPT`, `azure-deployment-RUN-ATTEMPT` e `azure-rescan-RUN-ATTEMPT` retêm 14 dias. O artifact de imagem CI retém 7 dias; run antigo sem artifact não pode ser usado para primeira entrega. Relatórios de falha também são publicados: existência do artifact **não significa sucesso**.

Dentro da evidência de entrega: `source-run.json`, `source-jobs.json`, `source-artifact.json`, `prepared-image.json`, `loaded-image.json`, `registry-manifest-*.json`, `release.json`, `deployment.json`, `deployed-app.json`, `ready-revision.json`, `healthz.json`, `estimate.json`, `post-smoke-app.json`, `served-revision.json`, `endpoint.json` e `workflow-status.json`. Falhas podem não produzir os arquivos de etapas posteriores. `previous-app.json`/`previous-revisions.json` registram o estado anterior; quando havia uma única revisão ativa provisionada com 100% do tráfego, `previous-ready-revision.json` guarda seu template efetivo. Esse arquivo é um snapshot do digest daquele instante, inclusive se o slot `--latest` for reutilizado. Não confundir template desejado com imagem servida, nem inventar endpoint se o output não existir.

Para operações autorizadas locais, carregar somente as variables Azure do environment sem `eval`:

```bash
while IFS=$'\t' read -r name value; do
  export "$name=$value"
done < <(gh variable list --repo felipinhobgtom/cloudcost-devsecops \
  --env azure-production --json name,value \
  --jq '.[] | select(.name | startswith("AZURE_")) | [.name,.value] | @tsv')
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
APP_ID="/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$AZURE_RESOURCE_GROUP/providers/Microsoft.App/containerApps/$AZURE_CONTAINER_APP_NAME"
az resource show --ids "$APP_ID" --api-version 2025-07-01 \
  --query '{desiredImage:properties.template.containers[0].image,latestRevision:properties.latestRevisionName,mode:properties.configuration.activeRevisionsMode,fqdn:properties.configuration.ingress.fqdn,state:properties.provisioningState}'
az rest --method GET \
  --url "https://management.azure.com${APP_ID}/revisions?api-version=2025-07-01" \
  --query '{activeRevisions:value[?properties.active==`true`].{revision:name,image:properties.template.containers[0].image,state:properties.provisioningState,traffic:properties.trafficWeight},nextLink:nextLink}'
FQDN=$(az resource show --ids "$APP_ID" --api-version 2025-07-01 \
  --query properties.configuration.ingress.fqdn --output tsv)
curl --fail --proto '=https' "https://$FQDN/healthz"
curl --fail --proto '=https' -H 'Content-Type: application/json' \
  --data '{"instances":1,"hours_per_month":720,"hourly_rate":0.1,"storage_gb":100,"storage_rate":0.1,"egress_gb":50,"egress_rate":0.1}' \
  "https://$FQDN/api/estimate"
```

## Rescan e rollback

Às **05:47 UTC**, `rescan` lista as revisões efetivas, percorre a paginação e exige Single-mode com **exatamente uma revisão ativa, `Provisioned` e com 100% do tráfego**. Confirma essa revisão por GET e extrai a referência imutável do seu template, nunca do template desejado do app nem de `latestReadyRevisionName`. Após autenticar no ACR, passa essa referência a `scripts/security-checks.sh --rescan`. Se ela identifica um índice, o scanner resolve um único candidato **Linux/amd64**, recusando seleção ambígua, até obter o manifesto executável por digest.

**No rescan, Trivy e SBOM consultam diretamente o registry**, usando o mesmo digest de manifesto executável selecionado; Docker puxa esse mesmo digest para o DAST isolado no runner. Não há rebuild, deployment, exportação `image.tar` nem checksum de tar nesse modo. Isso é diferente do CI completo, que continua construindo uma vez, analisando e entregando seu archive original com checksum. O DAST não é uma análise agressiva no endpoint público nem uma varredura de toda a infraestrutura.

`manifest-resolution.json` conserva `requested_reference` (inclusive o digest pai do índice), `runtime_reference`, `runtime_manifest_digest`, `runtime_config_digest`, plataforma exigida e a cadeia de seleção com os manifestos de evidência. `image-identity.json`/`summary.json` registram `scan_source: registry` e `scan_reference` do manifesto executável. A autenticação do scanner usa arquivo temporário privado, modo `0600`, montado somente para leitura, com credenciais **apenas do registry selecionado**; não copia todas as credenciais Docker para o scanner nem as publica nos relatórios. Aliases de Docker Hub são canonicalizados; credential helpers não suportados falham de forma fechada, sem fallback silencioso. `registry-access.json` registra o escopo e o modo de autenticação, não os segredos.

Ao final, o wrapper Azure relê a seleção ativa e exige a mesma referência por digest solicitada inicialmente; mudança concorrente não é reportada como scan aprovado da nova imagem. O job reutiliza a identidade Contributor RG/AcrPush e continua sujeito ao environment, inclusive espera por reviewers quando configurados. Schedules podem atrasar no GitHub. App ausente, seleção ambígua, falha de autenticação/scanner ou estado/tráfego não comprovado falham explicitamente.

Para executar a mesma reanálise manualmente, após carregar variables e login conforme acima:

```bash
./scripts/azure-deploy.sh rescan
```

Uma falha de rescan exige avaliação/correção e novo push aprovado. Não faz rollback/deploy automático. O CI diário da fonte é uma verificação distinta e não substitui esta reanálise do digest ativo.

Rollback é operação administrativa explícita: obter a referência completa **de uma entrega anterior aprovada**, dos snapshots `release.json`/`previous-ready-revision.json`, conferir findings e conservar autorização/evidência. O nome `--latest` pode representar outro conteúdo posteriormente: usar sempre o digest gravado no snapshot, não uma consulta futura pelo nome. Não resolver uma tag antiga, confiar apenas no template desejado de `previous-app.json` ou usar imagem arbitrária no primeiro deploy.

```bash
read -r -p 'Referência completa ACR/cloudcost@sha256 da entrega aprovada: ' APPROVED_IMAGE
./scripts/azure-deploy.sh rollback "$APPROVED_IMAGE"
```

O script rejeita tags e outro registry/repositório, puxa pelo digest, confere revision label, reaplica `main.bicep` e usa a mesma prova de app/revisão ativa provisionada com 100% do tráfego e digest exato **antes e depois** do smoke HTTPS. Não recria roles/fundação. Essa execução local usa a sessão do operador e **não herda** aprovação do environment Actions; registrar autorização manual separadamente. Enquanto o artifact existir, também é possível executar o dispatch com o run CI anterior aprovado. Conservar os manifests no ACR: apagar a imagem impede rollback/restart por digest.

## Custo: estimar antes, acompanhar depois

Preços variam com região, moeda, contrato, data e tributos; nenhum valor ao vivo é inventado aqui. Consulte a [calculadora Azure](https://azure.microsoft.com/en-us/pricing/calculator/), [ACA Consumption](https://azure.microsoft.com/en-us/pricing/details/container-apps/), [ACR Basic](https://azure.microsoft.com/en-us/pricing/details/container-registry/) e [transferência de dados](https://azure.microsoft.com/en-us/pricing/details/bandwidth/). Registre na evidência a data/região/moeda e as tarifas realmente consultadas.

Base para uma estimativa transparente: ACR Basic pelos dias provisionados, armazenamento adicional ao incluído quando aplicável, transferência de saída, requests e segundos ativos de ACA. Uma réplica usa **0,25 vCPU e 0,5 GiB**; duas usam até **0,5 vCPU e 1 GiB** alocados. Calcular segundos ativos × recurso × tarifa, descontando franquias **aplicáveis à assinatura**, não presumindo gratuidade. A página oficial informa franquias mensais de Consumption, compartilhadas no escopo da assinatura. Carga, cold starts, permanência ativa e tráfego afetam o total; `minReplicas: 0` não zera o custo fixo do ACR.

Não são criados produtos de IA, banco, workspace pago, domínio próprio ou gateway. GitHub Actions privado também consome a franquia/minutos e armazenamento de artifacts do plano. Defina Budget/alertas em Cost Management com valor autorizado; não há orçamento fictício na IaC nem desligamento automático prometido.

## Remoção restrita ao projeto — não executada por estes scripts

A remoção é destrutiva e apaga o ACR, imagens e revisões deste projeto. Primeiro exportar a evidência necessária. O comando abaixo não remove assinatura nem RG de terceiros; exige conferir as tags e digitar o nome exato. Use somente o RG exclusivo criado no bootstrap:

```bash
(
set -e
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az group show --name "$AZURE_RESOURCE_GROUP" --query '{id:id,tags:tags}'
test "$(az group show --name "$AZURE_RESOURCE_GROUP" --query tags.project -o tsv)" = CloudCost
test "$(az group show --name "$AZURE_RESOURCE_GROUP" --query tags.repository -o tsv)" = felipinhobgtom/cloudcost-devsecops
test "$(az group show --name "$AZURE_RESOURCE_GROUP" --query tags.managedBy -o tsv)" = cloudcost-bootstrap
read -r -p 'Digite o nome do RG para confirmar remoção: ' CONFIRM_RG
if [ "$CONFIRM_RG" = "$AZURE_RESOURCE_GROUP" ] && [ -n "$CONFIRM_RG" ]; then
  az group delete --subscription "$AZURE_SUBSCRIPTION_ID" --name "$AZURE_RESOURCE_GROUP" --yes
fi
)
```

O subshell interrompe em qualquer verificação falha. A aplicação/federação Entra e environment GitHub existem fora do RG; um administrador deve desativar a federação e revisar a remoção da aplicação exata (`oidcClientId`/`oidcObjectId` nas tags do RG, anotar antes de excluir). Não apagar aplicações por nome genérico. Desabilitar o workflow Azure ao aposentar o ambiente evita rescans diários contra recursos removidos. Nenhum comando de cleanup é executado pelo bootstrap/deployment.

## Validação sem criar recursos

Não é necessário `az login` para compilar Bicep. A instalação inicial precisa de rede; depois o build dos módulos locais não consulta a assinatura:

```bash
az bicep install --version v0.48.1
mkdir -p reports/azure-validation
az bicep build --file infra/azure/foundation.bicep --outfile reports/azure-validation/foundation.json
az bicep build --file infra/azure/main.bicep --outfile reports/azure-validation/main.json
bash -n scripts/azure-bootstrap.sh scripts/azure-source-run.sh scripts/azure-deploy.sh
# Se actionlint estiver instalado, inclui o workflow de entrega:
actionlint .github/workflows/ci.yml .github/workflows/deploy-azure.yml
```

Compilação/lint não certifica permissão, quota, Azure Policy, propagação RBAC nem funcionamento do endpoint. `az deployment group what-if`/`validate` exigem autenticação e acesso ao RG; não chamar isso de teste offline. A verificação final deve registrar quais comandos efetivamente foram executados e seu resultado, sem converter ausência de execução em aprovação.

## Referências primárias do contrato

- [Schema ACA environment API 2025-07-01](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2025-07-01/managedenvironments) e [containerApps API 2025-07-01](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2025-07-01/containerapps).
- [Schema ACR API 2025-04-01](https://learn.microsoft.com/en-us/azure/templates/microsoft.containerregistry/2025-04-01/registries), [managed identity API 2024-11-30](https://learn.microsoft.com/en-us/azure/templates/microsoft.managedidentity/2024-11-30/userassignedidentities) e [roleAssignments API 2022-04-01](https://learn.microsoft.com/en-us/azure/templates/microsoft.authorization/2022-04-01/roleassignments).
- [Pull do ACR com identidade e ARM audience](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull) e [documentação de identidades gerenciadas](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity). Recursos de lifecycle descritos na documentação geral não são evidência de suporte no ambiente Express usado nesta entrega.
- [Visão geral de ambientes Express](https://learn.microsoft.com/en-us/azure/container-apps/express-overview) e [FAQ Express](https://learn.microsoft.com/en-us/azure/container-apps/express-faq): consultar a matriz de recursos e o modelo de cobrança Consumption desse ambiente; `workloadProfiles: Consumption` não comprova suporte a todos os recursos de outros tipos de ambiente.
- [GitHub OIDC no Azure](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure), [API environments](https://docs.github.com/en/rest/deployments/environments) e [API branch policies](https://docs.github.com/en/rest/deployments/branch-policies).
- [Microsoft Graph: criar aplicação e permissões](https://learn.microsoft.com/en-us/graph/api/application-post-applications?view=graph-rest-1.0), [federação CLI](https://learn.microsoft.com/en-us/cli/azure/ad/app/federated-credential) e [contêineres suportados pelo ACA](https://learn.microsoft.com/en-us/azure/container-apps/containers).
- [API Get Revision 2025-07-01](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/container-apps-revisions/get-revision?view=rest-resource-manager-containerapps-2025-07-01), [API OIDC GitHub](https://docs.github.com/en/rest/actions/oidc) e [subjects imutáveis GitHub](https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/).
- [Docker containerd image store](https://docs.docker.com/engine/storage/containerd/), [OCI descriptors](https://github.com/opencontainers/image-spec/blob/v1.1.1/descriptor.md) e [OCI image index](https://github.com/opencontainers/image-spec/blob/v1.1.1/image-index.md).
- [API List Revisions 2025-07-01](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/container-apps-revisions/list-revisions?view=rest-resource-manager-containerapps-2025-07-01): origem da seleção da revisão ativa para rescan e snapshot anterior ao deployment.
