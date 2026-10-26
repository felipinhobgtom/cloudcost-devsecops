# CloudCost — implantação na Azure com DevSecOps

Calculadora web de estimativas mensais de infraestrutura: computação, armazenamento e transferência de dados. O usuário informa quantidades e preços; a aplicação calcula os custos em USD. Não consulta preços de provedores nem substitui uma fatura.

**A IA auxilia a criação deste projeto; a aplicação não consome IA.** Não há SDK de modelo, chamada a serviço de IA, chave de API, banco de dados, cookies ou telemetria. O backend utiliza somente a biblioteca padrão de Go; a interface é HTML, CSS e JavaScript local.

- Repositório: <https://github.com/felipinhobgtom/cloudcost-devsecops> — privado; acesso depende de permissão.
- Acervo de prompts: [arquivos locais](prompts/README.md) · [GitHub](https://github.com/felipinhobgtom/cloudcost-devsecops/tree/main/prompts).
- Apresentação: **9 slides** com texto, diagramas e URLs — [HTML navegável](presentation/index.html) · [PDF](presentation/cloudcost-devsecops.pdf).
- Resultado das verificações: [evidências e limites](docs/evidencias.md).

## Implantação na Azure

O destino de nuvem é **Azure Container Apps**, com plano Consumption, HTTPS e escalabilidade de zero a duas réplicas. A imagem fica no **Azure Container Registry** privado; a aplicação a obtém com identidade gerenciada. O GitHub Actions usa **OpenID Connect (OIDC)** para promover a imagem aprovada pelos controles DevSecOps, sem senha de Azure no repositório.

A infraestrutura declarativa está em [`infra/`](infra/). O procedimento de provisionamento, autenticação, entrega por digest e remoção dos recursos está em [docs/azure.md](docs/azure.md). São necessários uma assinatura Azure ativa e privilégios de provisionamento/RBAC. **ACR e uso de nuvem podem gerar cobrança; revise os preços e autorize a criação antes de executar.**

O [registro de evidências](docs/evidencias.md) distingue a preparação da infraestrutura da implantação efetivamente executada. Docker Compose abaixo é o ambiente local de desenvolvimento e verificação, não um substituto da Azure.

## Executar localmente

Pré-requisitos: Docker Engine e Docker Compose. A primeira compilação precisa de acesso ao Docker Hub. Para este modo local, não são necessárias credenciais de nuvem.

```sh
docker compose up --build -d --wait
```

Abra **http://127.0.0.1:8080**. A porta fica acessível apenas na máquina local, intencionalmente. A opção `--wait` exige que o healthcheck esteja saudável.

```sh
curl --fail http://127.0.0.1:8080/healthz

docker compose logs app
# Encerrar a implantação:
docker compose down
```

Para desenvolvimento sem Docker:

```sh
GOTOOLCHAIN=go1.27.3 go run ./cmd/server
```

Não execute as duas opções simultaneamente na mesma porta. O servidor aceita a variável `PORT`, com padrão `8080`.

## Exemplo de cálculo pela API

```sh
curl --fail-with-body http://127.0.0.1:8080/api/estimate \
  -H 'Content-Type: application/json' \
  --data '{"instances":1,"hours_per_month":720,"hourly_rate":0.1,"storage_gb":100,"storage_rate":0.1,"egress_gb":50,"egress_rate":0.1}'
```

Resultado esperado: `compute=72`, `storage=10`, `egress=5`, `total=87`, `currency="USD"`. Os preços são exemplos informados pelo usuário; o cálculo arredonda componentes para centavos. Todos os campos são obrigatórios, com limites explícitos e rejeição de entradas inválidas.

## Segurança como condição de entrega

O projeto separa três responsabilidades:

1. **Aplicação:** validação de entradas, limite de corpo, timeouts, CSP e outros cabeçalhos de segurança; sem persistência dos valores informados.
2. **Implantação:** imagem mínima e usuário sem privilégios. Localmente, Compose acrescenta sistema de arquivos somente leitura, capacidades removidas e healthcheck. Na Azure, os controles declarados são HTTPS, probes, recursos limitados e identidades gerenciadas; não se presume equivalência com todas as flags locais.
3. **Entrega:** análise estática, dependências/toolchain, segredos, imagem e configuração; verificações HTTP e evidências antes da publicação da imagem.

O pipeline está em [`.github/workflows/`](.github/workflows/). Publicar código não significa que o pipeline passou: consulte a execução no [GitHub Actions](https://github.com/felipinhobgtom/cloudcost-devsecops/actions) e o [registro de evidências](docs/evidencias.md).

**Não há promessa de “zero vulnerabilidades” nem certificação automática.** As análises têm escopo, data e limitações. O modo local HTTP não deve ser exposto à Internet: uma implantação pública exige HTTPS, proteção da borda, gestão de acesso e avaliação operacional. Veja [operação](docs/operacao.md), [modelo de ameaças](docs/ameacas.md) e [conformidade](docs/conformidade.md).

### Executar os controles locais

Pré-requisitos adicionais: Go, Python 3 e Git. O script baixa ferramentas fixadas e bases de vulnerabilidades, portanto requer Internet:

```sh
bash scripts/security-checks.sh
```

São executados testes/vet, **gosec**, **govulncheck**, **Gitleaks**, **Trivy**, geração de **SBOM CycloneDX** e verificações HTTP sobre o contêiner real. Qualquer finding bloqueante ou erro de ferramenta impede aprovação; não há exclusão geral de vulnerabilidades sem correção disponível.

O índice fica em `reports/latest.json`, com relatórios datados no diretório indicado. `reports/` não é versionado; o CI preserva os resultados como artifacts. O job agregado `security-gate` precisa passar antes de promover a imagem. O workflow Azure recebe o ID de uma CI aprovada em `push` de `main` e implanta **o mesmo artefato**, sem recompilar.

## Material para entrega e apresentação

| Entrega | Local |
| --- | --- |
| Aplicação e API | `cmd/server/`, `internal/` |
| Contêiner e implantação | `Dockerfile`, `compose.yaml` |
| Infraestrutura Azure e identidade | `infra/azure/`, `scripts/azure-*.sh`, [guia Azure](docs/azure.md) |
| Automação DevSecOps | `.github/`, `scripts/`, `security/` |
| Conformidade, ameaças e operação | `docs/` |
| Acervo de prompts reutilizáveis | `prompts/` |
| Slides com texto, imagens locais e URLs | `presentation/` |
| Política de segurança | [SECURITY.md](SECURITY.md) |
| Histórico de mudanças | [CHANGELOG.md](CHANGELOG.md) |

Para servir a apresentação localmente, a partir da raiz do projeto:

```sh
python3 -m http.server 8090 --bind 127.0.0.1
```

Abra http://127.0.0.1:8090/presentation/. O PDF pode ser aberto diretamente, sem servidor. A publicação no GitHub, os controles de revisão e o acesso ao registro de imagens são explicados em [docs/github.md](docs/github.md).

## Referências

- OWASP ASVS 5.0: <https://asvs.owasp.org/>
- NIST Secure Software Development Framework: <https://csrc.nist.gov/pubs/sp/800/218/final>
- Segurança do GitHub Actions: <https://docs.github.com/en/actions/security-for-github-actions>
- Segurança do Docker: <https://docs.docker.com/engine/security/>
- LGPD, texto legal: <https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm>
