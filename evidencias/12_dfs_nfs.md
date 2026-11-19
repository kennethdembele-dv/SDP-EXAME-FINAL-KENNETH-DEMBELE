# Cenario 12: Escrita e leitura dos ficheiros partilhados (NFS)

**Resultado: PASSOU** (9/9 verificacoes, 15.1 s, executado em 2026-11-19 02:18:31)

**Objectivo:** api-1 escreve um relatorio no NFS e api-2 le-o; os eventos de auditoria de varios servicos ficam no mesmo DFS; com o NFS em baixo os eventos ficam em espera e sao publicados depois.

**Dois computadores:** Com dois PCs, o servidor NFS esta no PC A e o api-2 do PC B monta-o pela rede.

## Procedimento executado

1. `02:18:18` api-1: POST /api/v1/relatorios/extracto (EU-1001)
2. `02:18:18` api-2: GET /api/v1/relatorios/EU-1001_20261119T001818Z_api-1.csv
3. `02:18:19` Falha do DFS: docker compose stop nfs; nova transferencia
4. `02:18:24` docker compose start nfs; esperar que os eventos sejam publicados

## Montagens de /mnt/dfs (/proc/mounts)

```
api-1: :/dfs /mnt/dfs nfs4 rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,soft,fatal_neterrors=none,proto=tcp,timeo=50,retrans=2,sec=sys,clientaddr=172.30.2.1,local_lock=none,addr=172.30.2.40 0 0
api-2: :/dfs /mnt/dfs nfs4 rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,soft,fatal_neterrors=none,proto=tcp,timeo=50,retrans=2,sec=sys,clientaddr=172.30.2.1,local_lock=none,addr=172.30.2.40 0 0
coordenador: :/dfs /mnt/dfs nfs4 rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,soft,fatal_neterrors=none,proto=tcp,timeo=50,retrans=2,sec=sys,clientaddr=172.30.2.1,local_lock=none,addr=172.30.2.40 0 0
```

## Relatorio escrito por api-1 e lido por api-2

```
{'nome': 'EU-1001_20261119T001818Z_api-1.csv', 'caminho_dfs': '/mnt/dfs/relatorios/EU-1001_20261119T001818Z_api-1.csv', 'escrito_por': 'api-1', 'movimentos': 5}

lido por api-2:
conta,titular,saldo_actual,gerado_por
EU-1001,ana,4840.50,api-1

data,tipo,montante,saldo_apos,contraparte,transferencia_id
2026-11-19T00:17:38.421663+00:00,DEBITO,1.00,4840.50,US-2001,d96fed09-de03-4bee-af35-cfad084f12da
2026-11-19T00:17:02.852126+00:00,DEBITO,5.00,4841.50,US-2001,7d6d42c3-6c02-48df-831a-70688d76239b
2026-11-19T00:15:42.552482+00:00,DEBITO,8.00,4846.50,US-2001,07477465-e8cc-4a01-8adf-ce8c7bc59a4e
2026-11-19T00:14:54.442613+00:00,DEBITO,20.00,4854.50,US-2001,8ca334da-7f8c-49a0-a7ff-a9fbf0c8f4da
2026-11-19T00:13:36.324540+00:00,DEBITO,125.50,4874.50,US-2001,05948f69-7ede-4341-8

No disco do servidor NFS:
total 4
-rw-r--r-- 1 root root 626 Nov 19 00:18 EU-1001_20261119T001818Z_api-1.csv
```

## Auditoria da transferencia do cenario 1, lida por api-2

```
2026-11-19T00:13:36.235+00:00  coordenador  INICIADA               REGISTADA  (2026-11-19/20261119T001336235200Z_05948f69-7ede-4341-82e2-bfd2846bd6de_coordenador_INICIADA_e0a607.json)
2026-11-19T00:13:36.421+00:00  coordenador  PREPARADO              europa: PREPARE TRANSACTION 'gs-05948f69-7ede-4341-82e2-bfd2  (2026-11-19/20261119T001336421191Z_05948f69-7ede-4341-82e2-bfd2846bd6de_coordenador_PREPARADO_1bf3f2.json)
2026-11-19T00:13:36.553+00:00  coordenador  PREPARADO              america: PREPARE TRANSACTION 'gs-05948f69-7ede-4341-82e2-bfd  (2026-11-19/20261119T001336553126Z_05948f69-7ede-4341-82e2-bfd2846bd6de_coordenador_PREPARADO_227baf.json)
2026-11-19T00:13:36.650+00:00  coordenador  DECISAO_COMMIT         COMMIT  (2026-11-19/20261119T001336650326Z_05948f69-7ede-4341-82e2-bfd2846bd6de_coordenador_DECISAO_COMMIT_65dadd.json)
2026-11-19T00:13:36.903+00:00  coordenador  CONFIRMADO             america: COMMIT PREPARED 'gs-05948f69-7ede-4341-82e2-bfd2846  (2026-11-19/20261119T001336903542Z_05948f69-7ede-4341-82e2-bfd2846bd6de_coordenador_CONFIRMADO_446097.json)
2026-11-19T00:13:36.924+00:00  coordenador  CONFIRMADO             europa: COMMIT PREPARED 'gs-05948f69-7ede-4341-82e2-bfd2846b  (2026-11-19/20261119T001336924292Z_05948f69-7ede-4341-82e2-bfd2846bd6de_coordenador_CONFIRMADO_add9fc.json)
2026-11-19T00:13:37.025+00:00  coordenador  CONCLUIDA              decisao aplicada em todos os participantes  (2026-11-19/20261119T001337025308Z_05948f69-7ede-4341-82e2-bfd2846bd6de_coordenador_CONCLUIDA_9734fd.json)
2026-11-19T00:13:37.152+00:00  api-1        ORDEM_ENVIADA          CONCLUIDA  (2026-11-19/20261119T001337152715Z_05948f69-7ede-4341-82e2-bfd2846bd6de_api-1_ORDEM_ENVIADA_5091da.json)
2026-11-19T00:13:38.068+00:00  coordenador  PARCEIRO_CONFIRMOU     referencia BP-000001 (HTTP 201)  (2026-11-19/20261119T001338068752Z_05948f69-7ede-4341-82e2-bfd2846bd6de_coordenador_PARCEIRO_CONFIRMOU_ab9b0a.json)
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
20261119T001820235833Z_061b9649-1d62-4a52-9e9a-e084f6fe7b95_coordenador_INICIADA_ae918a.json
20261119T001820409735Z_061b9649-1d62-4a52-9e9a-e084f6fe7b95_coordenador_PREPARADO_db8cfe.json
20261119T001820540155Z_061b9649-1d62-4a52-9e9a-e084f6fe7b95_coordenador_PREPARADO_c2dca6.json
20261119T001820636046Z_061b9649-1d62-4a52-9e9a-e084f6fe7b95_coordenador_DECISAO_COMMIT_4d3955.json
20261119T001820987987Z_061b9649-1d62-4a52-9e9a-e084f6fe7b95_coordenador_CONFIRMADO_093244.json
20261119T001821021531Z_061b9649-1d62-4a52-9e9a-e084f6fe7b95_coordenador_CONFIRMADO_bf31fc.json
20261119T001821126840Z_061b9649-1d62-4a52-9e9a-e084f6fe7b95_coordenador_CONCLUIDA_62919d.json
20261119T001821235661Z_061b9649-1d62-4a52-9e9a-e084f6fe7b95_api-1_ORDEM_ENVIADA_e31711.json
20261119T001821436166Z_061b9649-1d62-4a52-9e9a-e084f6fe7b95_coordenador_PARCEIRO_CONFIRMOU_408798.json
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
