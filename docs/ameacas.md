# Modelo de ameaças — CloudCost

## Escopo, ativos e pressupostos

A aplicação CloudCost calcula uma estimativa em USD com números fornecidos pelo visitante. Não faz compras nem provisiona recursos, consulta contas de nuvem, recebe credenciais ou persiste estimativas. A infraestrutura separada implanta essa aplicação na Azure. A IA foi ferramenta de criação do projeto, não um componente da arquitetura de execução.

Ativos a proteger: integridade do cálculo e da interface; disponibilidade do processo/plataforma; confidencialidade de eventuais informações que o visitante insira; integridade do código, ferramentas, imagem e relatórios; identidades de deployment/pull; permissões e orçamento da subscription Azure.

A demo local pressupõe host confiável, Docker atualizado e acesso em loopback. O destino de nuvem é Azure Container Apps Consumption com ACR privado, federação OIDC e identidade gerenciada de pull. O container não protege contra um administrador do host, da subscription ou do pipeline comprometido. Não há autenticação na app porque não há contas, recursos privados ou estado por usuário; qualquer mudança desse escopo exige nova análise.

## Fluxos e fronteiras de confiança

```text
Execução local:
[Navegador / entrada não confiável]
              | HTTP, 127.0.0.1:8080
              v
[Porta do host -> container app, UID 65532]
              | valida JSON e limites
              v
[Go: cálculo em memória] -> [JSON USD] -> [DOM textual]
              |
              +-- sem banco, chamadas cloud, cookies ou telemetria

Execução Azure, após provisionamento:
[Internet] -- HTTPS --> [ingress gerenciado Container Apps] -> [Go :8080]
                         TLS, escala, logs e plataforma são outra fronteira

Entrega:
[Autor / PR] -> [revisão + CloudCost CI] -> [imagem única + relatórios]
                                              | security-gate aprovado
                                              v
                                     [artefato cloudcost-image]
                                              | promoção manual / OIDC
                                              v
                                     [ACR privado / digest]
                                              | identidade AcrPull
                                              v
                                     [Azure Container Apps]
```

O build e os scanners precisam obter ferramentas/bases oficiais; a app não precisa dessas conexões durante o cálculo. GitHub OIDC permite a troca por credenciais temporárias na Azure; a identidade do deployment tem `Contributor` no resource group e `AcrPush` no ACR, enquanto a identidade gerenciada de pull tem apenas `AcrPull` no ACR. Credenciais não pertencem ao formulário. A configuração de ciclo de vida da identidade de pull não a oferece ao código da calculadora. Relatórios e logs têm acesso/retenção próprios. ACR privado significa autenticação/RBAC, não uma alegação de Private Link.

## Ameaças, mitigação e risco residual

Os impactos são qualitativos e orientam a revisão; não são probabilidades medidas nem resultado de pentest. “Controle” indica desenho/código/configuração disponível, não prova de eficácia. Execuções reais ficam em [evidências](evidencias.md).

| Ameaça / impacto | Caminho e controle no projeto | Risco residual e responsável |
| --- | --- | --- |
| Entrada ambígua, tipos errados ou números extremos alteram cálculo ou exaurem recursos | Parser em [estimate.go](../internal/estimate/estimate.go): campos obrigatórios, rejeição de null/desconhecidos/duplicados/JSON extra, faixas, corpo de 4096 bytes e expoente científico entre -4096 e 4096 antes da conversão numérica | Novas regras/campos podem reabrir ambiguidades; mantenedor deve preservar regressões e contrato. Limite de corpo não é rate limiting |
| XSS, interpretação de resposta ou clickjacking comprometem o navegador | Conteúdo estático embutido, renderização textual no [frontend](../internal/web/static/app.js), CSP `self` sem inline/CDN, `frame-ancestors 'none'`, `nosniff`, `no-referrer` em [handler.go](../internal/web/handler.go) | CSP não corrige toda falha de DOM ou navegador; revisão humana e navegador atualizado continuam necessários |
| Envio massivo ou conexões lentas causam indisponibilidade | Limite de corpo, timeouts no [servidor](../cmd/server/main.go), CPU/memória/PIDs no [Compose](../compose.yaml), limites de recursos/escala no [Bicep](../infra/azure/) | Um atacante ainda pode saturar limites e gerar tráfego/custos Azure. Escala limitada não equivale a rate limiting; o operador deve avaliar proteção de borda, capacidade e orçamento |
| Preços desatualizados ou semântica enganosa causam decisões financeiras incorretas | Interface explica preços de exemplo; categorias arredondadas a centavos, metade para cima; total soma categorias arredondadas; testes numéricos | Não inclui impostos, descontos, câmbio, reservas nem tarifas por faixa. Usuário deve conferir calculadora/contrato do provedor; não usar como fatura |
| Dados de estimativa, IP ou identificadores vazam em logs | Sem persistência da app nem logs de corpo/estimativa, cookies ou telemetria; respostas não precisam incluir entrada completa | Navegador, proxy, host e plataformas podem guardar metadados, dumps e IPs. Operador deve minimizar retenção/acesso e informar tratamento; ausência de banco não elimina LGPD |
| HTTP externo permite interceptação ou alteração | Bind loopback no Compose; ingress HTTPS Azure configurado no [Bicep](../infra/azure/) | Confirmar TLS/URL após provisionamento; a API deve ser chamada diretamente via HTTPS. Redirect não protege o primeiro pedido HTTP; HSTS não é presumido. Domínio personalizado tem configuração própria |
| Biblioteca padrão, compilador ou ferramenta comprometida injeta vulnerabilidade | Go e imagens/ferramentas fixados; biblioteca padrão incluída em govulncheck/Trivy/SBOM; [pins](../security/toolchain.md) e gates | `scratch` não remove CVEs do binário Go. Pins não provam confiabilidade original; bases podem estar incompletas e CVEs futuras exigem atualização/reexame |
| PR malicioso altera pipeline ou obtém privilégios Azure | Permissões mínimas, Actions fixadas, gate, validação da origem do artefato e deployment manual OIDC em environment restrito; [guia GitHub](github.md) | Quem controla workflow/branch/runner ou aprovação pode contornar controles. Administrador deve confirmar MFA, proteção de `main`/environment e revisão independente; OIDC sem senha não elimina comprometimento do pipeline |
| Imagem substituída entre exame e implantação | Build único, transporte do artefato examinado, publicação após gate, tag de commit para rastreio e implantação por `@sha256:` | Tag é mutável. Digest fixa conteúdo, não prova autoria nem segurança. Operador deve obter digest do run autorizado e conservar vínculo commit/relatórios/registry |
| Exploração da app escala privilégios ou escreve no host | Imagem mínima/UID 65532; localmente Compose define `read_only`, capabilities removidas e `no-new-privileges`, sem mounts de host/socket | Azure não herda flags Compose. Verificar somente controles suportados/configurados no Container Apps; kernel/plataforma e administração seguem responsabilidade compartilhada |
| Evidência ausente/desatualizada cria aprovação falsa | Relatórios por execução, erro de scanner bloqueante, [política](../security/POLICY.md), CI periódica, comando `--rescan` e job Azure agendado sobre o digest implantado | Rebuild não examina necessariamente a imagem implantada. Operador deve acompanhar runs/alertas; cron não prova execução. Rescan reutiliza identidade Contributor/AcrPush, não uma identidade dedicada somente de leitura |
| Federação ampla ou RBAC excessivo permite alterar recursos/exfiltrar imagens | OIDC restrito a repo/environment; identidades distintas para deployment e pull; papéis limitados a RG/ACR; admin do ACR desabilitado no [bootstrap](../scripts/azure-bootstrap.sh) | `Contributor` continua poderoso. O environment permite `main`, mas nesta entrega a exceção `--allow-no-reviewers` deixa aprovação independente não atestada. Proteger workflow/branch e revisar papéis/federação; credencial temporária ainda pode ser abusada |
| Abuso ou recursos esquecidos geram cobrança inesperada | Perfil Consumption e limites de escala; operação documenta autorização de custos e encerramento | ACR, armazenamento, logs e tráfego podem cobrar mesmo com app ociosa. Responsável pela subscription define orçamento/alertas, acompanha uso e remove recursos autorizados |

## Decisões de escopo

- Sem banco, upload, template definido pelo usuário, execução de shell a partir de entrada, URL de destino informada pelo visitante ou API cloud. SQL injection, upload executável e SSRF de funcionalidade não têm o respectivo caminho nesta versão; isso não é cobertura universal contra essas classes.
- Sem contas/sessões/ações privilegiadas. Não há cookies de autenticação para proteger, mas qualquer futura autenticação exige análise própria de sessão, autorização e CSRF. Requisições JSON/métodos restritos não são autenticação.
- HTTPS Azure é uma configuração a provisionar e confirmar, não resultado de rodar Compose. Proteção de borda, logs, revisão independente e gestão de acesso/retenção continuam decisões operacionais. Os guias de [operação](operacao.md) e [Azure](azure.md) explicitam os pré-requisitos e limites.
- Não há dados de aplicação para backup. Código, imagens aprovadas no ACR, digests, SBOM e evidências de release precisam ser preservados conforme política do operador; recuperação de identidades/infraestrutura e remoção de recursos têm procedimentos próprios.

## Quando rever este modelo

Reavalie antes de expor a app externamente, adicionar conta/persistência/telemetria/provedor, mudar toolchain ou publicação, e após incidente ou nova vulnerabilidade relevante. Registre decisão, responsável, evidência e risco aceito no processo de revisão; não aceite silenciosamente risco só para liberar um gate.

Referências primárias: [OWASP — Threat Modeling](https://owasp.org/www-community/Threat_Modeling), [OWASP ASVS 5.0](https://asvs.owasp.org/), [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final), [Docker — segurança do daemon](https://docs.docker.com/engine/security/), [Azure — ingress](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview), [Azure — OIDC](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect).
