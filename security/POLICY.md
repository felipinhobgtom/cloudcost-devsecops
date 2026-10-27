# Política dos gates e da entrega

Este projeto educacional **não é uma certificação** e não promete ausência de vulnerabilidades. O escopo dos controles é a aplicação CloudCost, seu artefato e a configuração de desenvolvimento. A produção alvo é **Azure Container Apps + Azure Container Registry**, com implantação por identidade federada/gerenciada, conforme os arquivos de infraestrutura e o workflow de entrega. Configuração não é evidência de recurso provisionado.

## Critérios de bloqueio

| Controle | Critério de aprovação | Evidência por execução |
| --- | --- | --- |
| Qualidade Go | `go vet ./...` e `go test -count=1 -json -coverprofile=... ./...` retornam zero | Logs, `go-test.jsonl`, `coverage.out` |
| SAST gosec | Nenhum finding/erro em produção ou testes; `-tests -nosec=true`, sem exclusões de regras | `gosec.json` + código de saída |
| SCA govulncheck | Nenhum finding, incluindo stdlib e findings não alcançáveis; parsing explícito do stream JSON | `govulncheck.json` |
| Segredos Gitleaks | Nenhum segredo no worktree examinável nem no histórico completo disponível; `--redact=100` e remoção de metadados `Message`/`Fragment` antes de publicar evidência | `gitleaks-worktree.json`, `gitleaks-history.json` sanitizados; exit code original preservado |
| Vulnerabilidades Trivy | Nenhuma vulnerabilidade **HIGH/CRITICAL**, incluindo as **sem correção disponível** | `trivy-image.json`; `--ignore-unfixed=false` |
| Configuração Trivy | Nenhuma falha em qualquer severidade, incluindo LOW/UNKNOWN; nenhum ignore ativo | `trivy-config.json`, com Dockerfile reconhecido |
| Compose/hardening | UID 65532, rootfs somente leitura, sem capabilities adicionais, `ALL` removidas, `no-new-privileges`, limites aplicados e porta em loopback | `compose.resolved.json`, `container-inspect.json` |
| Inventário | SBOM CycloneDX válido/não vazio e biblioteca padrão Go identificada | `sbom.cdx.json` |
| HTTP smoke/DAST | Todos os casos de API, limites, rejeição, headers, assets e disponibilidade aprovados | `dast.json` |
| Identidade do artefato | CI examina/executa o image ID exportado; rescan examina o digest imutável no registry e executa a imagem correspondente em Linux/AMD64 | `image-identity.json`, `image-inspect.json`, `summary.json`; `image.tar.sha256` somente no modo `full` |

Um scanner indisponível, timeout, erro de download, relatório inválido/vazio, build malsucedido, controle não executado por falha de pré-requisito ou exportação de artefato falha **bloqueia**. O wrapper usa `set -euo pipefail`; subprocessos Python são chamados com listas de argumentos, sem shell, e seus códigos são registrados. Não há `|| true`, `continue-on-error` nem conversão de falha de scanner em sucesso.

LOW/MEDIUM de imagem não são cobertos pelo gate HIGH/CRITICAL; precisam de triagem periódica e revisão de risco, não são uma declaração de ausência. O gate de configuração, diferentemente do de CVE, inclui todas as severidades. Governança deve acompanhar avisos Go e do fornecedor entre execuções; o agendamento não equivale a monitoramento contínuo.

## Escopo real de análise

- Gitleaks worktree e Trivy config recebem um snapshot dos arquivos rastreados pelo Git mais não rastreados/não ignorados. Não há exclusão por linguagem/diretório de aplicação. `.gitignore` separa artefatos gerados (`reports/`, `.tools/`, `.cache/`, `bin/`); arquivos rastreados continuam incluídos mesmo se também corresponderem a um ignore.
- Gitleaks também examina o histórico com `--all`. Checkout CI usa `fetch-depth: 0` e não persiste credenciais. Um repositório local ainda sem commits registra histórico como não aplicável, nunca como varredura executada; CI sem HEAD válido bloqueia.
- `.gitleaks.toml` e `.gitleaksignore` são recusados tanto no snapshot quanto na raiz montada para o histórico, inclusive se ignorados pelo Git. As regras embutidas da versão fixada continuam ativas; não são substituídas por allowlists do repositório.
- Todas as chamadas Trivy passam `--config=` e `--ignorefile=` para impedir configuração e supressões automáticas do repositório. O gate de configuração lê também o stderr: a mensagem `Falling back to embedded checks` da versão fixada bloqueia mesmo quando o scanner retorna zero, pois indica falha ao obter/carregar o bundle de checks.
- Trivy identifica tipos de configuração suportados, em especial Dockerfile. Compose é validado explicitamente pelo script e seu hardening é observado no contêiner. Não inferir que uma ferramenta analisou todos os formatos de infraestrutura só porque percorreu um diretório: validação Bicep/Azure e controles do serviço estão na entrega Azure.
- Smoke/DAST exercita o exemplo de USD 87, zeros, limites máximos, arredondamento, campos ausentes/nulos/negativos/acima do limite, tipos inválidos, JSON malformado/trailing, corpo acima de 4096 bytes, media types e métodos rejeitados, expoente extremo, headers e disponibilidade após rejeições. Também verifica assets locais e ausência de código inline/cookies. **Não** substitui pentest, fuzzing, análise manual ou teste de carga.
- HTTP é permitido somente no loopback para demonstração. Internet exige HTTPS: na Azure o endpoint público deve usar ingress TLS do Container Apps. Proteção contra abuso, configuração da conta/assinatura, RBAC e limites reais do serviço precisam da avaliação operacional indicada na documentação Azure.

## CI e cadeia de entrega

1. Pull requests e pushes em `main` executam `CloudCost CI`; uma rotina diária às **05:23 UTC** reexamina fonte e uma imagem recém-construída com os mesmos pins. Isso não é prova de que uma imagem histórica implantada foi reexaminada. O grupo de concorrência inclui o tipo de evento: agendamentos não cancelam a execução de push/manual que produz o artefato de entrega.
2. O job final **`security-gate`** depende do sucesso de `checks`, inclusive preservação de relatórios e exportação do artefato quando aplicável. Configure esse nome como required status check no GitHub; o arquivo YAML sozinho não ativa branch protection.
3. O workflow tem somente `contents: read`, não usa `pull_request_target`, não interpola entradas de PR dentro de comandos e não publica em GHCR. Actions usam SHA completo.
4. Relatórios são enviados com `if: always()` por 14 dias, mesmo em falha; o tar aprovado é retido por 7 dias. Gitleaks escreve primeiro em diretório temporário fora de `reports/`; os campos `Message` e `Fragment` são removidos do JSON antes de copiá-lo para evidências, inclusive em exit code não zero. Seu stdout/stderr bruto não é publicado, pois pode conter metadados não redigidos; o código de saída original e o relatório sanitizado são preservados. Falha de sanitização bloqueia. `--redact=100` protege os segredos reconhecidos, **não todo o contexto**: nomes de arquivo, autores, e-mails, hashes e outros metadados podem revelar informações. Mantenha acesso apropriado e revise os relatórios antes de divulgação; nenhuma ferramenta detecta todos os segredos.
5. O workflow Azure consome o artefato **`cloudcost-image`** de uma execução confiável/aprovada de `main`, verifica identidade/checksum e publica o mesmo image ID no ACR, sem rebuild. Implantação deve usar digest, não `latest` nem somente tag. Permissões OIDC/RBAC pertencem ao job/identidade de entrega, não à CI de PR.
6. Para reexaminar uma imagem publicada, use `bash scripts/security-checks.sh --rescan <referência-por-digest>`. Somente `registry/repository@sha256:<64 hex minúsculos>` é aceito. Antes do pull, `docker manifest inspect` resolve um único candidato Linux/AMD64: descriptors de outros OS/arches explícitos e attestations não participam da seleção. Múltiplos candidatos AMD64/variantes, plataforma ambígua ou mais de quatro níveis bloqueiam. Plataforma ausente é candidato potencial, não uma suposição: só segue se único e a inspeção final precisa comprovar Linux/AMD64. Docker e ambos os scans Trivy recebem **o mesmo digest final explícito**, não um índice sujeito a seleções independentes. Trivy usa `--image-src remote --platform linux/amd64`; Docker puxa esse filho e valida seu digest em `RepoDigests`. Não se compara `.Id` ao digest de config. Não há rebuild, push, reexportação ou fallback.
7. A autenticação do rescan copia somente a entrada `auths` do registry selecionado para um `DOCKER_CONFIG` temporário, fora de `reports/`, com diretório `0700`, arquivo `0600` e montagem somente leitura no Trivy. Para Docker Hub, `docker.io`, `index.docker.io` e `registry-1.docker.io` são aliases da mesma origem: todos participam da seleção de credenciais/helpers e a saída conserva a chave canônica `https://index.docker.io/v1/`. Referências Hub são normalizadas para `docker.io`, preservando o argumento original na evidência. Credenciais de outros registries não são montadas; tokens não entram nos argumentos nem relatórios. Sem credencial, imagens públicas podem ser examinadas anonimamente. `credHelpers` aplicável ou `credsStore` não suportado bloqueia, exigindo login temporário restrito.

O modo `rescan` registra a referência original em `requested_reference`, o manifesto final em `scan_reference` e `scan_source: registry` em `image-identity.json`/`summary.json`. `manifest-resolution.json` preserva a cadeia índice→filho, os digests de manifesto/config e os arquivos `registry-manifest-N.json`; `registry-access.json` registra apenas metadados, sem segredo. Não se declara geração de `image.tar`/checksum. O modo `full` mantém o artefato de CI exportado e seu checksum. Stores containerd podem possuir snapshots executáveis sem todos os blobs distribuíveis, produzindo tar incompleto mesmo com exit zero; no rescan, usa-se o registry canônico sem reconstruir/inventar bytes ausentes.

## Exceções responsáveis

**Não existem exceções ativas, baseline de aceitação, arquivo ignore vazio ou botão de bypass.** `#nosec` e comentários `gitleaks:allow` não liberam os gates deste projeto.

Para um falso positivo ou risco que não possa ser corrigido imediatamente:

1. Abra uma análise privada quando houver segredo, exploração ou dado sensível; siga `SECURITY.md`. Nunca cole credenciais ou provas destrutivas em issue pública.
2. Registre ferramenta/versão, regra/CVE, arquivo/linha ou pacote/versão, digest afetado, evidência de aplicabilidade, severidade, impacto, compensações, responsável e prazo de expiração.
3. Obtenha aprovação explícita de responsável técnico e de segurança; correção ou atualização é a primeira opção. Uma vulnerabilidade sem patch **não** é ignorada automaticamente.
4. A aprovação administrativa não altera o gate. Até correção, a entrega permanece bloqueada. Se for indispensável implementar uma exceção, isso exige um PR separado, escopo exato, justificativa pública sanitizada, expiração verificável e revisão; nunca exclusão de diretório/regra inteira, `--ignore-unfixed`, baseline genérica ou `continue-on-error`.
5. Remova a exceção junto com a correção e reexecute os controles sobre o novo digest. Preserve evidências anteriores para rastreabilidade.

Fontes: [Go vulnerability management](https://go.dev/security/vuln/), [Trivy vulnerability scanning](https://trivy.dev/docs/latest/scanner/vulnerability/), [Gitleaks](https://github.com/gitleaks/gitleaks), [GitHub Actions security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions), [Azure Container Apps ingress](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview).
