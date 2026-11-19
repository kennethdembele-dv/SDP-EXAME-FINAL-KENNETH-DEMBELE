# Ensaio da configuracao de dois computadores num so PC

**Resultado: PASSOU** (9/9 verificacoes, executado em 2026-11-19 03:14:10).

Os dois projectos (gs-pc-a e gs-pc-b) correm no mesmo Docker, mas so comunicam pelas portas publicadas, atraves de `host-gateway`, como fariam dois computadores. Com dois PCs reais troca-se `host-gateway` pelos IP (docs/DOIS_COMPUTADORES.md); este ensaio nao substitui a prova fisica com duas maquinas.

## Enderecos usados

```
IP_PC_A=host-gateway
IP_PC_B=host-gateway
NFS_ENDERECO=127.0.0.1
```

## PC A: docker compose ps

```
NAME                       STATUS                        PORTS
gs-pc-a-api-1-1            Up 59 seconds (healthy)       0.0.0.0:8001->8001/tcp, [::]:8001->8001/tcp
gs-pc-a-auth-1             Up About a minute (healthy)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
gs-pc-a-coordenador-1      Up About a minute (healthy)   0.0.0.0:8100->8100/tcp, [::]:8100->8100/tcp
gs-pc-a-db-coordenador-1   Up About a minute (healthy)   5432/tcp
gs-pc-a-db-europa-1        Up About a minute (healthy)   0.0.0.0:5433->5433/tcp, [::]:5433->5433/tcp
gs-pc-a-nfs-1              Up About a minute (healthy)   0.0.0.0:2049->2049/tcp, [::]:2049->2049/tcp
```

## PC B: docker compose ps

```
NAME                       STATUS                    PORTS
gs-pc-b-api-2-1            Up 6 seconds (healthy)    0.0.0.0:8002->8002/tcp, [::]:8002->8002/tcp
gs-pc-b-banco-parceiro-1   Up 18 seconds (healthy)   0.0.0.0:8200->8200/tcp, [::]:8200->8200/tcp
gs-pc-b-db-america-1       Up 17 seconds (healthy)   0.0.0.0:5434->5434/tcp, [::]:5434->5434/tcp
```

## PC A: o coordenador resolve os nomes do PC B (extra_hosts)

```
fdc4:f303:9324::254 db-america
fdc4:f303:9324::254 banco-parceiro
```

## Transferencias entre os dois PCs

```
ana EU-1001 -> US-2001 via api-1 (PC A): HTTP 201 CONCLUIDA
carlos US-2001 -> EU-1002 via api-2 (PC B): HTTP 201 CONCLUIDA (ordem assinada por api-2)
```

## PC B: comandos 2PC recebidos pelo db-america (vindos do coordenador no PC A)

```
statement: PREPARE TRANSACTION 'gs-fef1e464-80e2-48eb-ad2e-cf769c26cb84-america'
statement: COMMIT PREPARED 'gs-fef1e464-80e2-48eb-ad2e-cf769c26cb84-america'
```

## PC B: ligacao do coordenador (PC A) vista pelo db-america: servico | papel | origem | ssl | versao

```
coordenador | gs_transaccoes | 192.168.65.1 | t | TLSv1.3
```

## PC B: o api-2 monta o NFS do PC A

```
:/dfs /mnt/dfs nfs4 rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,soft,fatal_neterrors=none,proto=tcp,timeo=50,retrans=2,sec=sys,clientaddr=127.0.0.1,local_lock=none,addr=127.0.0.1 0 0
```

## PC B: auditoria lida pelo api-2 no DFS do PC A

```
coordenador  INICIADA               2026-11-19/20261119T011345636041Z_03015696-8917-47ec-9225-8380a4fc47aa_coordenador_INICIADA_7ebc36.json
coordenador  PREPARADO              2026-11-19/20261119T011345818862Z_03015696-8917-47ec-9225-8380a4fc47aa_coordenador_PREPARADO_ba4284.json
coordenador  PREPARADO              2026-11-19/20261119T011345999987Z_03015696-8917-47ec-9225-8380a4fc47aa_coordenador_PREPARADO_30c6e2.json
coordenador  DECISAO_COMMIT         2026-11-19/20261119T011346147911Z_03015696-8917-47ec-9225-8380a4fc47aa_coordenador_DECISAO_COMMIT_ea55d9.json
coordenador  CONFIRMADO             2026-11-19/20261119T011346603647Z_03015696-8917-47ec-9225-8380a4fc47aa_coordenador_CONFIRMADO_ec8dd5.json
coordenador  CONFIRMADO             2026-11-19/20261119T011346635740Z_03015696-8917-47ec-9225-8380a4fc47aa_coordenador_CONFIRMADO_05a987.json
coordenador  CONCLUIDA              2026-11-19/20261119T011346843975Z_03015696-8917-47ec-9225-8380a4fc47aa_coordenador_CONCLUIDA_f1f9ad.json
api-2        ORDEM_ENVIADA          2026-11-19/20261119T011347195068Z_03015696-8917-47ec-9225-8380a4fc47aa_api-2_ORDEM_ENVIADA_c5d6c8.json
coordenador  PARCEIRO_CONFIRMOU     2026-11-19/20261119T011347389735Z_03015696-8917-47ec-9225-8380a4fc47aa_coordenador_PARCEIRO_CONFIRMOU_f2d082.json
```

## Verificacoes

- [x] PC A: 6 servicos healthy
- [x] PC B: 3 servicos healthy
- [x] db-america e banco-parceiro resolvidos por extra_hosts no PC A
- [x] Europa (PC A) -> America (PC B): CONCLUIDA
- [x] America (PC B) -> Europa (PC A) via api-2: CONCLUIDA
- [x] o db-america do PC B recebeu PREPARE TRANSACTION e COMMIT PREPARED
- [x] a ligacao do coordenador do PC A ao db-america do PC B usa TLS 1.3
- [x] api-2 (PC B) monta /mnt/dfs por nfs4
- [x] o api-2 (PC B) le eventos escritos pelo coordenador (PC A) e por si proprio
