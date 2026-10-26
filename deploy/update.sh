#!/usr/bin/env bash
# Atualiza um servidor já instalado: código novo, dependências, migrações, nginx e teste.
# Uso (na VM): bash deploy/update.sh
set -Eeuo pipefail
APP=/home/ubuntu/SpaceSurvivors-Server
SVC=spacesurvivors
step(){ echo; echo "=== $*"; }
trap 'echo "!!! FALHOU na linha $LINENO: $BASH_COMMAND"' ERR
cd "$APP"

step "1. Código novo"
git pull --ff-only
git log --oneline -1

step "2. Dependências"
.venv/bin/pip install -q -r requirements.txt

step "3. Migrações do banco"
bash deploy/migrate.sh

step "4. Limite de requisições no nginx"
SITE=/etc/nginx/sites-available/spacesurvivors
sudo cp "$SITE" /tmp/spacesurvivors-site.bak
sudo python3 deploy/patch_nginx_ratelimit.py
if ! sudo nginx -t; then
  sudo cp /tmp/spacesurvivors-site.bak "$SITE"
  sudo rm -f /etc/nginx/conf.d/spacesurvivors-ratelimit.conf
  echo "config nova do nginx inválida: revertida, nada mudou"; exit 1
fi
sudo systemctl reload nginx

step "5. Reiniciando o app"
sudo systemctl restart $SVC
sleep 3
echo "serviço: $(systemctl is-active $SVC)"

step "6. Teste de fumaça (cria um jogador de teste e apaga no fim)"
FAIL=0
.venv/bin/python scripts/smoke_test.py http://127.0.0.1 --write || FAIL=1
sudo mysql -e "DELETE FROM \`$(grep '^DB_NAME=' .env | cut -d= -f2)\`.ranking WHERE nickname LIKE 'zzsmoke%'"
[ "$FAIL" = "0" ]
echo "UPDATE_OK"
