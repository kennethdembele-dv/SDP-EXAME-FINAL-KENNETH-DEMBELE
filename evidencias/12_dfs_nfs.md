# Cenario 12: Escrita e leitura dos ficheiros partilhados (NFS)

**Resultado: PASSOU** (9/9 verificacoes, 14.5 s, executado em 2026-11-19 02:27:36)

**Objectivo:** api-1 escreve um relatorio no NFS e api-2 le-o; os eventos de auditoria de varios servicos ficam no mesmo DFS; com o NFS em baixo os eventos ficam em espera e sao publicados depois.

**Dois computadores:** Com dois PCs, o servidor NFS esta no PC A e o api-2 do PC B monta-o pela rede.

## Procedimento executado

1. `02:27:23` api-1: POST /api/v1/relatorios/extracto (EU-1001)
2. `02:27:23` api-2: GET /api/v1/relatorios/EU-1001_20261119T002723Z_api-1.csv
3. `02:27:24` Falha do DFS: docker compose stop nfs; nova transferencia
4. `02:27:30` docker compose start nfs; esperar que os eventos sejam publicados

## Montagens de /mnt/dfs (/proc/mounts)

```
api-1: :/dfs /mnt/dfs nfs4 rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,soft,fatal_neterrors=none,proto=tcp,timeo=50,retrans=2,sec=sys,clientaddr=172.30.2.1,local_lock=none,addr=172.30.2.40 0 0
api-2: :/dfs /mnt/dfs nfs4 rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,soft,fatal_neterrors=none,proto=tcp,timeo=50,retrans=2,sec=sys,clientaddr=172.30.2.1,local_lock=none,addr=172.30.2.40 0 0
coordenador: :/dfs /mnt/dfs nfs4 rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,soft,fatal_neterrors=none,proto=tcp,timeo=50,retrans=2,sec=sys,clientaddr=172.30.2.1,local_lock=none,addr=172.30.2.40 0 0
```

## Relatorio escrito por api-1 e lido por api-2

```
{'nome': 'EU-1001_20261119T002723Z_api-1.csv', 'caminho_dfs': '/mnt/dfs/relatorios/EU-1001_20261119T002723Z_api-1.csv', 'escrito_por': 'api-1', 'movimentos': 5}

lido por api-2:
conta,titular,saldo_actual,gerado_por
EU-1001,ana,4840.50,api-1

data,tipo,montante,saldo_apos,contraparte,transferencia_id
2026-11-19T00:26:41.868522+00:00,DEBITO,1.00,4840.50,US-2001,d1f7d73e-306a-424e-8f04-38ce14fb91bb
2026-11-19T00:26:06.817770+00:00,DEBITO,5.00,4841.50,US-2001,ea670f49-5b30-4695-b2b0-a15326719f0e
2026-11-19T00:24:49.563184+00:00,DEBITO,8.00,4846.50,US-2001,158efdd1-056e-48ea-bba5-2e1695a1409d
2026-11-19T00:24:00.128194+00:00,DEBITO,20.00,4854.50,US-2001,f3d829cb-ab88-4a78-87b0-86dd8013e9d3
2026-11-19T00:22:45.449917+00:00,DEBITO,125.50,4874.50,US-2001,912affad-a763-43d3-b

No disco do servidor NFS:
total 4
-rw-r--r-- 1 root root 626 Nov 19 00:27 EU-1001_20261119T002723Z_api-1.csv
```

## Auditoria da transferencia do cenario 1, lida por api-2

```
2026-11-19T00:22:45.326+00:00  coordenador  INICIADA               REGISTADA  (2026-11-19/20261119T002245326922Z_912affad-a763-43d3-b17f-4f673c79e971_coordenador_INICIADA_918e71.json)
2026-11-19T00:22:45.532+00:00  coordenador  PREPARADO              europa: PREPARE TRANSACTION 'gs-912affad-a763-43d3-b17f-4f67  (2026-11-19/20261119T002245532621Z_912affad-a763-43d3-b17f-4f673c79e971_coordenador_PREPARADO_3921a9.json)
2026-11-19T00:22:45.710+00:00  coordenador  PREPARADO              america: PREPARE TRANSACTION 'gs-912affad-a763-43d3-b17f-4f6  (2026-11-19/20261119T002245710455Z_912affad-a763-43d3-b17f-4f673c79e971_coordenador_PREPARADO_173610.json)
2026-11-19T00:22:45.820+00:00  coordenador  DECISAO_COMMIT         COMMIT  (2026-11-19/20261119T002245820288Z_912affad-a763-43d3-b17f-4f673c79e971_coordenador_DECISAO_COMMIT_394af0.json)
2026-11-19T00:22:46.086+00:00  coordenador  CONFIRMADO             america: COMMIT PREPARED 'gs-912affad-a763-43d3-b17f-4f673c7  (2026-11-19/20261119T002246086038Z_912affad-a763-43d3-b17f-4f673c79e971_coordenador_CONFIRMADO_061c55.json)
2026-11-19T00:22:46.124+00:00  coordenador  CONFIRMADO             europa: COMMIT PREPARED 'gs-912affad-a763-43d3-b17f-4f673c79  (2026-11-19/20261119T002246124271Z_912affad-a763-43d3-b17f-4f673c79e971_coordenador_CONFIRMADO_38b0f5.json)
2026-11-19T00:22:46.303+00:00  coordenador  CONCLUIDA              decisao aplicada em todos os participantes  (2026-11-19/20261119T002246303855Z_912affad-a763-43d3-b17f-4f673c79e971_coordenador_CONCLUIDA_91e5d5.json)
2026-11-19T00:22:46.442+00:00  api-1        ORDEM_ENVIADA          CONCLUIDA  (2026-11-19/20261119T002246442530Z_912affad-a763-43d3-b17f-4f673c79e971_api-1_ORDEM_ENVIADA_884c69.json)
2026-11-19T00:22:47.453+00:00  coordenador  PARCEIRO_CONFIRMOU     referencia BP-000001 (HTTP 201)  (2026-11-19/20261119T002247453688Z_912affad-a763-43d3-b17f-4f673c79e971_coordenador_PARCEIRO_CONFIRMOU_fc7f6f.json)
```

## Ficheiros de auditoria no servidor NFS (um ficheiro por evento)

```
ficheiros: 208
temporarios: 0
api-1: 21
api-2: 9
coordenador: 178
```

## Eventos da transferencia feita com o NFS em baixo, ja no DFS

```
20261119T002725720512Z_56fb5e9f-a351-490c-a919-a46687843249_coordenador_INICIADA_371bc4.json
20261119T002725893109Z_56fb5e9f-a351-490c-a919-a46687843249_coordenador_PREPARADO_e19f0b.json
20261119T002726027214Z_56fb5e9f-a351-490c-a919-a46687843249_coordenador_PREPARADO_90381e.json
20261119T002726134916Z_56fb5e9f-a351-490c-a919-a46687843249_coordenador_DECISAO_COMMIT_392cdb.json
20261119T002726433780Z_56fb5e9f-a351-490c-a919-a46687843249_coordenador_CONFIRMADO_2287ab.json
20261119T002726478143Z_56fb5e9f-a351-490c-a919-a46687843249_coordenador_CONFIRMADO_462b21.json
20261119T002726583786Z_56fb5e9f-a351-490c-a919-a46687843249_coordenador_CONCLUIDA_e46a62.json
20261119T002726723042Z_56fb5e9f-a351-490c-a919-a46687843249_api-1_ORDEM_ENVIADA_667a7e.json
20261119T002727029974Z_56fb5e9f-a351-490c-a919-a46687843249_coordenador_PARCEIRO_CONFIRMOU_fce1fd.json
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
