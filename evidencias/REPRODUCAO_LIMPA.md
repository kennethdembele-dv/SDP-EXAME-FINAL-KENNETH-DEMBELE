# Reproducao a partir de uma instalacao limpa

Executada em 2026-11-19, no Windows 10 Pro 22H2 com Docker Desktop 4.99 (backend Hyper-V, VM com 2 GB e 2 CPUs),
Docker 29.9.3 e Compose v5.7.0. Os ficheiros de cenario desta pasta (00 a 12 e 99) sao os desta execucao.

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
