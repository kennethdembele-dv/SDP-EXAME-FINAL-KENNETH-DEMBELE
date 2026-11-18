#!/bin/sh
# Migracao 00 (base do coordenador): papel dono do registo 2PC.
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<SQL
SET log_statement = 'none';   -- nao escrever a palavra-passe no log
CREATE ROLE gs_coordenador LOGIN PASSWORD '${PG_SENHA_COORDENADOR}';
GRANT CREATE ON SCHEMA public TO gs_coordenador;
SQL
