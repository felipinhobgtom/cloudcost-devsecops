# GitHub e promoção para Azure

## Repositório real e estados distintos

Repositório privado criado: <https://github.com/felipinhobgtom/cloudcost-devsecops>. Prompts no caminho <https://github.com/felipinhobgtom/cloudcost-devsecops/tree/main/prompts> quando os arquivos estiverem na `main`. Usuários sem permissão podem receber 404; isso não transforma o link em endereço público de apresentação.

A existência do repo não prova que o código foi enviado, que a CI passou ou que há uma app Azure implantada. Use [evidencias.md](evidencias.md) para o estado observado de cada etapa. A arquitetura final publica imagens no **Azure Container Registry**, não no GitHub Packages/GHCR.

## Integrar sem sobrescrever o repositório do usuário

1. Se já trabalha num clone, confira `git remote -v` e o destino antes de enviar. Não recrie o repositório, não troque `origin` silenciosamente e não force-push.
2. Num repositório existente com histórico, importe as mudanças em uma branch de trabalho e abra PR para `main`, preservando arquivos/histórico alheios. Não use `--force` ou `--allow-unrelated-histories` como atalho de integração.
3. Revise arquivos staged, ignore caches/relatórios/credenciais e execute os gates autorizados antes de commit/push. `reports/`, `.azure/`, configuração do Docker, tokens e segredos não devem ser enviados.
4. Em um repo remoto ainda vazio, o mantenedor precisa enviar uma base inicial confiável para estabelecer `main` e registrar o primeiro status check. Essa janela de bootstrap não equivale a proteção aplicada: habilite as regras antes dos merges seguintes.
5. Dê acesso de leitura a quem precisa avaliar os prompts/slides; acesso de escrita somente a revisores/mantenedores necessários. Não torne o repo público apenas para contornar limitações de plano sem decisão do proprietário.

Se precisar clonar uma cópia separada, com autenticação já configurada:

```sh
gh repo clone felipinhobgtom/cloudcost-devsecops
```

Nunca coloque token na URL do remoto. Use autenticação oficial do GitHub CLI ou chave SSH gerenciada fora do projeto.

## Proteção de main

Em **Settings → Branches** ou **Rules → Rulesets**, configure uma regra para `main`:

- exigir PR e **pelo menos uma aprovação independente**; descartar aprovações obsoletas após mudanças relevantes e exigir resolução de conversas;
- exigir o status check de nome exato **`security-gate`**, produzido pelo workflow **`CloudCost CI`** em [ci.yml](../.github/workflows/ci.yml); selecione GitHub Actions como origem esperada quando a interface permitir;
- exigir branch atualizada antes do merge; não aceitar merge enquanto gates falharem;
- bloquear force-push e deleção; aplicar proteção a administradores/sem bypass rotineiro, quando disponível;
- revisar especialmente alterações em workflows, scripts de release, pins e infraestrutura Azure. Uma pessoa não pode oferecer revisão independente do próprio PR.

Execute a CI uma vez para o nome do check aparecer na seleção. O gate agregado é necessário: status `skipped`/`neutral` podem ser considerados aceitáveis pelo GitHub em alguns contextos; a implementação do gate deve falhar se dependências não concluírem com sucesso. Não crie outro job com o mesmo nome em outro workflow.

**Disponibilidade depende do plano e da visibilidade.** Proteção de branch e aprovações de environment em repositório privado podem exigir plano com suporte ao recurso. Se indisponíveis, registre a lacuna, mantenha revisão manual documentada e não declare enforcement automático. Um repo individual precisa de outro revisor autorizado para cumprir revisão independente; não remova esse requisito silenciosamente.

## Permissões de Actions

Configurações remotas cuja aplicação foi confirmada na criação deste projeto:

| Configuração do repositório | Valor aplicado | O que isso não garante |
| --- | --- | --- |
| Actions habilitado | `enabled=true` | Não prova execução de workflow |
| Política de Actions | `allowed_actions=all` com `sha_pinning_required=true` | SHA fixa a revisão, não é allowlist de fornecedores nem auditoria do código da Action |
| Permissão padrão do `GITHUB_TOKEN` | leitura (`default_workflow_permissions=read`) | Jobs precisam continuar declarando escopos mínimos |
| Actions pode criar/aprovar reviews de PR | `can_approve_pull_request_reviews=false` | Não configura revisão independente nem proteção de `main` por si só |

Reconfirme esses valores após mudanças administrativas. Na UI, mantenha **Workflow permissions: Read repository contents and packages permissions** e desabilite **Allow GitHub Actions to create and approve pull requests**. Limite quem pode editar workflows/administrar o repo e use MFA. Não entregue runners privilegiados ou segredos a PRs não confiáveis.

O caminho de CI tem leitura de conteúdo; o deployment usa `actions:read` para o artefato e `id-token:write` para a troca OIDC conforme o workflow. **`id-token:write` não fornece uma senha Azure:** a Azure só aceita o token se issuer/audience/subject corresponderem à federação configurada. Não conceda `packages:write`; o registry de produção é ACR.

## Environment azure-production e OIDC

O procedimento completo e os pré-requisitos de acesso estão em [azure.md](azure.md). O bootstrap autorizado usa [azure-bootstrap.sh](../scripts/azure-bootstrap.sh) e configura valores reais no environment **`azure-production`**:

| Variáveis | Finalidade |
| --- | --- |
| `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | Identificação da identidade federada, tenant e subscription; não são senhas |
| `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION` | Escopo de recursos e região autorizados |
| `AZURE_ACR_NAME`, `AZURE_ACR_LOGIN_SERVER` | Registry privado de destino |
| `AZURE_CONTAINER_APP_NAME`, `AZURE_ENVIRONMENT_NAME`, `AZURE_PULL_IDENTITY_NAME` | App, ambiente Container Apps e identidade de pull |

Não invente valores, não reutilize credenciais de outra subscription e não publique dumps de ambiente. O projeto não precisa de client secret, senha de service principal ou credencial admin do ACR.

A relação de confiança deve aceitar somente o repositório `felipinhobgtom/cloudcost-devsecops` e o environment autorizado, com issuer GitHub e audience esperados. Nesta entrega, o environment `azure-production` existe com `main` permitida; **aprovação independente não está atestada** no cenário de mantenedor único. O bootstrap usa o reconhecimento explícito `--allow-no-reviewers`. Isso é uma exceção com risco residual, não uma proteção equivalente a revisores obrigatórios. Habilite revisão independente quando disponível e não confunda a restrição de branch do environment com proteção de merge da `main`.

### Derivar o subject OIDC da configuração real

Não reconstrua o subject apenas com nomes de proprietário/repositório: o GitHub pode usar um prefixo com IDs imutáveis. A fonte autoritativa é a configuração OIDC do próprio repositório, consultada pelo bootstrap com a versão de API explícita:

```sh
gh api -H 'X-GitHub-Api-Version: 2026-03-10' \
  repos/felipinhobgtom/cloudcost-devsecops/actions/oidc/customization/sub
```

Antes de derivar o subject, o bootstrap exige `use_default: true`, `include_claim_keys` ausente/vazio e `sub_claim_prefix` presente/válido. O campo `use_immutable_subject` informa o modo adotado; preserve o prefixo retornado, inclusive IDs imutáveis quando presentes. Com as claims padrão e este environment, o subject é **o valor real de `sub_claim_prefix` seguido de `:environment:azure-production`**.

Se a API falhar, o prefixo faltar ou existirem claims customizadas, pare e revise a configuração; não invente um prefixo nem altere as claims do repositório para forçar o login. Na Azure, confira issuer, audience e subject exatos. Uma credencial federada antiga deve ser reconciliada pelo bootstrap autorizado, sem ampliar a confiança a subjects arbitrários ou manter um caminho legado de autenticação como atalho.


Papéis previstos:

- **Identidade OIDC de deployment e rescan agendado:** `Contributor` somente no resource group e `AcrPush` somente no ACR. A mesma identidade é reutilizada; o rescan não tem uma identidade read-only separada. Esses privilégios são amplos dentro do grupo: use o grupo dedicado `rg-cloudcost-devsecops`, revisão e proteção da federação.
- **Identidade gerenciada de pull:** `AcrPull` somente no ACR; sem senha no container. A configuração Azure restringe o uso dessa identidade à operação necessária, não ao código da calculadora.
- **Responsável pelo bootstrap:** precisa criar/configurar recursos e atribuir papéis. Não transfira seus privilégios administrativos para o workflow nem presuma que `Contributor` sozinho permite criar atribuições RBAC.

## Da CI à imagem implantada

1. `CloudCost CI` examina código/configuração, constrói uma imagem, examina/testa esse conteúdo e libera o artefato **`cloudcost-image`** com `image.tar`, `image-identity.json` e `summary.json` apenas após sucesso.
2. Uma pessoa revisa `main`, `security-gate`, relatórios/SBOM e o ID do run aprovado. Artefatos de PR/fork não são releases autorizadas.
3. O workflow manual [deploy-azure.yml](../.github/workflows/deploy-azure.yml) recebe esse ID:

```sh
gh workflow run deploy-azure.yml --ref main -f run_id="$CI_RUN_ID"
```

4. O deployment verifica origem/sucesso, usa OIDC, carrega o mesmo tar sem rebuild, valida a cadeia de configuração/rootfs, envia ao ACR e implanta **por digest**. Registra separadamente `source_image_id`, `config_digest` e `loaded_image_id`: o ID de origem pode identificar um índice OCI e não é necessariamente o digest da configuração. A tag de commit e os IDs locais não substituem o digest do manifesto publicado em `@sha256:`.
5. Conserve o artefato de deployment `azure-deployment-<run>-<attempt>`, os arquivos `azure-evidence/deployment.json`/`endpoint.json`, run CI, commit e digest. Só declare endpoint disponível após testar a URL HTTPS verdadeira.

Não edite o workflow para aceitar um run com falha nem faça upload manual de imagem reconstruída sob a mesma tag. Se um artefato expirar, gere nova CI completa e promova a imagem novamente examinada; não atribua evidências antigas a um novo binário.

O mesmo workflow configura um job `rescan` diário às 05:47 UTC, sem deployment no evento agendado. Ele usa `azure-deploy.sh rescan` para consultar o digest em execução e examiná-lo sem rebuild; os relatórios são preservados inclusive em falhas. Confirme os runs e atenda alertas: configuração de cron não comprova execução pontual nem correção dos achados.

## Autenticação ACR para uma pessoa

O login do GitHub não autentica o Docker na Azure. Para pull local, um operador com papel apropriado faz `az login`, seleciona a subscription autorizada e executa `az acr login --name "$AZURE_ACR_NAME"`; veja o procedimento por digest em [operação](operacao.md). Não habilite usuário admin do registry para facilitar acesso e não use `az acr login --expose-token` em logs ou prompts.

“ACR privado” significa imagem protegida por autenticação/RBAC; não implica Private Link, firewall de rede exclusivo ou endpoint sem acesso público. Verifique a configuração de rede real antes de alegar isolamento. A promoção automatizada usa OIDC; o runtime usa identidade gerenciada `AcrPull`.

## Fontes primárias

- [GitHub — proteção de branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
- [GitHub — environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
- [GitHub — OIDC para Azure](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure).
- [Microsoft — autenticação GitHub/Azure OIDC](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect).
- [Microsoft — pull ACR com identidade gerenciada](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull).
