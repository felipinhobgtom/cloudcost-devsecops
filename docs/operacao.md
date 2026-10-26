# Operação do CloudCost

## Dois ambientes, responsabilidades distintas

- **Local:** Docker Compose em `http://127.0.0.1:8080`, para desenvolvimento, demonstração e smoke. Não é um endpoint público seguro.
- **Nuvem solicitada:** Azure Container Apps Consumption, imagem privada no Azure Container Registry (ACR), pull com identidade gerenciada e deployment GitHub OIDC. O ingress Azure termina HTTPS; o binário continua HTTP na porta interna 8080.

Infraestrutura escrita não significa infraestrutura provisionada. Consulte [evidências](evidencias.md) para resultados observados e [Azure](azure.md) para o contrato completo de bootstrap, variáveis, permissões e custos. Não há chamada de IA nem provisionamento cloud realizado pela própria calculadora.

## Demonstração local

Requisitos: Docker Engine ativo, Docker Compose v2 com suporte a `--wait`, porta local 8080 livre e acesso para obter a imagem builder. O caminho Docker não exige instalar Go no host. Para a suíte de segurança, veja requisitos/pins em [toolchain](../security/toolchain.md); ela também usa Go, Python 3 e Git.

Na raiz do repositório:

```sh
CLOUDCOST_IMAGE=cloudcost:local docker compose up --build -d --wait
docker compose ps
curl --fail --silent --show-error http://127.0.0.1:8080/healthz
```

O último comando deve retornar `{"status":"ok"}` quando saudável. Abra `http://127.0.0.1:8080` no navegador. Os preços são exemplos, não tarifas atuais da Azure ou de outro provedor. O exemplo da API:

```sh
curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  --data '{"instances":1,"hours_per_month":720,"hourly_rate":0.1,"storage_gb":100,"storage_rate":0.1,"egress_gb":50,"egress_rate":0.1}' \
  http://127.0.0.1:8080/api/estimate
```

Resultado esperado, independentemente da ordem das chaves: `{"compute":72,"storage":10,"egress":5,"total":87,"currency":"USD"}`. O cálculo usa decimais exatos, arredonda meio centavo para cima por categoria e soma as categorias arredondadas. Impostos, descontos, câmbio e regras comerciais do provedor não entram nessa estimativa.

### Diagnóstico sem ampliar privilégios

```sh
docker compose exec -T app /cloudcost healthcheck
docker compose logs --since=10m app
docker inspect "$(docker compose ps -q app)" \
  --format 'user={{.Config.User}} readOnly={{.HostConfig.ReadonlyRootfs}} caps={{json .HostConfig.CapDrop}} security={{json .HostConfig.SecurityOpt}} memory={{.HostConfig.Memory}} pids={{.HostConfig.PidsLimit}} ports={{json .NetworkSettings.Ports}}'
```

O Compose configura `65532:65532`, rootfs somente leitura, `cap_drop: ALL`, `no-new-privileges`, 128 MiB, 0,50 CPU, 64 PIDs e bind loopback. O processo não precisa escrever em disco. A imagem `scratch` não tem shell ou `curl`; use o subcomando do binário, em vez de instalar utilitários na imagem final. O estado `unhealthy` sinaliza falha, mas a política Docker `restart` não reinicia automaticamente um processo apenas por esse estado: investigue logs/saída/recursos.

Se `--wait` falhar, verifique daemon, conflito de porta, download de builder e saúde do processo. Não remova limites/cabeçalhos ou use modo privilegiado para esconder o problema. `PORT` configura o processo; alterar a porta interna exige alinhar mapeamento, probes e configurações de deployment, não apenas exportar uma variável no shell.

Parar a demonstração:

```sh
docker compose down
```

Não há banco/volume de dados da app. Os logs Docker têm rotação no Compose, mas isso não estabelece uma política completa de privacidade/retensão do host.

## Gates e relatórios

```sh
bash scripts/security-checks.sh
```

A entrada executa controles de código, segredos, configuração e imagem e DAST direcionado; consulte a [política](../security/POLICY.md). Resultados são separados em `reports/<UTC>-<id>/`; `reports/latest.json` aponta o estado/diretório da última execução. Relatórios não são versionados automaticamente e podem conter detalhes operacionais: revise antes de compartilhar.

A CI `CloudCost CI` libera o artefato **`cloudcost-image`** apenas após aprovação. Ele contém `image.tar`, `image-identity.json` e `summary.json`, usados para transportar a imagem examinada. A existência do arquivo não basta: valide o run, commit, resultado do gate e identidade do artefato. Não reconstrua uma imagem depois do exame e a apresente como a mesma release.

A identidade tem camadas distintas: `source_image_id` registra o identificador do Docker na origem, `config_digest` identifica a configuração da imagem e `loaded_image_id` registra o identificador após carregar o tar. Um ID Docker de origem pode representar um índice OCI, portanto esses valores não são intercambiáveis nem precisam ser textualmente iguais. O deployment valida a cadeia da configuração e do rootfs para vincular o conteúdo examinado ao carregado/publicado; o digest ACR identifica o manifesto da release.

## Release manual por digest

### 1. Preparar Azure uma vez

Leia [azure.md](azure.md) antes de executar. É necessário acesso à subscription autorizada, permissão para criar recursos/atribuir papéis, acesso de administração ao repositório e aceite de custos. Autentique-se pelo mecanismo oficial, nunca copiando credenciais para arquivos do projeto. `AZURE_SUBSCRIPTION_ID` deve conter o identificador real selecionado pelo responsável.

Nesta entrega com mantenedor único, o environment `azure-production` existe e permite `main`, mas **aprovação independente não está atestada**. O comando abaixo registra essa exceção explicitamente com `--allow-no-reviewers`; não a trate como proteção equivalente a revisores obrigatórios. Antes de operação com maior risco, providencie revisão independente e retire essa exceção.

```sh
az login
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
bash scripts/azure-bootstrap.sh \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --resource-group rg-cloudcost-devsecops \
  --location southcentralus \
  --repository felipinhobgtom/cloudcost-devsecops \
  --accept-costs \
  --allow-no-reviewers
```

`--accept-costs` é consentimento operacional, não estimativa de preço nem garantia de gratuidade. A região escolhida para esta subscription é `southcentralus`: a política de regiões permitidas bloqueia `eastus`. Em outra subscription, confirme a política e cotas antes de escolher. O bootstrap configura infraestrutura/identidades e variáveis reais do environment `azure-production`; revisão/aprovação depende do plano/configuração GitHub. Não contorne uma falha de RBAC ou aprovação criando senhas permanentes.

### 2. Selecionar e aprovar a imagem

No GitHub real, selecione um run de `CloudCost CI` da `main` revisada, com `security-gate` e todos os controles aprovados. Confira commit, relatórios, SBOM e artefato antes da promoção.

```sh
gh run list --workflow ci.yml --branch main --status success --limit 10
```

Copie o ID do run aprovado para `CI_RUN_ID`, sem escolher um run de PR/fork ou inferir aprovação a partir de um badge. Inicie o deployment:

```sh
gh workflow run deploy-azure.yml --ref main -f run_id="$CI_RUN_ID"
```

O workflow usa OIDC, baixa o artefato aprovado, carrega o tar, publica no ACR e implanta no Container Apps por digest **sem rebuild**. A identidade de deployment e a identidade gerenciada de pull são distintas. Não há usuário admin do ACR ou senha Azure a inserir no container.

### 3. Registrar e verificar o release

Acompanhe o run Azure e salve o artefato `azure-deployment-<run>-<attempt>`, incluindo `azure-evidence/deployment.json` e `endpoint.json`. Registre responsável, commit, run CI, `source_image_id`, `config_digest`, `loaded_image_id`, referência ACR com `@sha256:`, revisão anterior/nova e horário. Preserve a evidência da validação de configuração/rootfs; não trate um ID local como digest do manifesto ACR. A URL HTTPS deve vir dos outputs Azure reais; nunca deduza um hostname fictício.

Confirme pelo Azure que a imagem configurada no Container Apps contém o digest aprovado; teste `/healthz`, o exemplo de cálculo e cabeçalhos na URL HTTPS obtida. Cold start/escala a zero podem aumentar a latência. Se alguma etapa falhar, não registre release como concluída nem faça push manual de uma imagem não examinada para “consertar” o gate.

**Tag não é digest:** `sha-<commit>` ajuda a localizar o conteúdo, mas uma tag pode ser reatribuída. `@sha256:<digest>` fixa o conteúdo do manifesto. Digest não é assinatura de autoria nem prova de segurança; sua origem deve estar ligada ao run autorizado.

## Reproduzir uma imagem ACR localmente

É opcional para diagnóstico e não substitui o deployment Azure. Carregue `AZURE_ACR_NAME` e a referência integral do digest aprovado a partir da configuração/evidência real. O usuário Azure precisa de permissão de pull no registry; o `gh` login sozinho não dá acesso ao ACR.

```sh
az login
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az acr login --name "$AZURE_ACR_NAME"
```

Defina `CLOUDCOST_IMAGE` como a referência real completa, no formato `<registry>.azurecr.io/cloudcost@sha256:<digest>`, e exporte-a antes de **todos** os comandos Compose da sessão:

```sh
export CLOUDCOST_IMAGE
docker compose pull app
docker compose up -d --no-build --wait
```

Não use `--build`, `latest` ou uma tag mutável neste caminho. O Docker armazena autenticação no cliente/credential helper; não copie sua configuração para o Git, para a imagem ou para relatórios. Ao terminar, use `docker logout "$AZURE_ACR_LOGIN_SERVER"` se a sessão de registro não precisar permanecer ativa.

Para reexaminar esse mesmo conteúdo após autenticação:

```sh
bash scripts/security-checks.sh --rescan "$CLOUDCOST_IMAGE"
```

Esse comando puxa a referência, resolve a identidade e examina sem rebuild. O scan periódico da fonte/imagem corrente na CI não substitui o reexame do digest em produção. Para isso, [deploy-azure.yml](../.github/workflows/deploy-azure.yml) também configura o job `rescan` diariamente às 05:47 UTC: `azure-deploy.sh rescan` consulta e examina o digest implantado, **sem realizar deployment no evento agendado**. O agendamento não comprova execução; acompanhe falhas e relatórios. Esse job reutiliza a identidade OIDC com `Contributor` no grupo e `AcrPush` no ACR; não é uma identidade dedicada somente de leitura.

## Rollback

1. Identifique no inventário de releases um digest anterior aprovado, ainda disponível no ACR e considerado **não afetado** pelo incidente. Uma imagem antiga não é automaticamente segura.
2. Preserve a evidência da falha. Confirme que o problema não exige rotação de credenciais, ajuste de infraestrutura ou resposta a comprometimento.
3. Em sessão Azure autorizada, com as variáveis descritas em [azure.md](azure.md) carregadas, defina `PREVIOUS_IMAGE` com a referência integral por digest e execute:

```sh
bash scripts/azure-deploy.sh rollback "$PREVIOUS_IMAGE"
```

4. Verifique novamente digest/revisão efetiva, HTTPS, saúde, cálculo e cabeçalhos; registre responsável, motivo e resultado. Rollback reimplanta conteúdo conhecido, não desfaz acesso indevido ou vazamento já ocorrido.

Para reprodução local, exporte `CLOUDCOST_IMAGE="$PREVIOUS_IMAGE"` e repita `docker compose pull app` e `docker compose up -d --no-build --wait`. A app não persiste dados; não há migração de banco para reverter. Preserve código, imagem, SBOM e evidências de release para recuperação futura.

## Antes de exposicao externa

O destino Azure define ingress HTTPS gerenciado e domínio padrão. Isso reduz trabalho de certificados, mas não substitui a revisão operacional:

- Confirme provisionamento, URL, TLS e ausência de entrega de conteúdo sensível em HTTP. Use **HTTPS diretamente** para a API: um redirect de HTTP ocorre depois do primeiro pedido e não protege dados já enviados. O comportamento padrão do ingress Azure não demonstra atendimento integral ao ASVS sobre redirects de APIs.
- Verifique HSTS e política de domínio explicitamente; este projeto não reivindica HSTS apenas por usar HTTPS. Domínio personalizado/certificado próprio exigem configuração adicional.
- Confirme RBAC e federação restrita ao repo/environment autorizados; identidade de pull apenas `AcrPull`; admin do ACR desabilitado. Registry privado significa acesso autenticado, **não Private Link** ou isolamento de rede automaticamente.
- Compare controles realmente suportados no Container Apps com os do Compose. Não transporte uma afirmação de rootfs read-only/cap_drop/PIDs de Docker local para Azure sem evidência na API/plataforma.
- Defina responsáveis por disponibilidade, abuso/rate limiting, logs, alertas e novas CVEs. Limites de CPU/escala reduzem consumo, mas não garantem defesa contra DDoS nem teto de gastos.
- Revise retenção/acesso de logs e IPs, transparência e obrigações LGPD. Não habilite log de corpos/estimativas/segredos para facilitar diagnóstico.
- Aplique orçamento e alertas da subscription. ACR, logs, tráfego e serviços auxiliares podem gerar cobrança mesmo com a app ociosa; Consumption não significa custo zero.
- Para encerrar a atividade, siga a seção de remoção em [azure.md](azure.md), após confirmar exclusividade dos recursos e preservar evidências. Parar Compose local não remove recursos Azure nem interrompe sua cobrança.

Referências: [Docker Compose](https://docs.docker.com/compose/), [Azure Container Apps — ingress](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview), [pull com identidade gerenciada](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull), [GitHub/Azure OIDC](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect), [preços Container Apps](https://azure.microsoft.com/pricing/details/container-apps/).
