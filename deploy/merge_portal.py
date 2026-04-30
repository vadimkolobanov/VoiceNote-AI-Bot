"""Сделать portal-nginx общим front-door для двух проектов:
  - portal (методекс корпоративный, domain TBD) — как есть, на :80
  - methodex secretary API (наш) — :443 для metodex.duckdns.org → host:8765

Шаги:
1. Перенастроить methodex-api: bind 0.0.0.0:8765 (был 127.0.0.1).
   UFW блокирует 8765 снаружи, так что utilizable только для Docker.
2. Обновить /opt/portal/docker-compose.prod.yml:
   portal-nginx — добавить 443:443, mount /etc/letsencrypt, extra_hosts host-gateway.
3. Обновить /opt/portal/nginx/portal.conf:
   server :80 default_server (как был — portal frontend),
   server :80 server_name metodex.duckdns.org → 301 https,
   server :443 server_name metodex.duckdns.org SSL → http://host-gateway:8765.
4. docker compose up -d nginx.
5. Smoke-tests.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ssh import put, run  # noqa: E402

DOMAIN = "metodex.duckdns.org"


PORTAL_CONF = textwrap.dedent("""\
    # Portal frontend / backend (default for unknown hosts).
    server {
        listen 80 default_server;
        server_name _;
        resolver 127.0.0.11 valid=30s;
        client_max_body_size 10M;

        location /api/ {
            proxy_pass http://172.20.0.10:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 120s;
            proxy_send_timeout 120s;
        }

        location /_next/static/ {
            proxy_pass http://172.20.0.11:3000;
            expires 365d;
            add_header Cache-Control "public, immutable";
        }

        location / {
            proxy_pass http://172.20.0.11:3000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    # Methodex Secretary API — HTTP → HTTPS redirect.
    server {
        listen 80;
        server_name DOMAIN_PLACEHOLDER;
        return 301 https://$host$request_uri;
    }

    # Methodex Secretary API — HTTPS, проксируем на host:8765.
    server {
        listen 443 ssl http2;
        server_name DOMAIN_PLACEHOLDER;
        client_max_body_size 25M;

        ssl_certificate     /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_prefer_server_ciphers off;

        location / {
            proxy_pass http://host.docker.internal:8765;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 120s;
        }
    }
""").replace("DOMAIN_PLACEHOLDER", DOMAIN)


def step(label: str) -> None:
    print(f"\n========== {label} ==========")


def main() -> None:
    step("ensure methodex-api binds 0.0.0.0:8765")
    run(
        "grep -q -- '--host 0.0.0.0 --port 8765' /etc/systemd/system/methodex-api.service || ("
        "sed -i 's|--host 127.0.0.1 --port 8765|--host 0.0.0.0 --port 8765|' "
        "/etc/systemd/system/methodex-api.service && "
        "systemctl daemon-reload && systemctl restart methodex-api"
        ")"
    )
    run("sleep 3 && curl -fsS -m 5 http://127.0.0.1:8765/health")

    step("write new portal.conf")
    Path("deploy/_portal.conf.tmp").write_text(PORTAL_CONF, encoding="utf-8")
    put("deploy/_portal.conf.tmp", "/opt/portal/nginx/portal.conf")

    step("patch docker-compose.prod.yml — add 443, mount letsencrypt, host-gateway")
    # ниже — целевой блок nginx; перепишем секцию nginx целиком.
    # Делаем через python на хосте для надёжности.
    patch = textwrap.dedent("""
        import re, sys
        p = '/opt/portal/docker-compose.prod.yml'
        text = open(p).read()
        new_nginx = '''  nginx:
            image: nginx:alpine
            container_name: portal-nginx
            ports:
              - "80:80"
              - "443:443"
            volumes:
              - ./nginx/portal.conf:/etc/nginx/conf.d/default.conf:ro
              - /etc/letsencrypt:/etc/letsencrypt:ro
            extra_hosts:
              - "host.docker.internal:host-gateway"
            depends_on:
              - backend
              - frontend
            restart: always
            networks:
              portal_net:
                ipv4_address: 172.20.0.12
        '''
        # вырежем старый блок nginx:
        new = re.sub(
            r'  nginx:\\n(?:    .*\\n|      .*\\n|        .*\\n)+',
            new_nginx,
            text,
            count=1,
        )
        if new == text:
            print('no change made — pattern miss')
            sys.exit(1)
        open(p, 'w').write(new)
        print('compose patched')
    """).strip()
    Path("deploy/_patch.py.tmp").write_text(patch, encoding="utf-8")
    put("deploy/_patch.py.tmp", "/tmp/patch.py")
    run("python3 /tmp/patch.py")
    run("cat /opt/portal/docker-compose.prod.yml | grep -A 18 '  nginx:'")

    step("recreate portal-nginx")
    run("cd /opt/portal && docker compose -f docker-compose.prod.yml up -d nginx")
    run("sleep 3; docker ps --filter name=portal-nginx --format '{{.Names}} | {{.Status}} | {{.Ports}}'")

    step("smoke")
    run(f"curl -fsSI -m 10 https://{DOMAIN}/health | head -5 || true")
    run(f"curl -fsS -m 10 https://{DOMAIN}/health || true")
    print()
    run("curl -fsSI -m 10 http://127.0.0.1/ | head -3 || true")


if __name__ == "__main__":
    main()
