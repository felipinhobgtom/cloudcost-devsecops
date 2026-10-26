# 05 — Modelar ameaças e mapear conformidade

Prompt reutilizável reconstruído. Entrada: código e configuração finais, evidências disponíveis e fontes primárias.

```text
Analise o CloudCost real, não um sistema genérico. Crie docs/ameacas.md e docs/conformidade.md em português, com escopo e limitações claros. Não altere código para encaixá-lo artificialmente em uma alegação de conformidade.

Desenhe o fluxo local navegador -> HTTP loopback -> cálculo em memória -> JSON e o fluxo Azure navegador -> HTTPS gerenciado -> Container Apps -> JSON. A cadeia de entrega é código/PR -> CI -> artefato cloudcost-image -> OIDC -> ACR privado -> Container Apps por digest com identidade gerenciada AcrPull. Separe fronteiras: entrada externa, processo/container, daemon local/plataforma Azure, GitHub Actions, federação e registry. A app não recebe credenciais cloud, não executa shell com entradas, não armazena dados nem consulta preços de terceiros.

Liste ativos, atores, pressupostos, ameaça, impacto, controle existente, evidência e risco residual. Considere entrada maliciosa/JSON ambíguo, XSS/clickjacking, exaustão de recursos/custos, resultados financeiros enganosos, vazamento em logs, dependências/toolchain, PR malicioso, federação OIDC ampla demais, RBAC excessivo, imagem substituída e escape de container. Não diga que scratch, não root ou CSP eliminam todas as ameaças.

Construa matriz parcial com: controle e referência versionada, evidência de implementação/configuração, como verificar, estado e limitação. Use OWASP ASVS 5.0.0 e NIST SSDF 1.1 (SP 800-218), com links oficiais. Confira identificadores antes de citá-los. Distingua implementado, configurado e pré-requisito manual; resultado executado só pode ser citado quando existe relatório, data, commit/digest e escopo. Não atribua nível ASVS ou certificação.

LGPD: descreva minimização, finalidade e limites. A calculadora só precisa de números e não persiste estimativas, mas IPs, user-agent, logs do proxy/host e contas do GitHub podem envolver dados pessoais. Não declare isenção automática por ser educacional ou não ter banco. Identificação de controlador/operadores, base legal, retenção, transparência, direitos e incidentes precisam de avaliação humana na implantação real. Consulte a Lei 13.709/2018, especialmente arts. 6, 7, 18 e 46.

Diferencie configuração Azure em Bicep de recursos efetivamente provisionados. Container Apps termina TLS no ingress; não presuma HSTS nem satisfação integral de todos os requisitos ASVS de transporte. Separe hardening Compose dos controles suportados pelo Azure. RBAC, revisão de main/environment, orçamento, limites de borda, monitoramento e políticas de logs precisam de confirmação operacional. Autenticação/sessões da app, SQL e pagamentos não fazem parte desta versão; registre justificativas de não aplicabilidade sem alegar cobertura de todo o padrão.

Use docs/evidencias.md como fonte dos resultados reais, sem duplicar números que podem ficar desatualizados. Saída: análise concisa, específica, revisável e sem promessas de zero vulnerabilidades ou parecer jurídico.
```
