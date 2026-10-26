# Política de segurança

CloudCost é um projeto educacional de estimativa, não um serviço de cobrança nem uma oferta com SLA. A manutenção se concentra no estado atual de `main`; digests antigos não têm garantia de suporte e não devem ser preservados em produção apenas por terem passado em um scan anterior.

## Como relatar uma vulnerabilidade

**Não publique tokens, dados pessoais, conteúdo de logs sensíveis ou uma prova de exploração em issue pública.** Não explore sistemas de terceiros para demonstrar um problema neste projeto.

- **Cópia local ou entrega ainda não publicada:** envie um relato reservado à pessoa responsável que forneceu o projeto, pelo mesmo canal privado de entrega. Mantenha anexos sensíveis fora do repositório e combine um meio de transferência antes de enviá-los. Não é necessário criar conta ou publicar um exploit.
- **Repositório privado atual:** <https://github.com/felipinhobgtom/cloudcost-devsecops>, mantido por `felipinhobgtom`. Um colaborador autorizado pode abrir uma issue no próprio repositório **depois de confirmar que sua visibilidade continua privada e quem tem acesso**. Todos os colaboradores com permissão de leitura podem vê-la; para detalhes restritos, use o canal privado de entrega.
- **Se o repositório se tornar público:** use a opção **Security → Report a vulnerability** somente se estiver habilitada. Na ausência dela, solicite ao responsável um canal privado, sem incluir detalhes da falha numa issue pública. Não há endereço de email ou canal de reporte fictício neste projeto.

Inclua apenas o necessário: commit ou digest afetado; ambiente e versões; endpoint/arquivo; passos mínimos com dados sintéticos; comportamento esperado e observado; impacto; e mitigação sugerida, se conhecida. Relatórios de ferramentas devem informar ferramenta, versão, data e regra/CVE; remova segredos antes do envio. Guarde o original de modo restrito se ele for necessário à investigação.

Não há programa de recompensa, SLA de resposta ou prazo contratual de correção. O responsável deve confirmar recebimento, avaliar impacto, combinar a divulgação com o relator e registrar correção/limites sem expor detalhes exploráveis antes da mitigação.

## Triagem e resposta

1. Delimite versões/digests e alcance. Se houver vazamento de credencial, revogue/rotacione no emissor antes de considerar limpeza do Git suficiente.
2. Se houver exposição ativa, retire a instância de acesso externo ou retorne a um digest anterior **avaliado como não afetado**. Rollback não remove credenciais já vazadas nem prova que o host não foi comprometido.
3. Corrija a causa, acrescente regressão pertinente e gere nova imagem pelo pipeline normal. Nunca transforme indisponibilidade de scanner em aprovação.
4. Faça revisão humana, conserve relatórios e publique uma nota de correção proporcional ao impacto. Investigue se host local, ingress Azure, permissões OIDC/RBAC, GitHub ou ACR também precisam de remediação.
5. Se dados pessoais puderem ter sido afetados, acione o responsável pelo tratamento para avaliar obrigações de comunicação aplicáveis; esta política não substitui análise jurídica.

## Controles e limites

A [política dos gates](security/POLICY.md) define bloqueios, triagem e exceções. A [matriz parcial](docs/conformidade.md), o [modelo de ameaças](docs/ameacas.md) e as [evidências](docs/evidencias.md) distinguem implementação, configuração e execução observada.

A aplicação não requer segredos de runtime, credenciais cloud fornecidas pelo visitante, dados pessoais ou persistência. O destino de produção é Azure Container Apps com ACR privado, federação GitHub OIDC e identidade gerenciada para pull; o [guia Azure](docs/azure.md) distingue configuração de provisionamento efetivo. Acesso ao daemon local, IAM/RBAC Azure, proteção de main/environment, logs, custos e monitoramento continuam responsabilidades operacionais. Publicar uma imagem ou obter um scan limpo não certifica segurança nem elimina vulnerabilidades desconhecidas.
