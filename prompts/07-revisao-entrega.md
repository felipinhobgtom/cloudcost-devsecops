# 07 — Revisar, verificar e entregar com evidência

Prompt reutilizável reconstruído. **Este prompt autoriza verificações somente quando o responsável pela integração o executar em uma nova etapa autorizada**; sua presença no arquivo não significa que os comandos foram executados.

```text
Você é o integrador autorizado do CloudCost. Espere todas as alterações de aplicação, deployment, documentação e apresentação terminarem. Faça uma rodada integrada de verificações em vez de vários builds/testes concorrentes sobre arquivos incompletos. Não publique nem altere o ambiente remoto sem a autorização correspondente.

Leia os scripts e a política antes de executá-los. Confira Go, Docker Engine/Compose, Python e ferramentas de análise requeridas; registre versões reais. Execute a entrada de verificação acordada, bash scripts/security-checks.sh, e os testes de UI/apresentação que ela não cobre. Verifique API positiva e negativa, headers, estado healthy, usuário não root, rootfs somente leitura, capacidades, limites, porta loopback e navegação acessível. Não desabilite um gate para produzir sucesso.

Verifique que os relatórios se referem ao commit e à imagem efetivamente examinados. Correlacione run aprovado de main, artefato cloudcost-image, source_image_id, config_digest, loaded_image_id, cadeia configuração/rootfs, tag no ACR e digest implantado no Container Apps; confirme que deploy-azure.yml não reconstrói. Não exija igualdade indevida entre ID de índice OCI, digest de configuração e ID após docker load. Para OIDC, confirme claims padrão e derive o subject do sub_claim_prefix da API GitHub real, não de um formato legado presumido. Se CI remoto ou deployment não executou, diga isso mesmo que verificações locais tenham passado.

Confira links locais de documentação/apresentação, pelo menos cinco slides, imagens/URLs, prompts e ausência de segredos. Revise exemplos de comandos para evitar que usem tag mutável em produção, token na linha de comando ou bind público por acidente. Separe testes criados de testes realmente executados.

Em docs/evidencias.md, registre data UTC, comandos, versões, escopo, commit/digest quando disponível, status e localização dos relatórios. Um erro de rede/base de CVEs/daemon é execução bloqueada, não resultado limpo. Se houver vulnerabilidade, registre achado/severidade/impacto e encaminhe correção; não invente falsos positivos nem ignore sem justificativa revisada.

Se autorizado a enviar ao GitHub, use o repositório real confirmado, sem sobrescrever histórico. Depois da CI, documente IDs/URLs reais dos runs. Somente com subscription, permissões e custo autorizados, execute o bootstrap e o workflow Azure; registre azure-evidence/deployment.json, endpoint.json, digest e resultado HTTPS da URL verdadeira. Informe controles manuais pendentes: main e environment protegidos, revisão, RBAC, orçamento, logs/privacidade e monitoramento. Não reivindique certificação, ausência absoluta de falhas nem deployment cloud que não aconteceu.

Entregue um resumo factual: o que foi criado, como executar, o que foi exercitado, o que falhou/não foi executado e riscos residuais. Uma pessoa responsável deve revisar a aceitação antes de exposição pública.
```
