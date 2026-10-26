# CloudCost — guia da apresentação

Apresentação educativa em **9 slides**, em português, com destino de implantação na **Azure Container Apps Consumption**, imagem em **Azure Container Registry privado** e desenvolvimento local com Docker Compose. A IA é usada para criar o projeto; a aplicação não consome serviços de IA.

- Abrir: [index.html](index.html).
- Arquivo de saída da exportação: [cloudcost-devsecops.pdf](cloudcost-devsecops.pdf).
- Código e instruções gerais: [README do projeto](../README.md).
- Deploy cloud: [docs/azure.md](../docs/azure.md).
- Controles e limites: [docs/conformidade.md](../docs/conformidade.md).
- Execuções efetivamente registradas: [docs/evidencias.md](../docs/evidencias.md).
- Arquivo de prompts: [prompts/README.md](../prompts/README.md).

## Abrir e navegar

Abra `presentation/index.html` diretamente no navegador. Não é necessário servidor, instalação de pacote ou conexão à internet para visualizar os slides: CSS, JavaScript e diagramas estão no diretório. Mantenha `index.html`, `styles.css` e `slides.js` juntos.

Na raiz do projeto, em um desktop Linux:

```sh
xdg-open presentation/index.html
```

| Ação | Comando |
| --- | --- |
| Próximo slide | seta direita, seta para baixo, Page Down ou espaço |
| Slide anterior | seta esquerda, seta para cima ou Page Up |
| Primeiro / último | Home / End |
| Escolher um slide | botões de navegação numerados para leitores de tela |
| Imprimir / exportar | botão “Imprimir / PDF”, tecla P ou Ctrl+P |
| Navegar pelos links e controles | Tab / Shift+Tab; Enter para ativar |

Há botões Anterior/Próximo, indicadores de posição e endereçamento direto por fragmento, por exemplo `index.html#slide-3`. A navegação não impede atalhos do navegador com Ctrl, Alt ou Meta. Sem JavaScript, os nove slides ficam disponíveis em sequência.

O layout de tela usa um canvas proporcional de até 1200 × 675 px e deixa espaço para os controles em uma janela de 1280 × 800 px. Em telas estreitas, as colunas passam a uma sequência vertical; diagramas largos podem ser deslocados horizontalmente. Os links externos requerem internet. Os links GitHub privados também requerem autorização.

## Exportar para PDF

As regras `@media print` e `@page` definem **A4 paisagem**, margem de 8 mm e **um slide por página**. Os slides inativos também entram na impressão; os controles de navegação não entram.

1. Abrir `index.html` no navegador.
2. Escolher “Imprimir / PDF”.
3. Selecionar “Salvar como PDF”, A4 e orientação paisagem.
4. Manter escala em 100%, habilitar gráficos de plano de fundo e desabilitar cabeçalhos e rodapés do navegador. Não aplicar margens adicionais às definidas pelo CSS.
5. Salvar como `presentation/cloudcost-devsecops.pdf`.
6. Conferir nove páginas, textos completos, diagramas e links. O HTML é o arquivo-fonte editável.

Alternativa com Chromium instalado, a partir da raiz do projeto:

```sh
chromium --headless --no-pdf-header-footer \
  --print-to-pdf="$PWD/presentation/cloudcost-devsecops.pdf" \
  "file://$PWD/presentation/index.html"
```

O nome do executável depende da instalação local (`chromium`, `chromium-browser` ou `google-chrome`). O comando é uma instrução de exportação, não um registro de execução. A validação visual e a geração do PDF fazem parte da verificação integrada da entrega.

## Roteiro para apresentar

| Slide | Conteúdo | Nota de apresentação |
| --- | --- | --- |
| 1 — Do prompt à entrega controlada | Propósito, criação assistida e execução independente | Começar pela distinção essencial: a IA criou o projeto; não há API de IA no fluxo de execução. Azure é o destino, Compose é o ambiente local. |
| 2 — Quanto custa este cenário? | Problema útil, fórmula e exemplo de US$ 87,00 | Explicar 72 de computação, 10 de armazenamento e 5 de tráfego. São preços informados pelo usuário, não preços atuais de um provedor nem o custo de operar esta implantação Azure. |
| 3 — Destino Azure, desenvolvimento local | Navegador → HTTPS → Container Apps; ACR privado, identidade gerenciada e AcrPull | Mostrar a fronteira entre build, runtime e registry. O binário Go contém a interface. Bicep descreve infraestrutura, mas sua existência não comprova recursos provisionados. |
| 4 — Controles em camadas | Validação da API, segurança do navegador e hardening Compose | Separar controles da aplicação e da imagem dos controles específicos do Docker Compose. Não presumir equivalência de todas as opções no Container Apps. |
| 5 — O mesmo artefato até o deploy | Testes, SAST, SCA, segredos, Trivy, SBOM e smoke; promoção Azure com OIDC | A CI gera `cloudcost-image`; o deploy manual seleciona uma execução aprovada, promove a mesma imagem ao ACR e referencia o digest. Não há rebuild nem publicação em GHCR neste fluxo. |
| 6 — Método não é evidência | Identificação do alvo, análise, correção e reavaliação | Distinguir configurado, executado e não comprovado. Uma contagem zero de achados não elimina risco. Apresentar resultados reais somente com os relatórios correspondentes. |
| 7 — Conformidade com escopo | Mapeamento parcial SSDF/ASVS, privacidade e responsabilidades Azure | Não usar termos como “certificado”, “LGPD garantida” ou “100% seguro”. ACR e serviços habilitados podem gerar cobrança mesmo se a aplicação escalar a zero. |
| 8 — Prompts e rastreabilidade | Arquivo local/GitHub, commit, run e digest | Mostrar o repositório real, explicar sua visibilidade privada e separar URL criada de código enviado, CI executada e cloud implantada. |
| 9 — Executar, observar e comprovar | Comandos locais, deploy Azure manual e referências | Se houver execução real comprovada, abrir a aplicação e os relatórios. Caso contrário, apresentar os comandos como instruções e os resultados como expectativas contratuais. |

## Demonstração local

Pré-requisitos e versões das ferramentas estão no [README principal](../README.md). Os comandos abaixo são executados na raiz do repositório; podem baixar imagens, ferramentas e bases de vulnerabilidades.

```sh
docker compose up --build -d --wait
curl -fsS http://127.0.0.1:8080/healthz
python3 scripts/smoke.py http://127.0.0.1:8080
bash scripts/security-checks.sh
```

Abra <http://127.0.0.1:8080/>. Para o exemplo do slide 2, informar:

| Entrada | Valor |
| --- | ---: |
| Instâncias | 1 |
| Horas no mês | 720 |
| Preço por instância/hora | 0,10 |
| Armazenamento em GB | 100 |
| Preço por GB de armazenamento no mês | 0,10 |
| Saída de dados em GB | 50 |
| Preço por GB de saída | 0,10 |

**Expectativas, não evidências capturadas:** `/healthz` retorna `{"status":"ok"}`; o cenário resulta em US$ 72,00 + US$ 10,00 + US$ 5,00 = **US$ 87,00**. Alterar as horas permite comparar cenários. Os relatórios gerados pelos controles ficam em `reports/`; sua existência e resultado devem ser conferidos na execução correspondente.

Encerrar o ambiente local:

```sh
docker compose down
```

## Demonstração Azure

Consulte [docs/azure.md](../docs/azure.md) antes de provisionar. É necessário acesso autenticado a uma assinatura, permissões adequadas, região permitida e autorização para os custos. O uso de OIDC na CI evita armazenar senha Azure; não dispensa o bootstrap da identidade, a federação, o RBAC nem a configuração do ambiente GitHub.

Fontes da infraestrutura: [infra/azure/foundation.bicep](../infra/azure/foundation.bicep), [infra/azure/main.bicep](../infra/azure/main.bicep) e [infra/azure/app.bicep](../infra/azure/app.bicep).

Exemplo de bootstrap com grupo dedicado, após definir `AZURE_SUBSCRIPTION_ID` e aprovar os parâmetros. Este projeto usa `southcentralus`: a política da assinatura não permite `eastus`. Em outra assinatura, confira as regiões autorizadas antes de provisionar.

```sh
./scripts/azure-bootstrap.sh \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --resource-group rg-cloudcost-devsecops \
  --location southcentralus \
  --repository felipinhobgtom/cloudcost-devsecops \
  --accept-costs \
  --allow-no-reviewers
```

O sinalizador `--accept-costs` representa um aceite real de cobrança. A execução real foi autorizada para este projeto, mas autorização não comprova provisionamento concluído. ACR e outros serviços habilitados podem gerar custos independentemente do número de réplicas da aplicação.

Neste laboratório com mantenedor único, `--allow-no-reviewers` declara explicitamente a exceção de seguir sem revisores independentes no ambiente de deploy. **Aprovação independente não está configurada nem atestada.** Em outro contexto, remova essa exceção e configure as políticas de aprovação compatíveis com o plano e a governança do repositório.

O bootstrap configura a fundação e a federação OIDC; não cria a aplicação nem constrói sua imagem. O deploy da aplicação ocorre pelo workflow manual a partir da CI autorizada.

Selecione o ID de uma execução aprovada da CI originada por **push em `main`**, não por PR, fork ou agendamento, que tenha o artefato `cloudcost-image` disponível; defina `CI_RUN_ID` com esse ID real. O artefato transporta `image.tar`, `image-identity.json` e `summary.json`.

```sh
gh workflow run deploy-azure.yml --ref main -f run_id="$CI_RUN_ID"
```

Depois do deploy, examine o run, o digest no ACR, a revisão ativa do Container Apps e o endpoint HTTPS informado pela Azure. Registre os resultados em conformidade com [docs/evidencias.md](../docs/evidencias.md). Não invente hostname público, ID de assinatura ou digest nos slides. A apresentação não pressupõe que esse provisionamento já ocorreu.

Ao encerrar o laboratório, siga a seção de remoção de recursos de `docs/azure.md`. Confirme que o grupo é dedicado ao projeto antes de remover recursos; encerrar o Compose não encerra recursos Azure.

## Origem dos diagramas e do tema

Todos os diagramas são **SVGs vetoriais originais, escritos para esta entrega e incorporados diretamente em `index.html`**. Não são screenshots de execução, imagens de provedores ou logotipos oficiais. Cores são herdadas das variáveis do tema em `styles.css`; os SVGs não dependem de download nem de propriedades CSS de um documento externo. Os textos alternativos estão em elementos `title` e `desc` associados por `aria-labelledby`.

| Ilustração | Local | Origem / significado |
| --- | --- | --- |
| Criação assistida e execução independente | Slide 1, `creation-title` | Diagrama autoral do escopo. IA participa da criação, não do runtime. |
| Arquitetura Azure e fronteiras | Slide 3, `arch-title` | Diagrama autoral alinhado ao contrato da implantação e à documentação Microsoft/Docker abaixo. Não representa recursos observados na assinatura. |
| Pipeline e promoção do artefato | Slide 5, `pipeline-title` | Diagrama autoral do fluxo configurado, não de uma execução aprovada. |
| Rastreabilidade de prompts até evidências | Slide 8, `trace-title` | Diagrama autoral que conecta intenção, commit, run e digest. |

A tipografia usa apenas fontes disponíveis no sistema. Não há CDN, framework de slides, imagens remotas, tracker ou biblioteca JavaScript externa. A pasta da apresentação pode ser distribuída offline; documentos vinculados por caminhos relativos precisam acompanhar a estrutura do repositório.

## Fontes primárias

Os slides pertinentes contêm links clicáveis. As fontes explicam práticas e recursos; elas **não certificam esta implementação nem comprovam seus resultados**.

- Azure Container Apps: <https://learn.microsoft.com/en-us/azure/container-apps/overview>.
- Pull de imagem privada com identidade gerenciada: <https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull>.
- GitHub Actions → Azure via OIDC: <https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect>.
- Docker multi-stage builds: <https://docs.docker.com/build/building/multi-stage/>.
- Docker Compose e opções de serviços: <https://docs.docker.com/reference/compose-file/services/>.
- Go vulnerability management / govulncheck: <https://go.dev/doc/security/vuln/>.
- Trivy vulnerability scanning: <https://trivy.dev/latest/docs/scanner/vulnerability/>.
- Uso seguro de GitHub Actions: <https://docs.github.com/en/actions/reference/security/secure-use>.
- NIST SP 800-218, SSDF 1.1: <https://csrc.nist.gov/pubs/sp/800/218/final>.
- OWASP ASVS 5.0: <https://asvs.owasp.org/>.

Repositório real, inicialmente privado: <https://github.com/felipinhobgtom/cloudcost-devsecops>. Arquivo remoto de prompts: <https://github.com/felipinhobgtom/cloudcost-devsecops/tree/main/prompts>. Os links exigem que os arquivos tenham sido enviados e que o visitante possua acesso; a criação da URL é um estado distinto da publicação do código e da execução de CI/deploy.
