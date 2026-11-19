# Cenario 12: Escrita e leitura dos ficheiros partilhados (NFS)

**Resultado: PASSOU** (9/9 verificacoes, 15.1 s, executado em 2026-11-19 03:07:48)

**Objectivo:** api-1 escreve um relatorio no NFS e api-2 le-o; os eventos de auditoria de varios servicos ficam no mesmo DFS; com o NFS em baixo os eventos ficam em espera e sao publicados depois.

**Dois computadores:** Com dois PCs, o servidor NFS esta no PC A e o api-2 do PC B monta-o pela rede.

## Procedimento executado

1. `03:07:35` api-1: POST /api/v1/relatorios/extracto (EU-1001)
2. `03:07:35` api-2: GET /api/v1/relatorios/EU-1001_20261119T010735Z_api-1.csv
3. `03:07:36` Falha do DFS: docker compose stop nfs; nova transferencia
4. `03:07:41` docker compose start nfs; esperar que os eventos sejam publicados

## Montagens de /mnt/dfs (/proc/mounts)

```
api-1: :/dfs /mnt/dfs nfs4 rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,soft,fatal_neterrors=none,proto=tcp,timeo=50,retrans=2,sec=sys,clientaddr=172.30.2.1,local_lock=none,addr=172.30.2.40 0 0
api-2: :/dfs /mnt/dfs nfs4 rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,soft,fatal_neterrors=none,proto=tcp,timeo=50,retrans=2,sec=sys,clientaddr=172.30.2.1,local_lock=none,addr=172.30.2.40 0 0
coordenador: :/dfs /mnt/dfs nfs4 rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,soft,fatal_neterrors=none,proto=tcp,timeo=50,retrans=2,sec=sys,clientaddr=172.30.2.1,local_lock=none,addr=172.30.2.40 0 0
```

## Relatorio escrito por api-1 e lido por api-2

```
{'nome': 'EU-1001_20261119T010735Z_api-1.csv', 'caminho_dfs': '/mnt/dfs/relatorios/EU-1001_20261119T010735Z_api-1.csv', 'escrito_por': 'api-1', 'movimentos': 5}

lido por api-2:
conta,titular,saldo_actual,gerado_por
EU-1001,ana,4840.50,api-1

data,tipo,montante,saldo_apos,contraparte,transferencia_id
2026-11-19T01:06:38.724221+00:00,DEBITO,1.00,4840.50,US-2001,22cd0e0d-f6fd-4b4a-a2be-49b76a76d61e
2026-11-19T01:05:48.962130+00:00,DEBITO,5.00,4841.50,US-2001,cc6f1627-cd8b-46d0-9edc-f52816c7a6e8
2026-11-19T01:04:13.995618+00:00,DEBITO,8.00,4846.50,US-2001,e12f62f8-f6d6-481b-a369-550bbd6a5d89
2026-11-19T01:03:27.092279+00:00,DEBITO,20.00,4854.50,US-2001,ab96e04a-ec39-4725-8b8b-37aadbfbeda7
2026-11-19T01:01:33.806185+00:00,DEBITO,125.50,4874.50,US-2001,2b560500-48c7-4e65-8

No disco do servidor NFS:
total 4
-rw-r--r-- 1 root root 626 Nov 19 01:07 EU-1001_20261119T010735Z_api-1.csv
```

## Auditoria da transferencia do cenario 1, lida por api-2

```
2026-11-19T01:01:33.730+00:00  coordenador  INICIADA               REGISTADA  (2026-11-19/20261119T010133730196Z_2b560500-48c7-4e65-8450-70bc3ea6db96_coordenador_INICIADA_ca2850.json)
2026-11-19T01:01:33.913+00:00  coordenador  PREPARADO              europa: PREPARE TRANSACTION 'gs-2b560500-48c7-4e65-8450-70bc  (2026-11-19/20261119T010133913491Z_2b560500-48c7-4e65-8450-70bc3ea6db96_coordenador_PREPARADO_5cb3b5.json)
2026-11-19T01:01:34.098+00:00  coordenador  PREPARADO              america: PREPARE TRANSACTION 'gs-2b560500-48c7-4e65-8450-70b  (2026-11-19/20261119T010134098688Z_2b560500-48c7-4e65-8450-70bc3ea6db96_coordenador_PREPARADO_adcd77.json)
2026-11-19T01:01:34.197+00:00  coordenador  DECISAO_COMMIT         COMMIT  (2026-11-19/20261119T010134197111Z_2b560500-48c7-4e65-8450-70bc3ea6db96_coordenador_DECISAO_COMMIT_5a8050.json)
2026-11-19T01:01:34.461+00:00  coordenador  CONFIRMADO             america: COMMIT PREPARED 'gs-2b560500-48c7-4e65-8450-70bc3ea  (2026-11-19/20261119T010134461735Z_2b560500-48c7-4e65-8450-70bc3ea6db96_coordenador_CONFIRMADO_071614.json)
2026-11-19T01:01:34.516+00:00  coordenador  CONFIRMADO             europa: COMMIT PREPARED 'gs-2b560500-48c7-4e65-8450-70bc3ea6  (2026-11-19/20261119T010134516870Z_2b560500-48c7-4e65-8450-70bc3ea6db96_coordenador_CONFIRMADO_0f51b5.json)
2026-11-19T01:01:34.629+00:00  coordenador  CONCLUIDA              decisao aplicada em todos os participantes  (2026-11-19/20261119T010134629663Z_2b560500-48c7-4e65-8450-70bc3ea6db96_coordenador_CONCLUIDA_abd73e.json)
2026-11-19T01:01:34.778+00:00  api-1        ORDEM_ENVIADA          CONCLUIDA  (2026-11-19/20261119T010134778082Z_2b560500-48c7-4e65-8450-70bc3ea6db96_api-1_ORDEM_ENVIADA_9cfdfb.json)
2026-11-19T01:01:35.794+00:00  coordenador  PARCEIRO_CONFIRMOU     referencia BP-000001 (HTTP 201)  (2026-11-19/20261119T010135794342Z_2b560500-48c7-4e65-8450-70bc3ea6db96_coordenador_PARCEIRO_CONFIRMOU_9c4114.json)
```

## Ficheiros de auditoria no servidor NFS (um ficheiro por evento)

```
ficheiros: 207
temporarios: 0
api-1: 21
api-2: 9
coordenador: 177
```

## Eventos da transferencia feita com o NFS em baixo, ja no DFS

```
20261119T010737251223Z_470fa145-4a04-45b1-8f91-07ad7230e369_coordenador_INICIADA_c0c070.json
20261119T010737422534Z_470fa145-4a04-45b1-8f91-07ad7230e369_coordenador_PREPARADO_7f6c83.json
20261119T010737548006Z_470fa145-4a04-45b1-8f91-07ad7230e369_coordenador_PREPARADO_9140a1.json
20261119T010737647190Z_470fa145-4a04-45b1-8f91-07ad7230e369_coordenador_DECISAO_COMMIT_48a237.json
20261119T010737915579Z_470fa145-4a04-45b1-8f91-07ad7230e369_coordenador_CONFIRMADO_963229.json
20261119T010737953448Z_470fa145-4a04-45b1-8f91-07ad7230e369_coordenador_CONFIRMADO_e3fc37.json
20261119T010738099242Z_470fa145-4a04-45b1-8f91-07ad7230e369_coordenador_CONCLUIDA_c0fef8.json
20261119T010738203754Z_470fa145-4a04-45b1-8f91-07ad7230e369_api-1_ORDEM_ENVIADA_fc6348.json
20261119T010738399160Z_470fa145-4a04-45b1-8f91-07ad7230e369_coordenador_PARCEIRO_CONFIRMOU_6533a5.json
```

## Verificacoes

- [x] os tres servicos montam /mnt/dfs por nfs4 a partir de 172.30.2.40
- [x] escrito por api-1 e lido por api-2 (transparencia de localizacao)
- [x] o ficheiro esta no disco do servidor NFS
- [x] eventos escritos por servicos diferentes (api-1 e coordenador) no mesmo DFS
- [x] cada evento tem id da transferencia, data UTC, servico e resultado
- [x] nenhum ficheiro incompleto (.tmp) no DFS
- [x] com o NFS em baixo a transferencia conclui (HTTP 201)
- [x] eventos guardados na pasta de espera local do coordenador (8)
- [x] os eventos foram publicados no DFS depois de o NFS voltar
