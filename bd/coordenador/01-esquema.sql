-- Migracao 01 (base do coordenador): registo duravel das transferencias distribuidas.
-- E aqui que fica a DECISAO GLOBAL do 2PC. Cada escrita e confirmada (fsync do WAL do
-- PostgreSQL, synchronous_commit=on) antes de o coordenador avancar para o passo seguinte.
SET ROLE gs_coordenador;

CREATE TABLE transferencias (
    id                  UUID PRIMARY KEY,
    utilizador          TEXT NOT NULL,
    chave_idempotencia  TEXT NOT NULL,
    hash_pedido         CHAR(64) NOT NULL,      -- SHA-256 dos dados do pedido (detecta reutilizacao da chave)
    conta_origem        TEXT NOT NULL,
    conta_destino       TEXT NOT NULL,
    montante_centimos   BIGINT NOT NULL CHECK (montante_centimos > 0),
    moeda               CHAR(3) NOT NULL,
    instancia_api       TEXT NOT NULL,           -- api-1 ou api-2 (quem assinou a ordem)
    -- INICIADA -> PREPARADA -> COMMIT_DECIDIDO -> CONCLUIDA
    --        \-> ABORT_DECIDIDO -> ABORTADA
    estado              TEXT NOT NULL CHECK (estado IN ('INICIADA', 'PREPARADA', 'COMMIT_DECIDIDO',
                                                        'CONCLUIDA', 'ABORT_DECIDIDO', 'ABORTADA')),
    decisao             TEXT CHECK (decisao IN ('COMMIT', 'ABORT')),
    codigo_erro         TEXT,
    motivo              TEXT,
    parceiro_estado     TEXT NOT NULL DEFAULT 'NAO_APLICAVEL'
                        CHECK (parceiro_estado IN ('NAO_APLICAVEL', 'POR_ENVIAR', 'CONFIRMADA')),
    parceiro_referencia TEXT,
    criada_em           TIMESTAMPTZ NOT NULL DEFAULT now(),
    decidida_em         TIMESTAMPTZ,
    concluida_em        TIMESTAMPTZ,
    actualizada_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Idempotencia: a mesma chave do mesmo utilizador corresponde sempre a mesma transferencia.
    UNIQUE (utilizador, chave_idempotencia)
);
CREATE INDEX transferencias_por_utilizador ON transferencias (utilizador, criada_em DESC);
CREATE INDEX transferencias_por_resolver ON transferencias (estado)
    WHERE estado NOT IN ('CONCLUIDA', 'ABORTADA');

-- Visao do coordenador sobre cada participante (no regional) da transferencia.
-- gid = identificador da transaccao preparada no PostgreSQL desse no (PREPARE TRANSACTION 'gid').
CREATE TABLE participantes (
    transferencia_id    UUID NOT NULL REFERENCES transferencias (id),
    no                  TEXT NOT NULL CHECK (no IN ('europa', 'america')),
    gid                 TEXT NOT NULL UNIQUE,
    -- POR_PREPARAR | PREPARADO | NAO_PREPARADO (falhou antes de preparar) |
    -- INCERTO (perdeu-se a resposta ao PREPARE) | CONFIRMADO | DESFEITO
    estado              TEXT NOT NULL,
    actualizado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (transferencia_id, no)
);

-- Diario de eventos do protocolo (o que aconteceu e quando), para auditoria e defesa.
CREATE TABLE eventos (
    id                  BIGSERIAL PRIMARY KEY,
    transferencia_id    UUID NOT NULL,
    evento              TEXT NOT NULL,
    detalhe             TEXT,
    em                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX eventos_por_transferencia ON eventos (transferencia_id, id);
