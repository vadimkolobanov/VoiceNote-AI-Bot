"""Update TG_BOT_TOKEN in VPS .env safely."""
import re

NEW_TOKEN = "7941868569:AAEbMBnFpF_vCnVKMkdhcZrDDT7M9ixTF90"
P = "/opt/methodex/.env"

text = open(P).read()
text = re.sub(
    r"^TG_BOT_TOKEN=.*$",
    f"TG_BOT_TOKEN={NEW_TOKEN}",
    text,
    flags=re.M,
)
if not text.endswith("\n"):
    text += "\n"
open(P, "w").write(text)
print("token updated")
