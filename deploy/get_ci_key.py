"""Заберём приватный CI-ключ с VPS и сразу зальём в GitHub Secrets через `gh`.

ssh-ключ при загрузке не печатаем в stdout — пишем в локальный временный файл,
потом gh secret set читает с диска. Файл удаляется в конце.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ssh import get, run  # noqa: E402


HOST = "216.57.108.153"
USER = "deploy"
PORT = "22"


def gh_set(name: str, value: str | bytes) -> None:
    """Положить секрет через gh cli (читает stdin). Не печатает значение."""
    if isinstance(value, str):
        value = value.encode("utf-8")
    p = subprocess.run(
        ["gh", "secret", "set", name],
        input=value,
        check=False,
    )
    if p.returncode != 0:
        sys.exit(f"gh secret set {name} failed: rc={p.returncode}")
    print(f"  ✓ secret {name} updated")


def main() -> None:
    if subprocess.run(["gh", "--version"], capture_output=True).returncode != 0:
        sys.exit("gh CLI not found in PATH")

    # public-key уже видели — а ещё нужно убедиться, что он в authorized_keys
    print("Sanity: public CI key:")
    run(f"cat /home/{USER}/.ssh/id_ed25519.pub")

    # Скачиваем приватный
    print("Fetching private CI key (will be wiped after upload) ...")
    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / "id_ed25519"
        get(f"/home/{USER}/.ssh/id_ed25519", str(local))
        os.chmod(local, 0o600)
        priv = local.read_bytes()

        print("Setting GitHub Secrets ...")
        gh_set("VPS_HOST", HOST)
        gh_set("VPS_USER", USER)
        gh_set("VPS_PORT", PORT)
        gh_set("VPS_SSH_KEY", priv)
        print("Local copy of private key wiped via TemporaryDirectory exit.")


if __name__ == "__main__":
    main()
