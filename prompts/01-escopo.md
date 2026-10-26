# 01 — Definir escopo e critérios de aceitação

Prompt reutilizável reconstruído; não é registro literal de execução. Cole o texto abaixo junto com o diretório autorizado e o estado atual do repositório.

```text
Você é responsável por criar um projeto educacional completo em português usando IA como ferramenta de engenharia. Não crie um aplicativo que chama IA. Antes de editar, leia os arquivos existentes, preserve alterações do usuário e proponha um plano com interfaces e responsabilidades.

Objetivo: entregar CloudCost, uma calculadora web stateless de custo mensal de computação, armazenamento e saída de dados. Os preços são exemplos informados pelo usuário, não preços atuais de um provedor. A aplicação não provisiona nuvem, não solicita credenciais, não autentica usuários e não persiste estimativas. Não inclua banco, telemetria, cookies ou serviços pagos sem necessidade.

Stack acordada: Go, somente biblioteca padrão em runtime; HTML/CSS/JavaScript sem dependências externas embutidos no binário. Module cloudcost; go.mod mínimo 1.26.0, builder e CI 1.27.3. Confirme versões oficiais antes de uma futura atualização e altere todos os pins de modo consistente. Entrypoint ./cmd/server; binário /cloudcost; porta 8080 por padrão via PORT; healthcheck por subcomando do próprio binário.

Entregue aplicação funcional, testes, Dockerfile multi-stage, Compose local endurecido, CI com gates de segurança, SBOM, infraestrutura Azure em Bicep, ACR privado, Azure Container Apps Consumption por digest e autenticação GitHub OIDC sem senha Azure armazenada. Transfira a mesma imagem verificada da CI ao ACR sem rebuild. Inclua procedimentos de atualização/rollback, análise parcial de conformidade, modelo de ameaças, SECURITY.md, changelog, arquivo de prompts e apresentação de pelo menos cinco slides com imagens e URLs de fontes primárias.

Critérios: execução local em 127.0.0.1:8080; POST /api/estimate com contrato estrito; resultado USD 87 para 1 instância, 720 horas, tarifa 0.1, 100 GB de armazenamento a 0.1 e 50 GB de saída a 0.1; healthcheck operacional; Compose não root/read-only/cap_drop ALL/no-new-privileges/limites; imagem liberada somente após gates; Azure Container Apps usando digest imutável e identidade gerenciada AcrPull no ACR; domínio HTTPS gerenciado da Azure. Não prometa no Container Apps controles de Compose que a API Azure não oferece. Documentação distingue HTTP local, infraestrutura configurada e provisionamento comprovado.

Explicite limites: não é calculadora de faturamento exato, não consulta preços ao vivo, não inclui impostos, descontos, câmbio ou faixas comerciais. OWASP ASVS 5.0 e NIST SSDF são referências parciais, não certificações. LGPD exige avaliação da operação, inclusive logs/IPs de proxy/host.

Use somente URL de repositório confirmada. Não invente execuções, resultados de scanners, deploy cloud, screenshots de aplicação não executada ou publicação. Antes de criar recursos cobrados, obtenha autorização e confirme subscription/permissões. Se ferramentas/acessos faltarem, documente exatamente o que é configurado e o que ainda não foi verificado; não entregue mock como execução real.

Saída: plano curto, contratos, mapa dos arquivos e critérios verificáveis. Depois implemente o escopo aprovado sem acrescentar funcionalidades alheias. Nunca exponha segredos nos prompts ou arquivos.
```
