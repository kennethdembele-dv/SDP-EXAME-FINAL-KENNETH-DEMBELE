#!/bin/sh
# Migracao 00 (nos regionais): papeis com o minimo de privilegios.
#   gs_leitura     -> autenticacao e APIs: so consultam utilizadores, contas e movimentos
#   gs_transaccoes -> coordenador 2PC: debita, credita, regista movimentos e prepara transaccoes
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<SQL
SET log_statement = 'none';   -- nao escrever as palavras-passe no log
CREATE ROLE gs_leitura LOGIN PASSWORD '${PG_SENHA_LEITURA}';
CREATE ROLE gs_transaccoes LOGIN PASSWORD '${PG_SENHA_TRANSACCOES}';
SQL
