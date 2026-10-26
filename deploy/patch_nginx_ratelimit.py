"""Limite de requisições por IP no site do nginx. Pode rodar de novo sem efeito.

Uso (como root): python3 deploy/patch_nginx_ratelimit.py
- ss_api: 30 requisições/minuto por IP em todas as rotas (rajada de 20).
- ss_register: 3 cadastros/minuto por IP em /register (rajada de 3).
Passou do limite: o nginx responde 429 sem chamar o app.
"""
import pathlib
import sys

SITE = pathlib.Path('/etc/nginx/sites-available/spacesurvivors')
ZONES = pathlib.Path('/etc/nginx/conf.d/spacesurvivors-ratelimit.conf')

ZONES.write_text(
    "# Limites por IP do Space Survivors (deploy/patch_nginx_ratelimit.py)\n"
    "limit_req_zone $binary_remote_addr zone=ss_api:10m rate=30r/m;\n"
    "limit_req_zone $binary_remote_addr zone=ss_register:10m rate=3r/m;\n"
    "limit_req_status 429;\n"
)

site = SITE.read_text()
if 'zone=ss_api' in site:
    print('limites já configurados no site')
    sys.exit(0)

out, done = [], False
for line in site.splitlines(keepends=True):
    if not done and line.strip() == 'location / {':
        i = line[:len(line) - len(line.lstrip())]
        out.append(
            f"{i}location = /register {{\n"
            f"{i}    limit_req zone=ss_register burst=3 nodelay;\n"
            f"{i}    proxy_pass http://127.0.0.1:8000;\n"
            f"{i}    proxy_set_header Host $host;\n"
            f"{i}    proxy_set_header X-Real-IP $remote_addr;\n"
            f"{i}    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
            f"{i}    proxy_set_header X-Forwarded-Proto $scheme;\n"
            f"{i}}}\n\n"
        )
        out.append(line)
        out.append(f"{i}    limit_req zone=ss_api burst=20 nodelay;\n")
        done = True
    else:
        out.append(line)
if not done:
    sys.exit("não achei 'location / {' em " + str(SITE))
SITE.write_text(''.join(out))
print('limites adicionados ao site')
