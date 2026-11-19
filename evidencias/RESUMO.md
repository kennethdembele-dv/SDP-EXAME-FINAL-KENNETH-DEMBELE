# Resumo das evidencias

Executado em 2026-11-19 03:07:50 (Docker Compose local, um computador). Cada linha indica a data da execucao no ficheiro do cenario.

| # | Cenario | Resultado | Verificacoes | Dois PCs |
|---|---|---|---|---|
| 0 | [Ambiente, rede, DNS e TLS](00_ambiente_rede_tls.md) | PASSOU | 8/8 |  |
| 1 | [Transferencia bem-sucedida entre Europa e America](01_transferencia_sucesso.md) | PASSOU | 8/8 | sim (ver nota) |
| 2 | [Saldo insuficiente e outras validacoes](02_saldo_insuficiente.md) | PASSOU | 9/9 |  |
| 3 | [Transferencias concorrentes sobre a mesma conta](03_concorrencia.md) | PASSOU | 7/7 |  |
| 4 | [Repeticao de um pedido com a mesma chave de idempotencia](04_idempotencia.md) | PASSOU | 8/8 |  |
| 5 | [Falha de um participante antes e durante a preparacao](05_falha_na_preparacao.md) | PASSOU | 9/9 | sim (ver nota) |
| 6 | [Falha durante a confirmacao e posterior recuperacao](06_falha_na_confirmacao.md) | PASSOU | 12/12 | sim (ver nota) |
| 7 | [Reinicio do coordenador com transaccoes pendentes](07_reinicio_coordenador.md) | PASSOU | 8/8 |  |
| 8 | [Queda de uma instancia da API e utilizacao da outra](08_queda_da_api.md) | PASSOU | 5/5 |  |
| 9 | [Token invalido ou expirado e acesso sem autorizacao](09_token_e_autorizacao.md) | PASSOU | 13/13 |  |
| 10 | [Mensagem de transferencia adulterada](10_mensagem_adulterada.md) | PASSOU | 7/7 |  |
| 11 | [Comunicacao entre Python e Java (XML sobre HTTPS)](11_python_java.md) | PASSOU | 10/10 |  |
| 12 | [Escrita e leitura dos ficheiros partilhados (NFS)](12_dfs_nfs.md) | PASSOU | 9/9 | sim (ver nota) |
| 99 | [Verificacao global de consistencia](99_invariantes.md) | PASSOU | 5/5 |  |
