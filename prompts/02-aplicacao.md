# 02 — Implementar aplicação e contrato verificável

Prompt reutilizável reconstruído. Entrada: escopo acordado, árvore atual e convenções existentes.

```text
Implemente CloudCost em Go usando apenas a biblioteca padrão em runtime, módulo cloudcost e entrypoint ./cmd/server. Embuta HTML, CSS e JavaScript no binário. A interface deve ser em português, acessível por labels, teclado e mensagens de erro claras. Use scripts e folhas de estilo locais externos ao HTML, sem inline, CDN, cookies ou telemetria.

API:
- GET /healthz retorna JSON {"status":"ok"}.
- POST /api/estimate exige application/json e exatamente estes campos obrigatórios: instances (inteiro 0..10000), hours_per_month (0..744), hourly_rate (0..1000), storage_gb (0..1000000), storage_rate (0..1000), egress_gb (0..1000000), egress_rate (0..1000).
- Rejeite campo ausente, null, desconhecido, duplicado, tipo incompatível, número inválido, negativo ou fora de faixa, corpo maior que 4096 bytes e JSON extra após o objeto. Antes da conversão exata, limite expoente científico a -4096..4096; o limite do corpo restringe a quantidade de dígitos, sem truncar casas decimais. Validação da UI não substitui validação no servidor.
- compute = instances * hours_per_month * hourly_rate; storage = storage_gb * storage_rate; egress = egress_gb * egress_rate. Respostas em USD, com aritmética decimal exata e arredondamento de meio centavo para cima por categoria; total soma as categorias arredondadas. Não apresente isso como precisão de cobrança de provedor.
- Exemplo: {"instances":1,"hours_per_month":720,"hourly_rate":0.1,"storage_gb":100,"storage_rate":0.1,"egress_gb":50,"egress_rate":0.1} produz {"compute":72,"storage":10,"egress":5,"total":87,"currency":"USD"}.
- Erros JSON {"error":"..."}; status 400 para validação, 413 para corpo grande, 415 para mídia, 405 para método não suportado, sem vazar stack trace ou conteúdo do pedido.

A aplicação deve escutar :8080 por padrão, admitir PORT válido e ter subcomando /cloudcost healthcheck, que consulta http://127.0.0.1:$PORT/healthz com timeout e falha com código não zero quando indisponível. Configure timeouts HTTP e desligamento gracioso. Não invoque shell, consulte URLs do usuário nem registre corpos/dados de estimativa.

Cabeçalhos: CSP com script-src/style-src 'self', object-src 'none', base-uri 'none', frame-ancestors 'none'; X-Content-Type-Options: nosniff; Referrer-Policy: no-referrer; Permissions-Policy restritiva. TLS termina no ingress gerenciado do Azure Container Apps em produção, não no binário Go. Exposição HTTPS real precisa ser verificada após provisionamento. Não abra CORS permissivo sem necessidade.

Inclua testes do exemplo, zeros, limites, arredondamento, campos faltantes/null/duplicados/desconhecidos, tipos errados, valores fora de faixa, mídia/métodos, JSON extra, corpo grande, cabeçalhos e healthcheck. Prefira renderização textual segura no frontend, nunca innerHTML com entrada do usuário. Explique testes criados separadamente de testes executados.

Saída: arquivos completos, contrato preservado, limitações e comandos de verificação para o integrador. Não adicione dependência de IA, autenticação, armazenamento ou consumo de APIs cloud à aplicação; o deployment Azure pertence à infraestrutura.
```
