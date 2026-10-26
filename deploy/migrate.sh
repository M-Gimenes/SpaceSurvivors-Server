#!/usr/bin/env bash
# Aplica as migrações de migrations/ que ainda não rodaram. Pode rodar de novo sem efeito.
set -euo pipefail
cd "$(dirname "$0")/.."
DB=$(grep '^DB_NAME=' .env | cut -d= -f2)
has_column() {
  sudo mysql -N -e "SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema='$DB' AND table_name='ranking' AND column_name='$1'"
}
if [ "$(has_column token_hash)" = "0" ]; then
  echo "aplicando 001_dono_do_nick_e_partidas.sql"
  sudo mysql "$DB" < migrations/001_dono_do_nick_e_partidas.sql
else
  echo "001 já aplicada"
fi
sudo mysql -e "SHOW COLUMNS FROM \`$DB\`.ranking"
