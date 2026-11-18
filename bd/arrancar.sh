#!/bin/sh
# Arranque do PostgreSQL com TLS. O PostgreSQL recusa uma chave privada legivel por outros
# utilizadores, e os ficheiros montados a partir do Windows nao tem permissoes Unix fiaveis:
# por isso copiamos o certificado e a chave para dentro do contentor com dono postgres e modo 0600.
set -e
mkdir -p /var/lib/postgresql/tls
cp "/run/secrets/${NO}.crt" /var/lib/postgresql/tls/servidor.crt
cp "/run/secrets/${NO}.key" /var/lib/postgresql/tls/servidor.key
cp /run/secrets/ca.crt /var/lib/postgresql/tls/ca.crt
chown -R postgres:postgres /var/lib/postgresql/tls
chmod 600 /var/lib/postgresql/tls/servidor.key
exec docker-entrypoint.sh "$@"
