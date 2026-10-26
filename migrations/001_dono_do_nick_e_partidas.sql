-- 1.0.1: o nick passa a ter dono (token) e a partida passa a ter prova de tempo.
-- token_hash NULL = nick vindo da 1.0.0 que ainda não foi reivindicado em /claim.
ALTER TABLE ranking
  ADD COLUMN token_hash VARCHAR(64) NULL,
  ADD COLUMN run_started_at DATETIME NULL;
