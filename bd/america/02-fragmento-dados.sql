-- Migracao 02 (no America): restricao do fragmento e dados ficticios de demonstracao.
-- O no America so aceita utilizadores e contas americanas.
ALTER TABLE utilizadores ADD CONSTRAINT fragmento_america CHECK (regiao = 'US');
ALTER TABLE contas ADD CONSTRAINT fragmento_america CHECK (id LIKE 'US-%');

-- Palavras-passe de demonstracao: carlos / Carlos#2026, diana / Diana#2026 (so para o laboratorio).
INSERT INTO utilizadores (id, nome, regiao, hash_palavra_passe) VALUES
 ('carlos', 'Carlos Mendes', 'US', 'scrypt$16384$8$5$c1318c3e05ca37c4f7c17f2a262a3c65$e71b7ee9df53c35d84497852c35fb521171ba8db6c6d344c85cfa468e9502707'),
 ('diana',  'Diana Lopes',   'US', 'scrypt$16384$8$5$40c27d18a52bdfb8153803e55d4449f8$df57109a25229a3d4bebc0b44ea7d5fe85c30b1cb88384a1090a76200705417b');

INSERT INTO contas (id, titular, moeda, saldo_centimos) VALUES
 ('US-2001', 'carlos', 'EUR', 300000),  -- 3000.00
 ('US-2002', 'diana',  'EUR',  80000);  --  800.00
