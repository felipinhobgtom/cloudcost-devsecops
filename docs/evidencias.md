# Evidências de execução — CloudCost

Registro da execução em **26/10/2026**. Esta página distingue aplicação exercitada, análise realizada e configuração remota. Não é certificação nem promessa de ausência de vulnerabilidades. Os relatórios locais ficam em diretórios ignorados pelo Git; os workflows preservam suas próprias evidências como artifacts.

## Aplicação e análise locais

A rodada `reports/20261026T225350Z-5f8668af/summary.json` terminou com **`status: passed`**, antes do primeiro commit. Comando executado:

```sh
bash scripts/security-checks.sh
```

| Verificação executada | Resultado observado |
| --- | --- |
| Go 1.27.3, `go vet` e testes Go | Aprovados |
| gosec 2.30.0 | Aprovado; sem achados bloqueantes |
| govulncheck 1.9.0 | Aprovado, incluindo análise da biblioteca padrão |
| Gitleaks 8.30.1, árvore de trabalho | Aprovado; histórico ainda não aplicável nessa rodada sem commits |
| Trivy 0.76.1, configuração e imagem | Aprovados; relatório da imagem sem vulnerabilidades HIGH/CRITICAL nas fontes consultadas |
| SBOM CycloneDX | Gerada e validada |
| Compose e runtime Docker | Configuração, usuário sem privilégios, restrições e healthcheck aprovados |
| HTTP/DAST direcionado | **61 cenários aprovados; 0 falhas** |

O ID reportado pelo Docker nessa rodada foi `sha256:f9af0c9ec46b052cc380c020128eec424d0dbc4d0110c28bd8968be8d4be90d6`. É o identificador observado no daemon local; não o confundir com um digest ACR de uma entrega posterior. O artefato possui também checksum de `image.tar` e SBOM. O resultado de Trivy refere-se ao filtro HIGH/CRITICAL, não a todos os riscos possíveis nem à segurança integral da infraestrutura Azure.

Os cenários HTTP incluíram cálculo de exemplo (87 USD), zero, limites superiores, arredondamento, campos ausentes/null/negativos/acima do limite, JSON inválido/extra, expoente extremo, corpo excedente, métodos/mídias, cabeçalhos e saúde após requisições rejeitadas. São verificações direcionadas, não pentest completo.

### Uso real no navegador

Executado `docker compose up -d --no-build --wait`, com contêiner saudável em `http://127.0.0.1:8080`.

- Desktop 1440 × 1000: resultado inicial **87,00**, alteração para duas instâncias com aviso de resultado desatualizado, novo cálculo **159,00** e restauração do exemplo para **87,00**.
- Nenhum erro de JavaScript observado durante esse fluxo.
- Tela móvel 390 × 844: formulário e resultado renderizados; largura do documento igual à viewport, sem rolagem horizontal.
- Contêiner adicional com `PORT=8081`: execução real de `/cloudcost healthcheck` aprovada. O contêiner de verificação foi removido.

## Azure: fundação provisionada

O usuário autorizou o provisionamento com consumo de créditos na assinatura Azure for Students. A política da assinatura permite `southcentralus`, mas não `eastus`; foi utilizada **South Central US**.

O bootstrap concluiu com sucesso em `rg-cloudcost-devsecops`, criando a fundação declarada e a federação OIDC. Outputs efetivamente gravados no environment GitHub:

| Recurso/configuração | Valor observado |
| --- | --- |
| ACR Basic autenticado | `cloudcostqdg4gnaofhy5k` |
| Environment Container Apps | `cloudcost-env-qdg4gnaofhy5k` |
| Nome reservado da aplicação | `cloudcost-app-qdg4gnaofhy5k` |
| Região | `southcentralus` |
| Environment GitHub | `azure-production`, permitindo somente a branch `main` |

**Este registro inicial ainda não atesta uma aplicação publicada na Azure.** O bootstrap deliberadamente não cria app com imagem de exemplo: a entrega exige uma CI bem-sucedida e promoção de seu artefato por digest. Identificadores de assinatura/tenant e tokens não são incluídos nesta página.

O bootstrap foi executado com `--allow-no-reviewers` para a demonstração de mantenedor único: **não houve aprovação humana independente**. Dispatch manual e restrição de branch não equivalem a required reviewers. Essa limitação permanece explícita na matriz de conformidade.

Bicep **v0.48.1** compilou `foundation.bicep` e `main.bicep` (incluindo o módulo `app.bicep`). A sintaxe Bash dos três scripts Azure foi verificada. **actionlint v1.7.12** aprovou os dois workflows. Compilar/lintar não substitui verificar o deployment no provedor.

## GitHub e controles remotos

Repositório privado criado: <https://github.com/felipinhobgtom/cloudcost-devsecops>.

Configurações aplicadas pela API:

- Actions habilitado, exigindo Actions fixadas por SHA.
- Permissões padrão de workflow somente leitura.
- Actions impedido de aprovar pull requests.
- Environment `azure-production` com política permitindo somente `main`.

A proteção de merges de `main` e a execução do pipeline precisam de evidência própria; não são presumidas pela presença dos arquivos YAML. Acesso ao repositório privado e a seus artifacts depende de permissão GitHub.

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

Erro de ferramenta foi tratado como falha, não como “nenhuma vulnerabilidade”. A revisão estática adicional não é apresentada como revisão humana independente ou auditoria certificadora.

## Limites operacionais

ACR Basic pode consumir créditos mesmo com a aplicação em escala zero. Não foi criado teto financeiro, WAF ou rate limit distribuído. Não há Log Analytics/workspace de retenção. A análise automática não comprova LGPD integral, ASVS completo, segurança do tenant ou inexistência de falhas desconhecidas. Consulte [conformidade](conformidade.md), [operação Azure e remoção de recursos](azure.md) e [política de segurança](../SECURITY.md).
