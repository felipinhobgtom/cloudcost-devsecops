# 04 — Automatizar DevSecOps e publicação

Prompt reutilizável reconstruído. Entrada: Docker/Compose, repositório real confirmado e política de segurança.

```text
Implemente uma esteira DevSecOps auditável para o CloudCost. Use .github/workflows/ci.yml com nome CloudCost CI e jobs checks -> security-gate. O nome exato security-gate será exigido pela proteção de main. Faça esse gate executar mesmo quando dependências falham e aprovar somente sucesso de todos os controles; skipped/cancelled não podem liberar deployment.

Execute go vet e testes, SAST com gosec, govulncheck incluindo a biblioteca padrão do Go, Gitleaks para segredos, Trivy para vulnerabilidades da imagem e configuração, SBOM e smoke/DAST direcionado à API/headers. scripts/security-checks.sh é o ponto de entrada local e deve falhar em achados bloqueantes e erros de ferramenta/download/base. Guarde relatórios em reports/ fora do Git, com versões, data, commit e identidade da imagem quando disponíveis. Não transforme falha de scanner em resultado limpo.

Política mínima: bloquear vulnerabilidades HIGH/CRITICAL, inclusive sem correção publicada, segredos detectados e falhas dos controles obrigatórios. Não use --ignore-unfixed nem ignore indiscriminadamente achados. Defina em security/POLICY.md o tratamento de severidades menores, triagem, correção e exceções humanas explícitas com escopo/prazo; documente o que a automação não avalia.

Compile a imagem UMA vez, examine/teste exatamente essa imagem e libere o artefato cloudcost-image apenas após os controles passarem. Sua raiz contém image.tar, image-identity.json e summary.json. O workflow Azure manual recebe o run_id aprovado de main, valida procedência/sucesso, baixa o artefato e carrega sem rebuild. Separe source_image_id, config_digest e loaded_image_id: o ID Docker de origem pode ser um índice OCI, não o digest de configuração. Valide a cadeia configuração/rootfs antes de publicar no ACR e implantar o digest do manifesto. Não há publicação GHCR neste desenho. Tag de commit e IDs locais não substituem @sha256:.

Permissões: contents:read por padrão; leitura dos artefatos do run e id-token:write somente onde necessários no deployment OIDC Azure. Não use packages:write, PAT embutido, senha de service principal ou chave cloud persistente. PR não publica imagem e não recebe credenciais Azure. Não execute código de PR não confiável em pull_request_target com segredos. Fixe Actions em SHA completo e scanners/imagens em versões/digests verificados em fontes oficiais; documente em security/toolchain.md como atualizar.

Configure reexame periódico da fonte/imagem corrente na CI e reexame do digest efetivamente implantado: deploy-azure.yml agenda apenas o job rescan às 05:47 UTC usando azure-deploy.sh rescan, sem deployment no schedule e com relatórios preservados inclusive em falha. Ofereça também bash scripts/security-checks.sh --rescan <ACR>/cloudcost@sha256:<digest> após autenticação autorizada. São verificações distintas: rebuild não demonstra o estado do digest em produção. O rescan Azure reutiliza a identidade OIDC de deployment; não alegue identidade read-only separada. Não confunda agendamento com execução/atendimento de alerta. Gere SBOM como inventário, não como certificado.

Documente configuração manual do GitHub: main exige security-gate e revisão independente, proteção contra force-push/deleção e privilégios mínimos. Confirme disponibilidade no plano privado antes de afirmar enforcement. Configure environment/federação OIDC restritos ao repositório e implantação aprovados; derive o subject de sub_claim_prefix retornado pela API real do GitHub, após exigir use_default true e ausência de include_claim_keys customizadas. Não presuma prefixo baseado apenas em owner/repo; preserve o modo de subject imutável. Use ACR sem admin e Container Apps com identidade AcrPull. Descreva autenticação sem tokens expostos e separe privilégios de bootstrap/operação.

Saída: arquivos completos e documentação dos gates, artefatos e limites. Não alegue que CI, scanners ou publicação foram executados sem evidência de uma execução real. Deixe a rodada integrada para o responsável designado.
```
