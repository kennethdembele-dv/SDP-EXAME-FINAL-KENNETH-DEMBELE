# Reproducao a partir de uma instalacao limpa

Executada em 2026-11-19, no Windows 10 Pro 22H2 com Docker Desktop 4.99 (backend Hyper-V, VM com 2 GB e 2 CPUs),
Docker 29.9.3 e Compose v5.7.0. O resultado desta execucao esta na tabela abaixo. Os ficheiros de cenario desta pasta sao de uma execucao posterior, igual, feita com uma janela por cenario para as capturas de ecra do relatorio.

## Procedimento (o mesmo do README)

```
git clone <repositorio> gs-limpo            # clone novo: 4634bae Evidencias reais em Docker: 13 cenarios e verificacao global passam
cd gs-limpo
python seguranca/gerar_materiais.py         # CA, certificados, chaves e .env NOVOS
docker compose up -d --build                # 9 contentores
docker compose ps                           # 9 de 9 healthy
python testes/cenarios.py                   # 13 cenarios + verificacao global
```

## Resultado

- `docker compose up -d --build`: codigo 0; os 9 contentores ficaram `healthy`.
- `python testes/cenarios.py`: codigo 0; todos os cenarios PASSOU numa unica execucao seguida (ver RESUMO.md).
- Os segredos foram gerados de novo no clone: nada do computador de desenvolvimento foi reutilizado alem do codigo.

## Contentores no fim da execucao

```
NAME                            STATUS
global-scale-api-1-1            Up 2 minutes (healthy)
global-scale-api-2-1            Up 6 minutes (healthy)
global-scale-auth-1             Up 2 minutes (healthy)
global-scale-banco-parceiro-1   Up About a minute (healthy)
global-scale-coordenador-1      Up 2 minutes (healthy)
global-scale-db-america-1       Up 4 minutes (healthy)
global-scale-db-coordenador-1   Up 6 minutes (healthy)
global-scale-db-europa-1        Up 5 minutes (healthy)
global-scale-nfs-1              Up 59 seconds (healthy)
```

## Resultado de cada cenario nesta execucao (clone limpo, 2026-11-19 02:27)

| # | Cenario | Resultado | Verificacoes | Dois PCs |
|---|---|---|---|---|
| 0 | Ambiente, rede, DNS e TLS | PASSOU | 8/8 |  |
| 1 | Transferencia bem-sucedida entre Europa e America | PASSOU | 8/8 | sim (ver nota) |
| 2 | Saldo insuficiente e outras validacoes | PASSOU | 9/9 |  |
| 3 | Transferencias concorrentes sobre a mesma conta | PASSOU | 7/7 |  |
| 4 | Repeticao de um pedido com a mesma chave de idempotencia | PASSOU | 8/8 |  |
| 5 | Falha de um participante antes e durante a preparacao | PASSOU | 9/9 | sim (ver nota) |
| 6 | Falha durante a confirmacao e posterior recuperacao | PASSOU | 12/12 | sim (ver nota) |
| 7 | Reinicio do coordenador com transaccoes pendentes | PASSOU | 8/8 |  |
| 8 | Queda de uma instancia da API e utilizacao da outra | PASSOU | 5/5 |  |
| 9 | Token invalido ou expirado e acesso sem autorizacao | PASSOU | 13/13 |  |
| 10 | Mensagem de transferencia adulterada | PASSOU | 7/7 |  |
| 11 | Comunicacao entre Python e Java (XML sobre HTTPS) | PASSOU | 10/10 |  |
| 12 | Escrita e leitura dos ficheiros partilhados (NFS) | PASSOU | 9/9 | sim (ver nota) |
| 99 | Verificacao global de consistencia | PASSOU | 5/5 |  |
