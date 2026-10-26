# Arquivo de prompts — CloudCost

## Intenção e procedência

A solicitação humana é usar IA **para criar um deployment educacional completo**, com aplicação real, Docker, controles DevSecOps, análise de conformidade, publicação organizada no GitHub e apresentação com pelo menos cinco slides, imagens e URLs. O destino de nuvem solicitado é **Azure Container Apps**, com imagem privada no **Azure Container Registry (ACR)**; Compose continua como ambiente local. A aplicação resultante **não consome uma API de IA**: é uma calculadora de custos mensais que não recebe credenciais de provedores.

Os textos numerados deste diretório são **prompts reutilizáveis reconstruídos a partir dos requisitos e das decisões do projeto**. Não são transcrições literais da conversa, não preservam cada interação intermediária e não demonstram que todos foram executados palavra por palavra. O código, os commits e as evidências efetivamente registradas são as fontes para verificar a entrega; um prompt descreve intenção, não comprova execução.

Repositório real: <https://github.com/felipinhobgtom/cloudcost-devsecops>. O repositório é privado; o acesso depende de permissão. Caminho do arquivo após o envio do código: <https://github.com/felipinhobgtom/cloudcost-devsecops/tree/main/prompts>. A existência dessas URLs não prova que um workflow ou uma publicação de imagem terminou; consulte [evidências](../docs/evidencias.md).

## Como reutilizar

1. Leia o [README principal](../README.md), o código atual e as restrições antes de copiar um prompt.
2. Forneça ao assistente o diretório autorizado, o commit-base e os arquivos existentes. Nas novas utilizações, informe a URL real do seu próprio repositório e o ambiente de destino; não substitua silenciosamente estes dados.
3. Use a sequência abaixo; execute o refinamento Azure (08) depois da CI (04) e antes da revisão final (07). Cada etapa deve preservar os contratos anteriores ou explicar uma alteração para revisão humana.
4. Não forneça tokens, chaves, dados pessoais, documentos confidenciais nem saídas integrais de logs. Use números sintéticos para as estimativas.
5. Revise o diff, as fontes oficiais e os comandos antes de autorizar execução. Comandos que criam recursos Azure e geram custos, publicam imagens, mudam proteção de branch ou substituem containers precisam de autorização e acesso apropriados.

## Rastreabilidade

| Prompt | Entrada necessária | Saída esperada | Verificação humana/automatizada a exigir |
| --- | --- | --- | --- |
| [01 — Escopo](01-escopo.md) | Pedido humano, diretório, ambiente e restrições | Contrato funcional, limites e critérios de aceitação | Confirmar que IA cria o projeto, não é dependência da aplicação; distinguir local de produção |
| [02 — Aplicação](02-aplicacao.md) | Contrato da API, limites numéricos, stack | Go, interface em português e testes | Casos positivos/negativos, centavos, acessibilidade básica, ausência de coleta desnecessária |
| [03 — Container](03-container.md) | Entrypoint, porta, healthcheck, versão oficial do Go | Dockerfile e Compose endurecidos | Inspecionar usuário, permissões, exposição de rede, limites e estado de saúde |
| [04 — CI e segurança](04-ci-seguranca.md) | Imagem, política de severidade, repo real | Pipeline, scanners, SBOM, gate e artefato verificado | Falha de scanner bloqueia liberação; a imagem enviada ao ACR é a examinada |
| [05 — Ameaças e conformidade](05-analise-conformidade.md) | Código/configuração, fontes oficiais, resultados disponíveis | Modelo de ameaças e matriz parcial com evidências | Não confundir configuração com execução; registrar riscos e pré-requisitos manuais |
| [06 — Documentação e slides](06-documentacao-slides.md) | Artefatos reais, fontes, limitações e URL confirmada | Guias, apresentação com imagens/URLs e arquivo de prompts | Links, navegação, leitura offline, ausência de alegações inventadas |
| [07 — Revisão e entrega](07-revisao-entrega.md) | Árvore final, permissões e ferramentas disponíveis | Resultados verificáveis e entrega sem segredos | Registrar comando, data, versão, commit/digest, saída e bloqueio real; revisão humana final |
| [08 — Azure](08-azure.md) | Subscription autorizada, região, repo e run CI aprovado | Bicep, bootstrap, federação OIDC, ACR privado e Container Apps por digest | Validar RBAC, artefato sem rebuild, HTTPS real, custo e rollback; não confundir IaC com recurso provisionado |

## Precauções de revisão

- A IA pode errar APIs, requisitos normativos, versões e identificadores de vulnerabilidade. Verifique fontes primárias e não trate a saída como parecer jurídico ou auditoria independente.
- Nunca aceite “seguro”, “certificado”, “100% conforme” ou “zero vulnerabilidades” como substituto de relatórios com escopo e data. Uma varredura limpa não exclui falhas desconhecidas ou de lógica.
- Preserve a diferença entre **implementado**, **configurado**, **executado com evidência** e **pré-requisito manual**. O histórico deste arquivo não é histórico de execução de ferramentas.
- Não relaxe gates, remova testes ou invente fallbacks para produzir resultados verdes. Qualquer exceção deve ser explícita, justificada, revisada e ter prazo, de acordo com a [política](../security/POLICY.md).
- Não inclua segredos nos prompts, issues, commits, slides ou relatórios. Varredura de segredos reduz risco, mas não prova ausência de vazamento.
- Revisão por uma pessoa continua necessária antes de merge, criação de recursos Azure ou exposição pública. OIDC, identidade gerenciada, HTTPS gerenciado, IAM e privacidade da infraestrutura não estão efetivos apenas porque há arquivos que os descrevem.
