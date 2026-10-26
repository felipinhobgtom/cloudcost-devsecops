# 03 — Criar deployment Docker mínimo

Prompt reutilizável reconstruído. Entrada: aplicação implementada, arquitetura do host e contrato do healthcheck.

```text
Crie o deployment Docker do CloudCost sem mudar o contrato funcional. Reutilize os padrões existentes. Entregue Dockerfile multi-stage e compose.yaml realmente executáveis, .dockerignore e documentação dos pins no local já adotado pelo projeto.

Builder: Go 1.27.3, obtido da fonte oficial, fixado em digest verificado. Não invente sha256. Compile ./cmd/server em /cloudcost com CGO desativado, sem download de dependências de runtime de terceiros. Imagem final scratch contendo só o binário necessário. Configure usuário/grupo 65532:65532, porta interna 8080 e healthcheck exec com /cloudcost healthcheck; não dependa de curl, shell ou gerenciador de pacotes na imagem final.

Compose: serviço app, imagem padrão cloudcost:local, porta 127.0.0.1:8080:8080, read_only, cap_drop [ALL], no-new-privileges, limites explícitos de CPU/memória/PIDs e política de reinício adequada. Não monte Docker socket, código, diretórios do host nem volumes de dados sem necessidade. O binário não requer escrita em disco. Evite privilégios e não exponha o serviço em 0.0.0.0 por padrão.

Permita CLOUDCOST_IMAGE apontar para uma imagem ACR por digest ao reproduzir uma release localmente. Esse caminho usa --no-build para não substituir o artefato verificado. Documente docker compose up --build -d --wait para demonstração local. Produção é Azure Container Apps e não usa Compose: consome o mesmo artefato da CI publicado no ACR por digest. Diferencie tag de commit (rastreável, mas mutável) de digest (identidade do conteúdo).

Defina como inspecionar usuário, rootfs read-only, capacidades, limites, mapeamento de porta e healthcheck; como parar; e como reverter para digest anterior aprovado. Não diga que scratch elimina CVEs: Go embutido, host, runtime e cadeia de build ainda têm riscos. Não execute checks concorrentes com implementação de outras partes; deixe a verificação integrada para o responsável designado.

Saída: arquivos finais e procedimentos locais, com pré-requisitos reais. Separe os controles de runtime do Compose dos campos efetivamente suportados pelo Azure Container Apps. HTTPS gerenciado, identidade AcrPull e infraestrutura Azure são definidos na etapa Azure; nunca os descreva como provisionados sem evidência.
```
