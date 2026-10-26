# Evidências de execução — CloudCost

Registro da execução em **26/10/2026**. Esta página distingue aplicação exercitada, análise realizada e configuração remota. Não é certificação nem promessa de ausência de vulnerabilidades. Os relatórios locais ficam em diretórios ignorados pelo Git; os workflows preservam suas próprias evidências como artifacts.

## Aplicação e análise locais

A rodada final local `reports/20261026T230543Z-222e7c1a/summary.json` terminou com **25 etapas aprovadas**, vinculada ao commit `127e1f03dfe2dae13e59aedfb1bcc6708f4ddfcc`, incluindo a análise do histórico Git. Comando executado:

```sh
bash scripts/security-checks.sh
```

| Verificação executada | Resultado observado |
| --- | --- |
| Go 1.27.3, `go vet` e testes Go | Aprovados |
| gosec 2.30.0 | Aprovado; sem achados bloqueantes |
| govulncheck 1.9.0 | Aprovado, incluindo análise da biblioteca padrão |
| Gitleaks 8.30.1, árvore de trabalho e histórico Git | Aprovados; arquivos de supressão automática também verificados |
| Trivy 0.76.1, configuração e imagem | Aprovados; relatório da imagem sem vulnerabilidades HIGH/CRITICAL nas fontes consultadas |
| SBOM CycloneDX | Gerada e validada |
| Compose e runtime Docker | Configuração, usuário sem privilégios, restrições e healthcheck aprovados |
| HTTP/DAST direcionado | **61 cenários aprovados; 0 falhas** |

O ID reportado pelo Docker nessa rodada foi `sha256:1ef57b9f1dd781ae04fe9119d578a516fc35d68e42d05cbae6c4f8c477017dca`. `azure-deploy.sh prepare` validou o archive OCI real, seu grafo de descriptors, checksum, commit e bytes das camadas/configuração, sem executar ou recompilar a imagem. O digest de configuração observado foi `sha256:d2053c1b841c32df264bc3da7bbbea2751b93d09a5ecc566337c99e43024e957`: ele é diferente do ID de índice reportado pelo Docker. Esses valores locais não são presumidos como digest ACR de uma entrega posterior. O resultado Trivy refere-se ao filtro HIGH/CRITICAL, não a todos os riscos possíveis nem à segurança integral da infraestrutura Azure.

Também foi exercitada a preparação do **artefato real baixado do GitHub CI** no daemon containerd local: o config digest `sha256:f602cba8079b40abceb65714f187a1ff7a688e321a272b0afc72beca92bf0c8c` foi preservado e o daemon reportou o loaded Image ID `sha256:77d6a1357f1879f7a320a5d5e026dfcc1691eb8b8d8ce136790181d4a5b3654d`. Isso verificou a conversão entre stores reais sem tratar um ID de índice como se fosse config digest. Evidência local em `reports/cross-store-prepare/`.

Os cenários HTTP incluíram cálculo de exemplo (87 USD), zero, limites superiores, arredondamento, campos ausentes/null/negativos/acima do limite, JSON inválido/extra, expoente extremo, corpo excedente, métodos/mídias, cabeçalhos e saúde após requisições rejeitadas. São verificações direcionadas, não pentest completo.

### Verificações negativas dos controles

Foram exercitados os caminhos de bloqueio com fixtures temporárias, posteriormente removidas:

- Gitleaks detectou um token **sintético** no formato GitHub em um histórico Git de teste, retornou código 1 e teve mensagem do commit/conteúdo sensível removidos dos relatórios publicados. Configuração automática de supressão foi recusada.
- Um Dockerfile inseguro demonstrou a supressão automática do Trivy com argumentos padrão; os argumentos do projeto desabilitaram o ignore e mantiveram o bloqueio.
- A indisponibilidade deliberada do bundle de checks fez Trivy recorrer a checks embutidos com exit zero; o gate do projeto detectou o fallback e rejeitou a execução.
- Rescan por tag mutável, promoção com commit divergente e checksum adulterado foram recusados antes de pull/load.

Resultados: `reports/scanner-negative-smoke.json` e `reports/azure-negative-smoke.json`. Falhas esperadas nessas fixtures demonstram bloqueio, não achados de segredo real no projeto.

### Uso real no navegador

Executado `docker compose up -d --no-build --wait`, com contêiner saudável em `http://127.0.0.1:8080`.

- Desktop 1440 × 1000: resultado inicial **87,00**, alteração para duas instâncias com aviso de resultado desatualizado, novo cálculo **159,00** e restauração do exemplo para **87,00**.
- Nenhum erro de JavaScript observado durante esse fluxo.
- Tela móvel 390 × 844: formulário e resultado renderizados; largura do documento igual à viewport, sem rolagem horizontal.
- Contêiner adicional com `PORT=8081`: execução real de `/cloudcost healthcheck` aprovada. O contêiner de verificação foi removido.

## Azure: aplicação implantada e validada

O usuário autorizou o provisionamento com consumo de créditos na assinatura Azure for Students. A política da assinatura permite `southcentralus`, mas não `eastus`; foi utilizada **South Central US**.

O bootstrap concluiu com sucesso em `rg-cloudcost-devsecops`, criando a fundação declarada e a federação OIDC. Outputs efetivamente gravados no environment GitHub:

| Recurso/configuração | Valor observado |
| --- | --- |
| ACR Basic autenticado | `cloudcostqdg4gnaofhy5k` |
| Environment Container Apps | `cloudcost-env-qdg4gnaofhy5k` |
| Aplicação publicada | `cloudcost-app-qdg4gnaofhy5k` |
| Região | `southcentralus` |
| Environment GitHub | `azure-production`, permitindo somente a branch `main` |

Aplicação disponível em <https://cloudcost-app-qdg4gnaofhy5k.whiteglacier-f82b4e8a.southcentralus.azurecontainerapps.io/>. O bootstrap não utilizou imagem de exemplo: a entrega promoveu o artefato aprovado da CI por digest, sem rebuild. Identificadores de assinatura/tenant e tokens não são incluídos nesta página.

- **61 cenários HTTP aprovados, zero falhas**, executados contra a URL HTTPS pública; relatório local `reports/azure-public-smoke.json`.
- Navegador real na Azure: desktop 1440 × 1100 e móvel 390 × 844; exemplo **87,00**, duas instâncias **159,00**, restauração **87,00**. Sem erros JavaScript; recursos solicitados somente à origem da própria aplicação; tela móvel sem overflow horizontal.
- [Captura da interface executada na Azure](assets/cloudcost-azure.png).
- Imagem efetiva: `cloudcostqdg4gnaofhy5k.azurecr.io/cloudcost@sha256:ec85e6713e346d51d94ff51d256239c33b69b1cd5cbec098b082527bb6429e10`.
- Origem da imagem: CI `40417451541`, commit `127e1f03dfe2dae13e59aedfb1bcc6708f4ddfcc`. O login Azure via OIDC e o push autenticado ao ACR foram executados com sucesso.

O bootstrap foi executado com `--allow-no-reviewers` para a demonstração de mantenedor único: **não houve aprovação humana independente**. Dispatch manual e restrição de branch não equivalem a required reviewers. Essa limitação permanece explícita na matriz de conformidade.

Bicep **v0.48.1** compilou `foundation.bicep` e `main.bicep` (incluindo o módulo `app.bicep`). A sintaxe Bash dos três scripts Azure foi verificada. **actionlint v1.7.12** aprovou os dois workflows. Compilar/lintar não substitui verificar o deployment no provedor.

## GitHub e controles remotos

Código, prompts, infraestrutura e apresentação publicados no repositório privado: <https://github.com/felipinhobgtom/cloudcost-devsecops>. A execução inicial do CI **concluiu com sucesso**, incluindo `checks` e `security-gate`: <https://github.com/felipinhobgtom/cloudcost-devsecops/actions/runs/40417451541>.

O artifact `cloudcost-image` foi baixado e conferido: `summary.json` registra **25 etapas aprovadas** às `2026-10-26T23:10:30Z`, para o commit `127e1f03dfe2dae13e59aedfb1bcc6708f4ddfcc`. O Trivy remoto não reportou vulnerabilidades HIGH/CRITICAL na imagem; o SBOM contém `stdlib v1.27.3`. Arquivos preservados localmente em `reports/github-ci-image/`. A imagem para a entrega Azure é essa imagem do CI, não uma recompilação local.

Configurações aplicadas pela API:

- Actions habilitado, exigindo Actions fixadas por SHA.
- Permissões padrão de workflow somente leitura.
- Actions impedido de aprovar pull requests.
- Environment `azure-production` com política permitindo somente `main`.

A proteção de merges de `main` exige configuração remota própria; não é presumida pela presença dos arquivos YAML. Acesso ao repositório privado e a seus artifacts depende de permissão GitHub.

## Apresentação

- **9 slides** em `presentation/index.html`, com conteúdo técnico, fontes clicáveis e **4 diagramas SVG locais**.
- Navegação por botões, `Home` e `End` exercitada em Chromium; sem erros observados.
- Verificação de layout em 1280 × 800 sem conteúdo fora dos slides; layout de impressão também observado.
- `presentation/cloudcost-devsecops.pdf` exportado no navegador e conferido: **9 objetos de página**, aproximadamente 320 kB. Sem dependência de fontes, imagens ou scripts externos para apresentar.

## Falhas encontradas e tratamento

A primeira rodada não foi aprovada. Os erros foram preservados em `reports/20261026T225005Z-b8840eec/`:

1. **gosec G704 no healthcheck:** o fluxo foi tornado estruturalmente seguro com porta numérica validada e `url.URL`, mantendo host loopback, sem proxy nem redirects. Nova análise passou, sem suprimir a regra.
2. **Validação Compose:** o Docker serializou memória como string numérica. O validador passou a interpretar a representação canônica sem mudar os limites exigidos.
3. **Trivy sem espaço temporário:** ampliado o tmpfs do scanner de 128 MiB para 1 GiB. O limite de memória da aplicação continuou 128 MiB; a análise seguinte concluiu.
4. **Preflight Azure:** o serviço recusou o literal `appLogsConfiguration.destination: 'none'`. O bloco foi removido; a exportação de logs não foi configurada. O provisionamento seguinte concluiu sem criar workspace pago.
5. **Identidade OIDC:** a API autenticada do GitHub informou subject imutável com IDs de proprietário/repositório. A credencial Entra inicial foi corrigida para o prefixo real; a versão entregue exige a correspondência exata, sem confiança paralela no formato antigo.
6. **Identidade de imagem:** o Docker local reportou um índice OCI como Image ID, não o config digest. O fluxo passou a distinguir origem, imagem carregada, configuração e manifesto, verificando a cadeia sem rebuild. A preparação foi exercitada com sucesso no archive real.
7. **Compatibilidade Express:** a [primeira entrega Azure](https://github.com/felipinhobgtom/cloudcost-devsecops/actions/runs/40417975049) aprovou origem, preparação, login OIDC e push ACR, mas o provedor recusou `identitySettings` com `ExpressEnvironmentFeatureNotSupported`. Removida a propriedade não suportada, mantendo AcrPull restrito ao registro. Não se alega isolamento do token da identidade em relação ao processo nesse ambiente; esse risco residual está documentado.
8. **Prontidão da revisão:** a [segunda entrega](https://github.com/felipinhobgtom/cloudcost-devsecops/actions/runs/40418499535) publicou a imagem e concluiu a implantação ARM, mas o script marcou falha esperando `latestReadyRevisionName`, ausente no ambiente Express. A aplicação estava funcional: API de revisão mostrou estado `Provisioned`, ativa, 100% do tráfego e digest esperado; o smoke HTTPS público aprovou os 61 cenários. O controle foi corrigido para verificar esses estados observáveis e o digest antes/depois do smoke, sem inferir sucesso pela ausência do campo. `ScaledToZero` é esperado com mínimo zero; o nome Express `--latest` não é identidade imutável da imagem.

Erro de ferramenta foi tratado como falha, não como “nenhuma vulnerabilidade”. A revisão estática adicional não é apresentada como revisão humana independente ou auditoria certificadora.

## Limites operacionais

ACR Basic pode consumir créditos mesmo com a aplicação em escala zero. Não foi criado teto financeiro, WAF ou rate limit distribuído. Não há Log Analytics/workspace de retenção. A análise automática não comprova LGPD integral, ASVS completo, segurança do tenant ou inexistência de falhas desconhecidas. Consulte [conformidade](conformidade.md), [operação Azure e remoção de recursos](azure.md) e [política de segurança](../SECURITY.md).
