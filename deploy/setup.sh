#!/usr/bin/env bash
# Instalação completa numa VM Ubuntu 24.04 (testado na Oracle Cloud, 1 GB de RAM).
# Pode rodar de novo sem quebrar nada. Uso (na VM, dentro do repo clonado):
#   bash deploy/setup.sh
# Antes: copie builds/Space Survivors.exe e, se for migrar saves da 1.0.0, instance/private_key.
set -Eeuo pipefail
APP=/home/ubuntu/SpaceSurvivors-Server
SVC=spacesurvivors
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
step(){ echo; echo "=== $*"; }
trap 'echo "!!! FALHOU na linha $LINENO: $BASH_COMMAND"; sudo journalctl -u $SVC -n 25 --no-pager 2>/dev/null || true' ERR
cd "$APP"

step "0. Conferindo arquivos"
[ -f "builds/Space Survivors.exe" ] && echo "ok    builds/Space Survivors.exe" || echo "AVISO: sem builds/Space Survivors.exe (/download_update vai falhar)"
[ -f instance/private_key ] && echo "ok    instance/private_key" || echo "AVISO: sem instance/private_key (/claim desativado)"

step "1. Swap de 1 GB"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 1G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi
free -h

step "2. Pacotes"
sudo DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get -o DPkg::Lock::Timeout=180 install -y -qq \
  mysql-server nginx python3-venv >/dev/null

step "3. MySQL enxuto pra 1 GB"
sudo tee /etc/mysql/mysql.conf.d/zz-lowmem.cnf >/dev/null <<'EOF'
[mysqld]
performance_schema = OFF
innodb_buffer_pool_size = 64M
max_connections = 30
EOF
sudo systemctl restart mysql

step "4. venv e dependências"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

step "5. Banco, usuário com senha nova e .env (a senha não aparece na tela)"
DBPASS=$(openssl rand -hex 24)
VERSION=$(grep '^APP_VERSION=' .env 2>/dev/null | cut -d= -f2 || true)
sudo mysql -e "CREATE DATABASE IF NOT EXISTS ranking CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE USER IF NOT EXISTS 'ecko'@'localhost' IDENTIFIED BY '${DBPASS}';
  ALTER USER 'ecko'@'localhost' IDENTIFIED BY '${DBPASS}';
  GRANT ALL PRIVILEGES ON ranking.* TO 'ecko'@'localhost'; FLUSH PRIVILEGES;"
umask 077
cat > .env <<EOF
DB_USERNAME=ecko
DB_PASSWORD=${DBPASS}
DB_HOSTNAME=localhost
DB_NAME=ranking
APP_VERSION=${VERSION:-1.0.1}
FLASK_DEBUG=0
EOF
unset DBPASS
umask 022
chmod 600 .env
[ -f instance/private_key ] && chmod 600 instance/private_key
echo ".env escrito, APP_VERSION=$(grep '^APP_VERSION=' .env | cut -d= -f2)"

step "6. Tabela e migrações"
.venv/bin/python -c "from app import create_app; from app.models import db; app = create_app(); app.app_context().push(); db.create_all()"
bash deploy/migrate.sh

step "7. Serviço systemd (gunicorn)"
sudo tee /etc/systemd/system/$SVC.service >/dev/null <<EOF
[Unit]
Description=Space Survivors backend (gunicorn)
After=network.target mysql.service
Wants=mysql.service

[Service]
User=ubuntu
WorkingDirectory=$APP
# 1 processo com 4 threads: cabe em 1 GB de RAM e sobra para o volume de jogadores.
ExecStart=$APP/.venv/bin/gunicorn --workers 1 --threads 4 --bind 127.0.0.1:8000 --timeout 120 --access-logfile - wsgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable $SVC >/dev/null 2>&1
sudo systemctl restart $SVC
sleep 3
echo "serviço: $(systemctl is-active $SVC)"

step "8. nginx na porta 80, com limite de requisições"
if [ ! -f /etc/nginx/sites-available/$SVC ]; then
  sudo tee /etc/nginx/sites-available/$SVC >/dev/null <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 1m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
EOF
fi
sudo ln -sf /etc/nginx/sites-available/$SVC /etc/nginx/sites-enabled/$SVC
sudo rm -f /etc/nginx/sites-enabled/default
sudo cp /etc/nginx/sites-available/$SVC /tmp/spacesurvivors-site.bak
sudo python3 deploy/patch_nginx_ratelimit.py
if ! sudo nginx -t; then
  sudo cp /tmp/spacesurvivors-site.bak /etc/nginx/sites-available/$SVC
  sudo rm -f /etc/nginx/conf.d/spacesurvivors-ratelimit.conf
  echo "config nova do nginx inválida: revertida"; exit 1
fi
sudo systemctl enable nginx >/dev/null 2>&1
sudo systemctl reload nginx || sudo systemctl restart nginx

step "9. Firewall da VM (iptables): 80 e 443 antes do REJECT"
for p in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport $p -m state --state NEW -j ACCEPT 2>/dev/null; then
    POS=$(sudo iptables -L INPUT --line-numbers | awk '/REJECT/ {print $1; exit}')
    if [ -n "$POS" ]; then sudo iptables -I INPUT "$POS" -p tcp --dport $p -m state --state NEW -j ACCEPT
    else sudo iptables -A INPUT -p tcp --dport $p -m state --state NEW -j ACCEPT; fi
  fi
done
sudo netfilter-persistent save >/dev/null 2>&1 || sudo sh -c 'iptables-save > /etc/iptables/rules.v4'

step "10. Teste de fumaça (cria um jogador de teste e apaga no fim)"
FAIL=0
.venv/bin/python scripts/smoke_test.py http://127.0.0.1 --write || FAIL=1
sudo mysql -e "DELETE FROM ranking.ranking WHERE nickname LIKE 'zzsmoke%'"
[ "$FAIL" = "0" ]
for s in mysql nginx $SVC; do echo "$s: $(systemctl is-active $s)"; done
echo "SETUP_OK"
