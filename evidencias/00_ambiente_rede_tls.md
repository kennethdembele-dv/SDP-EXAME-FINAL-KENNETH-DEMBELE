# Cenario 0: Ambiente, rede, DNS e TLS

**Resultado: PASSOU** (8/8 verificacoes, 8.7 s, executado em 2026-11-19 03:01:21)

**Objectivo:** Mostrar os nos, as redes, os IP, as portas e provar que as ligacoes a BD usam TLS verificado.

## Procedimento executado

1. `03:01:13` docker compose ps
2. `03:01:13` Resolucao DNS a partir do contentor api-1
3. `03:01:14` Parametros do PostgreSQL relevantes para o 2PC e TLS
4. `03:01:15` Cada servico abre uma ligacao ao db-europa com o seu DSN (TLS verify-full); o servidor mostra-as
5. `03:01:20` Tentar ligar ao db-europa sem TLS e com o nome errado no certificado
6. `03:01:20` HTTPS: pedido sem a CA do laboratorio e pedido com a CA

## Contentores (docker compose ps)

```
NAME                            STATUS                    PORTS
global-scale-api-1-1            Up 10 seconds (healthy)   0.0.0.0:8001->8001/tcp, [::]:8001->8001/tcp
global-scale-api-2-1            Up 12 seconds (healthy)   0.0.0.0:8002->8002/tcp, [::]:8002->8002/tcp
global-scale-auth-1             Up 13 seconds (healthy)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
global-scale-banco-parceiro-1   Up 31 seconds (healthy)   127.0.0.1:8200->8200/tcp
global-scale-coordenador-1      Up 13 seconds (healthy)   127.0.0.1:8100->8100/tcp
global-scale-db-america-1       Up 30 seconds (healthy)   5432/tcp
global-scale-db-coordenador-1   Up 29 seconds (healthy)   5432/tcp
global-scale-db-europa-1        Up 29 seconds (healthy)   5432/tcp
global-scale-nfs-1              Up 28 seconds (healthy)   2049/tcp
```

## Redes e enderecos IP (docker network inspect)

```
global-scale_frontal  172.30.1.0/24
   172.30.1.10/24     global-scale-auth-1
   172.30.1.11/24     global-scale-api-1-1
   172.30.1.12/24     global-scale-api-2-1
global-scale_interna  172.30.2.0/24
   172.30.2.10/24     global-scale-db-europa-1
   172.30.2.11/24     global-scale-db-america-1
   172.30.2.12/24     global-scale-db-coordenador-1
   172.30.2.20/24     global-scale-coordenador-1
   172.30.2.30/24     global-scale-banco-parceiro-1
   172.30.2.40/24     global-scale-nfs-1
   172.30.2.50/24     global-scale-auth-1
   172.30.2.51/24     global-scale-api-1-1
   172.30.2.52/24     global-scale-api-2-1
```

## DNS interno (getaddrinfo dentro de api-1)

```
db-europa        172.30.2.10
db-america       172.30.2.11
db-coordenador   172.30.2.12
coordenador      172.30.2.20
auth             172.30.1.10
banco-parceiro   172.30.2.30
nfs              172.30.2.40
```

## Configuracao dos nos PostgreSQL

```
db-europa       max_prepared_transactions=40  ssl=on  porta=5433  PostgreSQL 17.12
db-america      max_prepared_transactions=40  ssl=on  porta=5434  PostgreSQL 17.12
db-coordenador  max_prepared_transactions=40  ssl=on  porta=5435  PostgreSQL 17.12
```

## Ligacoes ao db-europa vistas pelo servidor (pg_stat_ssl): servico | papel | IP | ssl | versao | cifra

```
api-1 | gs_leitura | 172.30.2.51 | t | TLSv1.3 | TLS_AES_256_GCM_SHA384
api-2 | gs_leitura | 172.30.2.52 | t | TLSv1.3 | TLS_AES_256_GCM_SHA384
auth | gs_leitura | 172.30.2.50 | t | TLSv1.3 | TLS_AES_256_GCM_SHA384
coordenador | gs_transaccoes | 172.30.2.20 | t | TLSv1.3 | TLS_AES_256_GCM_SHA384
```

## Ligacoes de teste a partir de api-1

```
sem TLS -> RECUSADO: connection failed: connection to server at "172.30.2.10", port 5433 failed: FATAL:  pg_hba.conf rejects connection for host "172.30.2.51", user "gs_le
IP em vez do nome -> RECUSADO: connection failed: connection to server at "172.30.2.10", port 5433 failed: server certificate for "db-europa" (and 2 other names) does not match host
correcto -> ligou, TLS TLSv1.3
```

## HTTPS na API

```
sem a CA do laboratorio: recusado: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1010)
com a CA: HTTP 200 {'servico': 'api-1', 'estado': 'ok', 'auditoria_por_publicar': 0}
```

## Verificacoes

- [x] api-1 resolve todos os nomes dos servicos
- [x] max_prepared_transactions > 0 e ssl=on nos tres nos
- [x] as ligacoes de auth, api-1, api-2 e coordenador usam TLS 1.3
- [x] sem TLS: recusado pelo pg_hba.conf
- [x] certificado sem esse nome: recusado (verify-full)
- [x] ligacao correcta usa TLSv1.3
- [x] o certificado da API so e aceite com a CA do laboratorio
- [x] HTTP sem TLS na porta 8001 e recusado: recusado (RemoteProtocolError)
