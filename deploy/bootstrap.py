"""One-shot bootstrap скрипт для VPS (Ubuntu 24).

Идемпотентный: запуск повторно не ломает state. Делает:
1. apt-update + установка нужных пакетов (python3.12, nginx, git, ufw, certbot)
2. Создание юзера `deploy` с sudo на restart сервиса
3. Генерация SSH-ключа для CI (на сервере), вывод public-key
4. UFW: открыть 22, 80, 443
5. Клон репо в /opt/methodex (как deploy)
6. Подготовка venv + зависимости
7. systemd unit для FastAPI
8. nginx reverse-proxy 80 → 127.0.0.1:8765 (HTTP только пока, без TLS)
9. Запуск
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ssh import run, put  # noqa: E402

REPO_URL = "https://github.com/vadimkolobanov/VoiceNote-AI-Bot.git"
APP_DIR = "/opt/methodex"
APP_USER = "deploy"
SERVICE_NAME = "methodex-api"


def step(label: str) -> None:
    print(f"\n========== {label} ==========")


def install_packages() -> None:
    step("apt update + install")
    run(
        "DEBIAN_FRONTEND=noninteractive apt-get update -qq && "
        "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "
        "python3 python3-venv python3-pip git nginx ufw curl ca-certificates ffmpeg"
    )


def create_deploy_user() -> None:
    step("create deploy user")
    run(
        f"id -u {APP_USER} >/dev/null 2>&1 || "
        f"adduser --disabled-password --gecos '' {APP_USER}"
    )
    # sudo для рестарта сервиса (без пароля, узко)
    sudoers = (
        f"{APP_USER} ALL=(root) NOPASSWD: "
        f"/bin/systemctl restart {SERVICE_NAME}, "
        f"/bin/systemctl status {SERVICE_NAME}, "
        f"/bin/systemctl reload nginx, "
        f"/bin/systemctl restart nginx"
    )
    run(
        f"echo '{sudoers}' > /etc/sudoers.d/{APP_USER} && chmod 440 /etc/sudoers.d/{APP_USER}"
    )


def gen_ci_ssh_key() -> None:
    step("ensure CI SSH key")
    run(
        f"sudo -u {APP_USER} mkdir -p /home/{APP_USER}/.ssh && "
        f"sudo -u {APP_USER} chmod 700 /home/{APP_USER}/.ssh"
    )
    rc, _, _ = run(
        f"test -f /home/{APP_USER}/.ssh/id_ed25519",
        check=False,
        quiet=True,
    )
    if rc != 0:
        run(
            f"sudo -u {APP_USER} ssh-keygen -t ed25519 -N '' "
            f"-f /home/{APP_USER}/.ssh/id_ed25519 -C 'ci@methodex'"
        )
    # GitHub Actions подключается через приватный ключ deploy@VPS;
    # public должен быть в authorized_keys того же deploy.
    run(
        f"sudo -u {APP_USER} bash -c "
        f"'cat /home/{APP_USER}/.ssh/id_ed25519.pub > /home/{APP_USER}/.ssh/authorized_keys && "
        f"chmod 600 /home/{APP_USER}/.ssh/authorized_keys'"
    )


def firewall() -> None:
    step("UFW")
    run("ufw allow 22/tcp", check=False)
    run("ufw allow 80/tcp", check=False)
    run("ufw allow 443/tcp", check=False)
    run("ufw --force enable", check=False)


def clone_repo() -> None:
    step("clone repo")
    run(f"mkdir -p {APP_DIR} && chown {APP_USER}:{APP_USER} {APP_DIR}")
    rc, _, _ = run(f"test -d {APP_DIR}/.git", check=False, quiet=True)
    if rc != 0:
        run(f"sudo -u {APP_USER} git clone {REPO_URL} {APP_DIR}")
    else:
        run(f"sudo -u {APP_USER} git -C {APP_DIR} fetch --all && "
            f"sudo -u {APP_USER} git -C {APP_DIR} reset --hard origin/master")


def setup_venv() -> None:
    step("venv + deps")
    run(
        f"sudo -u {APP_USER} bash -c '"
        f"cd {APP_DIR} && "
        f"test -d .venv || python3 -m venv .venv && "
        f"./.venv/bin/pip install --upgrade pip -q && "
        f"./.venv/bin/pip install -q -r requirements.txt'",
        check=False,  # requirements set большой, не падаем сразу
    )


def upload_systemd_unit() -> None:
    step("systemd unit")
    unit = textwrap.dedent(f"""\
        [Unit]
        Description=Methodex Secretary API
        After=network.target

        [Service]
        Type=simple
        User={APP_USER}
        Group={APP_USER}
        WorkingDirectory={APP_DIR}
        EnvironmentFile={APP_DIR}/.env
        Environment=GOOGLE_APPLICATION_CREDENTIALS={APP_DIR}/firebase-service-account.json
        ExecStart={APP_DIR}/.venv/bin/python -m uvicorn dev_app:app --host 127.0.0.1 --port 8765
        Restart=on-failure
        RestartSec=3

        [Install]
        WantedBy=multi-user.target
    """)
    tmp = "/tmp/methodex-api.service"
    Path("deploy/_unit.tmp").write_text(unit)
    put("deploy/_unit.tmp", tmp)
    run(f"mv {tmp} /etc/systemd/system/{SERVICE_NAME}.service && "
        f"systemctl daemon-reload && systemctl enable {SERVICE_NAME}")


def upload_nginx() -> None:
    step("nginx")
    cfg = textwrap.dedent("""\
        server {
            listen 80 default_server;
            server_name _;
            client_max_body_size 25M;

            location / {
                proxy_pass http://127.0.0.1:8765;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_read_timeout 120s;
            }
        }
    """)
    tmp = "/tmp/methodex.conf"
    Path("deploy/_nginx.tmp").write_text(cfg)
    put("deploy/_nginx.tmp", tmp)
    run(f"mv {tmp} /etc/nginx/sites-available/methodex && "
        f"ln -sf /etc/nginx/sites-available/methodex /etc/nginx/sites-enabled/methodex && "
        f"rm -f /etc/nginx/sites-enabled/default && "
        f"nginx -t && systemctl reload nginx")


def show_summary() -> None:
    step("CI public key (paste into GitHub Secrets)")
    run(f"cat /home/{APP_USER}/.ssh/id_ed25519.pub")
    step("CI private key (DO NOT print to chat — fetch separately)")
    run(f"echo '/home/{APP_USER}/.ssh/id_ed25519 - copy via SFTP'")


def main() -> None:
    install_packages()
    create_deploy_user()
    gen_ci_ssh_key()
    firewall()
    clone_repo()
    setup_venv()
    upload_systemd_unit()
    upload_nginx()
    show_summary()


if __name__ == "__main__":
    main()
