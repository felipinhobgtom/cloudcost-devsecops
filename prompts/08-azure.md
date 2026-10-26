# 08 — Refinar o destino para Azure

Prompt reutilizável reconstruído a partir do requisito humano de usar a nuvem Azure. Execute depois da definição do artefato de CI e antes da revisão final. Não é prova de que recursos foram criados.

```text
Use Azure como destino real do CloudCost. Preserve a app Go e o Compose para desenvolvimento/smoke local. Não mantenha um segundo fluxo de publicação GHCR. Entregue infraestrutura declarativa e procedimentos reais, não um exemplo que executa uma imagem diferente da aplicação.

Arquitetura: Azure Container Apps Consumption, ACR privado com usuário admin desabilitado, imagem cloudcost por digest, ingress HTTPS no domínio padrão fornecido pela Azure, health probes na porta 8080 e limites de recursos/escala explícitos. Registry privado significa acesso autenticado; não afirme Private Link ou isolamento de rede se não configurados. Não prometa que os campos de hardening Docker Compose são todos suportados pela API Container Apps.

Implemente infra/azure/foundation.bicep, main.bicep e app.bicep, scripts/azure-bootstrap.sh, scripts/azure-deploy.sh e .github/workflows/deploy-azure.yml. docs/azure.md deve ser o guia autoritativo dos parâmetros, permissões, custos, outputs e recuperação. Antes de provisionar, confirme subscription, região permitida, cotas, acesso e autorização explícita de custos. Nesta entrega, use resource group rg-cloudcost-devsecops em southcentralus: a política da subscription bloqueia eastus. Não exponha IDs desnecessários, tokens ou dados de credenciais em evidências públicas.

O bootstrap cria a infraestrutura de base e federação GitHub OIDC para o repositório real e environment azure-production. Sem client secret, senha do registry ou token permanente no repositório. Separe identidade de deployment (Contributor somente no resource group e AcrPush somente no ACR) da identidade gerenciada de pull (AcrPull somente no ACR). A identidade de pull não deve ser oferecida ao código da aplicação quando a plataforma permitir restringir seu ciclo de vida. Documente privilégios temporários de bootstrap e sua remoção/restrição.

Consulte repos/<repository>/actions/oidc/customization/sub com X-GitHub-Api-Version: 2026-03-10. Exija use_default true, include_claim_keys ausente/vazio e sub_claim_prefix válido antes de formar subject = prefixo real + :environment:azure-production. Respeite use_immutable_subject e IDs retornados; não monte o prefixo apenas com owner/repo. Falha de API ou claims customizadas exige parada/revisão, não fallback de subject nem mudança automática das claims. Reconcile somente a credencial federada gerenciada e autorizada, sem ampliar confiança para manter um subject antigo.

Workflow manual com input run_id: aceite somente CloudCost CI concluído com sucesso no repositório/main autorizados e com security-gate aprovado. Baixe cloudcost-image com image.tar, image-identity.json e summary.json; confira origem e conteúdo. Registre source_image_id, config_digest e loaded_image_id separadamente: o ID Docker de origem pode identificar índice OCI. Valide a cadeia configuração/rootfs do tar à imagem carregada/publicada, sem assumir que todo ID é digest de configuração; publique no ACR e implante o digest do manifesto sem rebuild. O job usa id-token:write para OIDC, não packages:write. Proteja o environment; não aceite artefato de PR/fork como release.

Gere evidência real de release em azure-evidence/deployment.json e endpoint.json, com ligação ao run/commit/digest, sem tokens. Capture a URL somente dos outputs Azure e teste HTTPS/health/API depois do deploy autorizado. Não substitua indisponibilidade de credenciais, cota ou região por URL fictícia.

Inclua rollback explícito para digest anterior aprovado usando azure-deploy.sh rollback, com registro do digest anterior/novo e verificação posterior. Diferencie reimplantar imagem de restaurar dados (a app não persiste dados). Preserve artefatos e relatórios necessários à recuperação.

Explique custos: Consumption não significa gratuito; ACR, logs, tráfego, armazenamento e recursos auxiliares podem cobrar mesmo com app ociosa. Limite escala, recomende orçamento/alertas e descreva encerramento dos recursos somente com confirmação do responsável. Aprovação/revisores dependem do plano e de pessoas distintas. Neste cenário de mantenedor único, registre a exceção --allow-no-reviewers e que aprovação independente não foi atestada; environment restrito a main não equivale a revisão obrigatória. Nunca crie bypass silencioso.

Saída: arquivos operacionais completos e documentação com estados configurado/provisionado/verificado separados. Registre execução apenas se autorizada e observada; deixe os demais pré-requisitos explicitamente atribuídos ao operador.
```
