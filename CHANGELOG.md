# Changelog

## Criação inicial — 2026-10-26

### Adicionado

- CloudCost: interface em português e API Go para estimativa mensal de computação, armazenamento e saída de dados em USD, com preços de exemplo informados pelo usuário.
- Contrato JSON estrito, limites de entrada, arredondamento por categoria, healthcheck e cabeçalhos de segurança; sem banco, cookies, telemetria ou integração de IA em runtime.
- Testes de aplicação e verificação HTTP, deployment Docker multi-stage e Compose local com usuário não root, filesystem somente leitura, capacidades removidas e limites de recursos.
- Pipeline DevSecOps com análise estática, vulnerabilidades, segredos, configuração, SBOM, gate e artefato único verificado; rastreabilidade por commit e digest e comando de reexame sem rebuild.
- Infraestrutura Azure em Bicep e automação de deployment para ACR privado/Container Apps Consumption, GitHub OIDC, identidade gerenciada AcrPull, ingress HTTPS e operação por digest, sem senha Azure persistente no repositório.
- Modelo de ameaças, matriz parcial OWASP ASVS 5.0.0/NIST SSDF 1.1, limites LGPD, operação, orientação GitHub/Azure e política de relato de vulnerabilidades.
- Prompts reutilizáveis reconstruídos e apresentação educacional com diagramas e referências oficiais.

### Escopo e evidência

Este registro descreve a criação dos artefatos, **não uma release certificada nem aprovação de testes**. Comandos efetivamente executados, achados, publicação e limitações ambientais são registrados em [docs/evidencias.md](docs/evidencias.md). HTTP em loopback é demonstração local; exposição externa exige os pré-requisitos de [operação](docs/operacao.md).
