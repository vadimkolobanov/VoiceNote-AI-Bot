"""Quick диагностика прода."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _ssh import run

run("journalctl -u methodex-api -n 50 --no-pager")
print()
run("ss -ltnp | grep -E '8765|nginx|:80\\b' || true")
print()
run("sleep 5; curl -sv -m 10 http://127.0.0.1:8765/health 2>&1 | tail -20")
print()
run("curl -sv -m 10 http://127.0.0.1/health 2>&1 | tail -20")
