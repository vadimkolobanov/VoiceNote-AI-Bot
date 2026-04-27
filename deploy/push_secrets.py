"""Заливаем секреты на VPS из локалки.

Локальные .env и firebase-service-account.json идут в /opt/methodex/.
Делаем их доступными для service-юзера.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ssh import run, put  # noqa: E402

APP_USER = "deploy"
APP_DIR = "/opt/methodex"


def _normalize_env(local_path: str) -> str:
    """LF-окончания + APP_VERSION прода. Возвращает путь к нормализованному tmp."""
    raw = Path(local_path).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    out = Path("deploy/_env.tmp")
    out.write_bytes(raw)
    return str(out)


def main() -> None:
    if not Path(".env").exists():
        sys.exit(".env not found locally")
    if not Path("firebase-service-account.json").exists():
        sys.exit("firebase-service-account.json not found locally")

    print("Uploading .env (LF normalized) ...")
    put(_normalize_env(".env"), "/tmp/.env.upload")
    run(f"mv /tmp/.env.upload {APP_DIR}/.env && "
        f"chown {APP_USER}:{APP_USER} {APP_DIR}/.env && "
        f"chmod 600 {APP_DIR}/.env")

    print("Uploading firebase service account ...")
    put("firebase-service-account.json", "/tmp/fb.json")
    run(f"mv /tmp/fb.json {APP_DIR}/firebase-service-account.json && "
        f"chown {APP_USER}:{APP_USER} {APP_DIR}/firebase-service-account.json && "
        f"chmod 600 {APP_DIR}/firebase-service-account.json")

    print("Running alembic migrations (dotenv autoload) ...")
    run(f"sudo -u {APP_USER} bash -c "
        f"'cd {APP_DIR} && ./.venv/bin/python -m alembic upgrade head'")

    print("Starting service ...")
    run("systemctl restart methodex-api && sleep 3 && "
        "systemctl --no-pager status methodex-api | head -20")

    print("Smoke test localhost ...")
    run("curl -s -m 5 http://127.0.0.1:8765/health || true")
    print()
    print("Smoke test through nginx ...")
    run("curl -s -m 5 http://127.0.0.1/health || true")


if __name__ == "__main__":
    main()
