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

### Corrigido e exercitado

- Implantação real por GitHub Actions/OIDC no Azure Container Apps, com promoção sem rebuild ao ACR e verificação HTTPS da imagem aprovada.
- Prontidão baseada na revisão efetivamente ativa, `Provisioned`, com 100% do tráfego e digest esperado, verificada antes/depois do smoke; não depende do campo ausente `latestReadyRevisionName` no ambiente Express.
- Distinção entre ID Docker, configuração e manifesto OCI, preservando a integridade do artefato entre os armazenamentos Docker da CI e do ambiente local.
- Proteção de `main` com PR, `security-gate` vinculado ao GitHub Actions, aplicação a administradores e bloqueio de force-push/deleção. Revisão humana independente não foi configurada na demonstração de mantenedor único.
- Verificação da aplicação pública com 61 cenários HTTP e navegação real em desktop e celular; apresentação exportada para PDF de nove páginas.
- Reanálise do digest implantado diretamente no registry autenticado, com isolamento temporário da credencial selecionada e sem depender da reexportação incompleta observada no Docker local. Um manifesto Linux/AMD64 inequívoco vincula Docker, Trivy e SBOM; aliases Docker Hub preservam a chave de autenticação canônica. Reexame real e limites de seleção/credenciais exercitados.

### Escopo e evidência

Este registro descreve a criação dos artefatos, **não uma release certificada nem aprovação de testes**. Comandos efetivamente executados, achados, publicação e limitações ambientais são registrados em [docs/evidencias.md](docs/evidencias.md). HTTP em loopback é demonstração local; exposição externa exige os pré-requisitos de [operação](docs/operacao.md).
