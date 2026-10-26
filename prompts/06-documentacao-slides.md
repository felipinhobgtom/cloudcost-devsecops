# 06 — Documentar e apresentar a entrega

Prompt reutilizável reconstruído. Entrada: arquivos implementados, fontes oficiais, URL real confirmada e resultados efetivamente disponíveis.

```text
Documente CloudCost em português para uma pessoa conseguir entender, executar, analisar e apresentar o projeto sem conhecer a conversa original. Use os arquivos reais como fonte e não invente comandos, outputs, imagens de execução, badges ou URLs publicadas.

README: objetivo e aviso de estimativa, arquitetura, requisitos, quickstart Docker local, deployment Azure Container Apps/ACR, uso e contrato da API, fluxo de segurança, localização dos relatórios, prompts e apresentação. Explique que IA foi usada para criar o deployment e não é consumida pela aplicação.

Guias: docs/operacao.md deve incluir build local, healthcheck, inspeção, desligamento, implantação Azure do artefato aprovado por digest, rollback e pré-requisitos de operação. docs/azure.md detalha Bicep, bootstrap, custos, OIDC, ACR privado, identidade gerenciada AcrPull e HTTPS padrão Azure. docs/github.md orienta uso do repositório existente, main com security-gate obrigatório, revisão, permissões restritas, environment azure-production e acesso aos artefatos sem revelar tokens. SECURITY.md precisa oferecer caminho de relato utilizável também numa cópia local/não publicada, sem inventar email ou prometer SLA. CHANGELOG.md registra criação sem dizer que testes passaram se não foram observados.

Crie uma apresentação com pelo menos cinco slides, texto legível, imagens reais do projeto ou diagramas originais identificados como diagramas, textos alternativos e URLs de fontes primárias. Inclua problema/objetivo, arquitetura Azure, Docker local versus Container Apps, pipeline DevSecOps/ACR/OIDC, ameaças/conformidade, demonstração/limites e conclusão. Se usar screenshot, capture uma execução verdadeira; se não houver execução, não simule uma screenshot. Não use mídia remota obrigatória para a apresentação funcionar offline.

Arquive prompts numerados reutilizáveis de escopo, app, container, CI, análise, documentação e refinamento Azure. prompts/README.md deve mapear intenção do usuário, entradas, saídas e verificação humana. Declare que são reconstruções dos requisitos, não transcrição literal de todas as mensagens nem prova de execução verbatim.

Referências: use OWASP ASVS 5.0.0, NIST SSDF 1.1, LGPD, documentação oficial de Go, Docker, GitHub e Microsoft Learn. Qualquer URL de projeto deve vir de um remoto realmente confirmado; obtenha a URL da app somente dos outputs Azure reais. Distingua repositório criado, código enviado, workflow configurado/executado, imagem no ACR e Container Apps acessível por HTTPS; cada estado exige evidência própria.

Saída: documentação coerente com os arquivos finais, apresentação navegável e arquivo de prompts rastreável. Informe o que permanece responsabilidade humana sem transformar pré-requisito de produção em promessa de deploy cloud realizado.
```
