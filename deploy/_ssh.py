"""Утилитка для SSH-команд на VPS из локальной разработки.

Дев-only хелпер: даёт `run("...")` и `put(local, remote)`. Юзается из
локальных скриптов сетапа. На прод сам не уходит — на проде CI делает то же
через ssh-action.
"""
from __future__ import annotations

import io
import os
import sys

import paramiko

# stdout под utf-8 — на Windows по умолчанию cp1251 ломается на → и ё
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HOST = os.environ.get("VPS_HOST", "216.57.108.153")
USER = os.environ.get("VPS_USER", "root")
PASS = os.environ.get("VPS_PASS", "")


def _client() -> paramiko.SSHClient:
    if not PASS:
        sys.exit("VPS_PASS env var is empty — set it before running.")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20, look_for_keys=False, allow_agent=False)
    return c


def run(cmd: str, *, check: bool = True, quiet: bool = False) -> tuple[int, str, str]:
    with _client() as c:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=300)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
    if not quiet:
        if out:
            print(out, end="")
        if err:
            print(err, end="", file=sys.stderr)
        print(f"--- rc={rc} cmd={cmd[:80]}")
    if check and rc != 0:
        sys.exit(f"command failed: {cmd}")
    return rc, out, err


def put(local: str, remote: str) -> None:
    with _client() as c:
        with c.open_sftp() as sftp:
            sftp.put(local, remote)
            print(f"--- uploaded {local} -> {remote}")


def get(remote: str, local: str) -> None:
    with _client() as c:
        with c.open_sftp() as sftp:
            sftp.get(remote, local)
            print(f"--- downloaded {remote} -> {local}")


if __name__ == "__main__":
    # quick smoke
    run("uname -a; cat /etc/os-release | head -3; whoami")
