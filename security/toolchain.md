# Toolchain e referências fixadas

Esta configuração foi preparada em **26/10/2026**. Versões/digests abaixo foram consultados nas APIs oficiais; isso **não significa que os scanners foram executados**. Resultados executados pertencem a `reports/` e ao relatório de evidências do projeto.

## Imagens e ferramentas

| Componente | Pin utilizado | Origem primária |
| --- | --- | --- |
| Builder | `golang:1.27.3-alpine@sha256:b8c9b82affbbb82a020bbcf998dad2ba9516944ac7e883524642a481a9505e9c` | [Docker Hub, imagem oficial Go](https://hub.docker.com/v2/repositories/library/golang/tags/1.27.3-alpine), [Go downloads](https://go.dev/dl/) |
| Runtime | `scratch`; somente `/cloudcost`, UID/GID `65532:65532` | [Docker: imagem base mínima](https://docs.docker.com/build/building/base-images/#create-a-minimal-base-image-using-scratch) |
| Go dos testes/SCA | `1.27.3` (`GOTOOLCHAIN=go1.27.3`) | [Toolchains Go](https://go.dev/doc/toolchain) |
| gosec | `github.com/securego/gosec/v2/cmd/gosec@v2.30.0` | [Release oficial](https://github.com/securego/gosec/releases/tag/v2.30.0) |
| govulncheck | `golang.org/x/vuln/cmd/govulncheck@v1.9.0` | [Go module proxy](https://proxy.golang.org/golang.org/x/vuln/@v/v1.9.0.info), [código/documentação oficial](https://github.com/golang/vuln/blob/v1.9.0/cmd/govulncheck/doc.go) |
| Gitleaks | `zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f` | [Imagem oficial indicada pelo projeto](https://github.com/gitleaks/gitleaks/tree/v8.30.1#installing), [digest Docker Hub](https://hub.docker.com/v2/repositories/zricethezav/gitleaks/tags/v8.30.1) |
| Trivy | `aquasec/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c` | [Release oficial](https://github.com/aquasecurity/trivy/releases/tag/v0.76.1), [digest Docker Hub](https://hub.docker.com/v2/repositories/aquasec/trivy/tags/0.76.1) |

Os digests de imagens são de índices multiplataforma. CI usa `ubuntu-24.04`/Linux AMD64; a imagem aprovada mantém a arquitetura em que foi construída. Não há `latest`, `curl | sh` ou dependências de terceiros em runtime. `security/toolchain.json` é a configuração consumida pelo script; builder/Go também estão fixados no Dockerfile e workflow e devem ser atualizados juntos.

Os executáveis gosec/govulncheck são instalados em `.tools/bin` pelo Go, com versão explícita, `proxy.golang.org` e `sum.golang.org`. Se a instalação falha, um executável antigo **não** substitui o pin. Downloads de ferramentas não viram dependências da aplicação.

## Actions fixadas por commit completo

| Action | Versão de referência | Commit | Verificação oficial |
| --- | --- | --- | --- |
| `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | [Ref oficial](https://api.github.com/repos/actions/checkout/git/ref/tags/v7.0.1) |
| `actions/setup-go` | `v7.0.0` | `b7ad1dad31e06c5925ef5d2fc7ad053ef454303e` | [Ref oficial](https://api.github.com/repos/actions/setup-go/git/ref/tags/v7.0.0) |
| `actions/upload-artifact` | `v7.0.2` | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` | [Ref oficial](https://api.github.com/repos/actions/upload-artifact/git/ref/tags/v7.0.2) |
| `actions/download-artifact` | `v8.0.2` | `9000827ccba6bdab643e8b6fd33ac0654aef8333` | [Ref oficial](https://api.github.com/repos/actions/download-artifact/git/ref/tags/v8.0.2) |

As três primeiras actions compõem a CI; a quarta é o contrato de consumo do artefato pela entrega Azure. Actions específicas de Azure e seus pins estão no workflow de entrega. Dependabot propõe atualizações semanais de Actions e Docker; revisão humana e gates continuam obrigatórios. Não aprovar automaticamente uma troca de digest.

## Reexecução e evidências

Pré-requisitos: Linux, Bash, Git, Python 3, Go capaz de selecionar a toolchain fixada, Docker Engine e Docker Compose v2. Acesso ao daemon Docker é privilégio elevado no host; use uma máquina/runner dedicado, nunca monte o socket na aplicação ou nos scanners. É necessário acesso de rede aos registries, Go proxy/checksum database e bases de vulnerabilidades.

```bash
# Build único de entrega + todos os controles locais; não faz push nem cria recursos Azure.
bash scripts/security-checks.sh

# Aplicação local para demonstração, fora do contêiner efêmero do scanner.
docker compose up --build -d --wait
python3 scripts/smoke.py http://127.0.0.1:8080 --report reports/smoke-manual.json
docker compose down

# Reexaminar o artefato já publicado, após autenticação de leitura no ACR.
# Substitua a referência pelo digest REAL registrado na entrega Azure.
bash scripts/security-checks.sh --rescan REGISTRY.azurecr.io/cloudcost@sha256:DIGEST_REAL
```

O último comando contém marcadores de documentação, não uma imagem publicada: o argumento efetivo deve ser minúsculo, com `@sha256:` seguido de 64 caracteres hexadecimais. Rescan aceita **somente digest**: tags, mesmo `sha-<commit completo>`, são mutáveis e recusadas antes do pull.

Cada execução cria um diretório novo `reports/<UTC>-<id>/`. `reports/latest.json` aponta para ele e inclui o resultado dos stages; não apaga execuções anteriores. São preservados códigos de saída, comandos sem credenciais, duração, relatórios JSON, SBOM CycloneDX, inspeção do contêiner e identidade da imagem. O modo `full` também preserva manifesto de arquivos-fonte, Compose resolvido, `image.tar` e checksum; o modo `rescan` registra origem remota/digest e não reexporta o tar. Stdout/stderr são preservados, exceto o texto bruto do Gitleaks: ele fica apenas em arquivos temporários privados, pois pode conter metadados de commit não redigidos. Antes de publicar seu JSON, são removidos `Message` e `Fragment`, mesmo quando o scanner falha; o exit code original permanece no resumo. Isso não anonimiza caminhos, autores, e-mails ou todo o contexto. Falhas não são resultados limpos.

A CI `CloudCost CI`, em `.github/workflows/ci.yml`, publica o artefato `cloudcost-image` somente após o script inteiro passar em `main` (push ou execução manual, não agendamento). Contém `image.tar`, `image.tar.sha256`, `image-identity.json`, `image-inspect.json`, `summary.json`, `sbom.cdx.json` e `trivy-image.json`. O tar foi salvo por image ID e pode não carregar uma tag: o consumidor deve verificar checksum, carregar o tar e conferir o ID, não reconstruir. A entrega Azure é separada; esta CI não tem credenciais de nuvem nem permissão de escrita em registry.

### Origem da imagem no rescan

`--rescan` usa o padrão `docker manifest inspect` da entrega Azure, com profundidade máxima quatro, para resolver o manifesto executável por digest. Seleciona exatamente um candidato Linux/AMD64; outros OS/arches explícitos e attestations ficam fora da seleção, preservando o suporte a índices multiplataforma. Múltiplas variantes AMD64 são recusadas, sem escolher a primeira. Plataforma ausente permanece candidato potencial e só pode seguir se único, com verificação final da plataforma pelo Docker; ambiguidades bloqueiam. Docker pull, Trivy de vulnerabilidades e SBOM recebem **a mesma referência final do filho** em Linux/AMD64. A inspeção valida o digest do filho em `RepoDigests`; `.Id` não é comparado ao digest de config. `requested_reference` preserva o argumento original, `scan_reference` identifica o filho e `manifest-resolution.json` registra a cadeia. Não há fallback, rebuild ou reexportação de tar. O fluxo `full`/CI permanece inalterado.

Para ACR privado, o login temporário Azure já fornece `DOCKER_CONFIG`. Copiam-se apenas `auth`, `identitytoken` ou `registrytoken` da entrada selecionada para um diretório temporário `0700`, com `config.json` `0600`, montado read-only e removido ao terminar. Docker Hub normaliza os aliases `docker.io`, `index.docker.io` e `registry-1.docker.io` tanto para lookup de credenciais quanto para detectar helpers; o arquivo restrito mantém a chave `https://index.docker.io/v1/` exigida pelo DefaultKeychain, e a referência de scan usa `docker.io`. O argumento original continua registrado. Nunca se monta todo `~/.docker` nem se copiam credenciais de outros registries. Sem credencial, usa-se configuração vazia para imagens públicas; helper aplicável/configurado é recusado explicitamente.

A resolução explícita evita que Docker e Trivy escolham filhos diferentes de um mesmo índice: o [go-containerregistry seleciona o primeiro descriptor correspondente](https://github.com/google/go-containerregistry/blob/v0.22.1/pkg/v1/remote/index.go#L169-L198), o que não prova igualdade entre consumidores quando há variantes. A [chave canônica de autenticação Docker Hub](https://github.com/google/go-containerregistry/blob/v0.22.1/pkg/authn/keychain.go#L153-L178) também deve ser preservada, não substituída apenas pelo hostname.

Motivo operacional: um snapshot executável no store containerd não prova que todos os blobs comprimidos necessários a `docker save` estão disponíveis. O exportador pode omitir descendentes de um manifest e ainda retornar zero, como descrito na [documentação Docker](https://docs.docker.com/engine/storage/containerd/#lazy-pulling), no [incidente Moby #49473](https://github.com/moby/moby/issues/49473) e na [correção de aquisição de blobs #53615](https://github.com/moby/moby/pull/53615). Nesse caso, ajustar o parser do scanner não recupera os bytes ausentes. A origem remota por digest evita depender dessa reexportação e mantém a identidade criptográfica do artefato publicado. Referências do scanner: [flag de origem na versão fixada](https://github.com/aquasecurity/trivy/blob/v0.76.1/pkg/flag/image_flags.go) e [autenticação por registry/DOCKER_CONFIG](https://www.trivy.dev/docs/latest/advanced/private-registries/).


## O que é e o que não é reproduzível

- Pins, código, parâmetros de build e arquitetura tornam a entrada do build explícita; `-trimpath`, `-buildvcs=false`, `-buildid=` e `SOURCE_DATE_EPOCH` reduzem variação. Não se promete reprodução bit a bit entre plataformas/builders diferentes sem medir.
- No modo `full`, a imagem de entrega é construída **uma vez**, exportada, examinada, executada por ID e entregue como o mesmo tar para ACR. No modo `rescan`, Trivy/SBOM leem diretamente o digest já publicado e Docker executa esse mesmo digest; nenhuma nova imagem é construída.
- As bases CVE/Go e as regras Trivy são atualizadas em cada execução; não são congeladas para esconder descobertas. Resultados podem mudar sem alteração de código. Data, metadados do scanner e relatório devem acompanhar toda alegação. Falha de download/carregamento do bundle de checks que produz `Falling back to embedded checks` bloqueia o gate de configuração; não é aceita uma troca silenciosa para regras embutidas.
- `govulncheck -json` pode retornar zero **mesmo com findings**. O script lê o stream completo e bloqueia qualquer finding, inclusive stdlib e achados não alcançáveis. Uma resposta vazia/malformada também bloqueia.
- Trivy deve identificar o binário Go; o SBOM precisa incluir `stdlib`. `scratch` reduz pacotes de SO, mas não elimina vulnerabilidades da biblioteca padrão.
- Trivy sempre recebe `--config=` e `--ignorefile=`. A semântica de desativar carregamento com string vazia está declarada nos flags oficiais da versão fixada: [global_flags.go](https://github.com/aquasecurity/trivy/blob/v0.76.1/pkg/flag/global_flags.go) e [report_flags.go](https://github.com/aquasecurity/trivy/blob/v0.76.1/pkg/flag/report_flags.go). A condição de fallback é definida em [artifact/run.go](https://github.com/aquasecurity/trivy/blob/v0.76.1/pkg/commands/artifact/run.go).
- Gitleaks usa as regras embutidas fixadas. `.gitleaks.toml`/`.gitleaksignore` na raiz real ou no snapshot bloqueiam o scanner, em vez de alterar sua cobertura. A [descoberta de configuração](https://github.com/gitleaks/gitleaks/blob/v8.30.1/cmd/root.go) e os [limites da redação nativa](https://github.com/gitleaks/gitleaks/blob/v8.30.1/report/finding.go) fundamentam esses controles.
