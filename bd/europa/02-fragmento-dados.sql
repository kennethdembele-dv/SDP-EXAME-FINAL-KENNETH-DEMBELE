-- Migracao 02 (no Europa): restricao do fragmento e dados ficticios de demonstracao.
-- O no Europa so aceita utilizadores e contas europeias.
ALTER TABLE utilizadores ADD CONSTRAINT fragmento_europa CHECK (regiao = 'EU');
ALTER TABLE contas ADD CONSTRAINT fragmento_europa CHECK (id LIKE 'EU-%');

-- Palavras-passe de demonstracao: ana / Ana#2026, bruno / Bruno#2026 (so para o laboratorio).
INSERT INTO utilizadores (id, nome, regiao, hash_palavra_passe) VALUES
 ('ana',   'Ana Silva',   'EU', 'scrypt$16384$8$5$a6e34038847dad0fac8bc84e47ac3c29$81ff10e49c473983c3e39530374624bae7e8b381a3fd5c4a046daadb1a6573c7'),
 ('bruno', 'Bruno Costa', 'EU', 'scrypt$16384$8$5$190b5896422e1a344bfac1ef6ec72be7$fe3ff963ec83efdbd6d66774be57e36b2046cb39e043a9600bd284e696eaa29a');

INSERT INTO contas (id, titular, moeda, saldo_centimos) VALUES
 ('EU-1001', 'ana',   'EUR', 500000),   -- 5000.00
 ('EU-1002', 'ana',   'EUR', 150000),   -- 1500.00
 ('EU-1003', 'bruno', 'EUR',  30000);   --  300.00
