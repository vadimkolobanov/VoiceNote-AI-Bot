"""Поднять HTTPS для metodex.duckdns.org через certbot --nginx.

Пред-условие: DNS-запись metodex.duckdns.org → 216.57.108.153 уже на месте,
nginx слушает 80, порт 80 открыт в UFW.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ssh import put, run  # noqa: E402

DOMAIN = "metodex.duckdns.org"
EMAIL = "mayardolva6@gmail.com"


def step(label: str) -> None:
    print(f"\n========== {label} ==========")


def main() -> None:
    step("install certbot")
    run("DEBIAN_FRONTEND=noninteractive apt-get install -y -qq certbot python3-certbot-nginx")

    step("update nginx server_name")
    cfg = (
        "server {\n"
        "    listen 80 default_server;\n"
        f"    server_name {DOMAIN};\n"
        "    client_max_body_size 25M;\n"
        "\n"
        "    location / {\n"
        "        proxy_pass http://127.0.0.1:8765;\n"
        "        proxy_set_header Host $host;\n"
        "        proxy_set_header X-Real-IP $remote_addr;\n"
        "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
        "        proxy_set_header X-Forwarded-Proto $scheme;\n"
        "        proxy_read_timeout 120s;\n"
        "    }\n"
        "}\n"
    )
    Path("deploy/_nginx.tmp").write_text(cfg, encoding="utf-8")
    put("deploy/_nginx.tmp", "/tmp/methodex.conf")
    run("mv /tmp/methodex.conf /etc/nginx/sites-available/methodex && nginx -t && systemctl reload nginx")

    step("issue Let's Encrypt cert via nginx plugin")
    run(
        f"certbot --nginx --non-interactive --agree-tos --email {EMAIL} "
        f"--redirect -d {DOMAIN}"
    )

    step("smoke test HTTPS")
    run(f"curl -fsS -m 10 https://{DOMAIN}/health || true")


if __name__ == "__main__":
    main()
