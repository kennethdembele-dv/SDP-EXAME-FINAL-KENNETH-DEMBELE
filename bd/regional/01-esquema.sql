-- Migracao 01 (nos regionais): o mesmo esquema na Europa e na America.
-- Fragmentacao horizontal: cada no guarda so as linhas da sua regiao (ver 02-fragmento-*.sql).

CREATE TABLE utilizadores (
    id                  TEXT PRIMARY KEY,                       -- nome de login
    nome                TEXT NOT NULL,
    regiao              TEXT NOT NULL CHECK (regiao IN ('EU', 'US')),
    hash_palavra_passe  TEXT NOT NULL                           -- scrypt$N$r$p$sal$hash
);

CREATE TABLE contas (
    id              TEXT PRIMARY KEY CHECK (id ~ '^(EU|US)-[0-9]{4}$'),
    titular         TEXT NOT NULL REFERENCES utilizadores (id),
    moeda           CHAR(3) NOT NULL DEFAULT 'EUR',
    -- Centimos inteiros (sem virgula flutuante). A restricao impede saldo negativo mesmo que
    -- o codigo tenha um erro: a base de dados e a ultima defesa.
    saldo_centimos  BIGINT NOT NULL CHECK (saldo_centimos >= 0),
    criada_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Cada transferencia gera exactamente um DEBITO (no no da conta de origem) e um CREDITO
-- (no no da conta de destino). A unicidade (transferencia_id, tipo) impede duplicados mesmo
-- que a mesma decisao seja aplicada duas vezes durante uma recuperacao.
CREATE TABLE movimentos (
    id                  BIGSERIAL PRIMARY KEY,
    transferencia_id    UUID NOT NULL,
    conta_id            TEXT NOT NULL REFERENCES contas (id),
    tipo                TEXT NOT NULL CHECK (tipo IN ('DEBITO', 'CREDITO')),
    montante_centimos   BIGINT NOT NULL CHECK (montante_centimos > 0),
    saldo_apos_centimos BIGINT NOT NULL,
    contraparte         TEXT NOT NULL,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (transferencia_id, tipo)
);
CREATE INDEX movimentos_por_conta ON movimentos (conta_id, criado_em DESC);

GRANT SELECT ON utilizadores, contas, movimentos TO gs_leitura;
GRANT SELECT ON contas, movimentos TO gs_transaccoes;
GRANT UPDATE (saldo_centimos) ON contas TO gs_transaccoes;
GRANT INSERT ON movimentos TO gs_transaccoes;
GRANT USAGE ON SEQUENCE movimentos_id_seq TO gs_transaccoes;
