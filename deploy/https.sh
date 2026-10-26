#!/usr/bin/env bash
# HTTPS (Let's Encrypt) no nginx + backup diário do ranking.
# Uso (na VM): bash deploy/https.sh <dominio>    ex.: bash deploy/https.sh spacesurvivors.duckdns.org
# O domínio já tem que apontar para o IP público da VM.
set -Eeuo pipefail
DOMAIN="${1:?passe o domínio}"
SITE=/etc/nginx/sites-available/spacesurvivors
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
step(){ echo; echo "=== $*"; }
trap 'echo "!!! FALHOU na linha $LINENO: $BASH_COMMAND"' ERR

step "1. O domínio aponta pra esta VM?"
MYIP=$(curl -s -m 10 https://api.ipify.org || curl -s -m 10 https://ifconfig.me)
DNSIP=$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)
echo "IP público da VM: $MYIP | $DOMAIN resolve para: ${DNSIP:-nada}"
if [ "$MYIP" != "$DNSIP" ]; then echo "O DNS ainda não aponta pra cá"; exit 1; fi

step "2. nginx conhecendo o nome do domínio"
grep -q "server_name $DOMAIN" "$SITE" || sudo sed -i "s/server_name _;/server_name $DOMAIN _;/" "$SITE"
sudo nginx -t
sudo systemctl reload nginx

step "3. Certificado Let's Encrypt (certbot)"
sudo DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get -o DPkg::Lock::Timeout=180 install -y -qq certbot python3-certbot-nginx >/dev/null
# --no-redirect: HTTP continua respondendo. Um redirect 301 faria o requests trocar POST por GET.
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --no-redirect
sudo nginx -t
sudo systemctl reload nginx

step "4. Renovação automática (o certificado vale 90 dias)"
echo "certbot.timer: $(systemctl is-active certbot.timer) / boot: $(systemctl is-enabled certbot.timer)"
sudo certbot renew --dry-run 2>&1 | tail -n 2

step "5. HTTPS respondendo"
curl -s -o /dev/null -w "https://$DOMAIN/version -> HTTP %{http_code}\n" --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/version"

step "6. Backup diário do ranking (04:00 UTC, guarda 14 dias)"
mkdir -p /home/ubuntu/backups
sudo tee /etc/cron.d/spacesurvivors-backup >/dev/null <<'EOF'
# Backup diario do ranking as 04:00 UTC; apaga os com mais de 14 dias
0 4 * * * root mysqldump ranking | gzip > /home/ubuntu/backups/ranking_$(date +\%F).sql.gz && chown ubuntu:ubuntu /home/ubuntu/backups/*.sql.gz && find /home/ubuntu/backups -name 'ranking_*.sql.gz' -mtime +14 -delete
EOF
sudo chmod 644 /etc/cron.d/spacesurvivors-backup
sudo sh -c "mysqldump ranking | gzip > /home/ubuntu/backups/ranking_$(date +%F).sql.gz"
sudo chown ubuntu:ubuntu /home/ubuntu/backups/*.sql.gz
ls -la /home/ubuntu/backups
echo "HTTPS_OK"
