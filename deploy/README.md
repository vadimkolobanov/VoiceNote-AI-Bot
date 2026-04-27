# Deploy

Прод живёт на VPS Timeweb (Frankfurt, Ubuntu 24.04).
- API: `http://216.57.108.153/health`
- Сервис: `methodex-api.service` (systemd)
- Reverse-proxy: nginx → 127.0.0.1:8765
- Юзер запуска: `deploy` (uid 1000), home `/opt/methodex`

## Что уже сделано

- `deploy/bootstrap.py` поднял VPS с нуля: установил python/nginx/git, создал `deploy`, открыл UFW 22/80/443, склонировал репо, поставил venv-зависимости, развернул systemd unit и nginx-конфиг
- `deploy/push_secrets.py` залил `.env` и `firebase-service-account.json`, прогнал миграции
- На VPS сгенерирован отдельный SSH-ключ для CI (`/home/deploy/.ssh/id_ed25519`), его публичная часть лежит в `authorized_keys` того же `deploy`. Приватная часть сохранена локально в `deploy/secrets/ci_id_ed25519` (gitignored)

## Один раз — добавить 4 секрета в GitHub

Settings → Secrets and variables → Actions → New repository secret. Нужно создать:

| Имя | Значение |
|---|---|
| `VPS_HOST` | `216.57.108.153` |
| `VPS_USER` | `deploy` |
| `VPS_PORT` | `22` |
| `VPS_SSH_KEY` | содержимое файла `deploy/secrets/ci_id_ed25519` (включая `-----BEGIN OPENSSH PRIVATE KEY-----` и `-----END OPENSSH PRIVATE KEY-----`, целиком) |

Альтернатива — через `gh` CLI:
```bash
gh auth login                       # один раз
gh secret set VPS_HOST  -b 216.57.108.153
gh secret set VPS_USER  -b deploy
gh secret set VPS_PORT  -b 22
gh secret set VPS_SSH_KEY < deploy/secrets/ci_id_ed25519
```

## Дальше

После того как секреты на месте, любой `git push` в `master`, который трогает `src/**`, `alembic/**`, `requirements.txt`, `dev_app.py`, `deploy/**` или сам workflow — будет автоматически выкатывать прод.

Workflow: `.github/workflows/deploy.yml`. Делает:
1. Подключается по ssh к VPS как `deploy`
2. `git fetch && reset --hard origin/master`
3. `pip install -r requirements.txt`
4. `alembic upgrade head`
5. `sudo systemctl restart methodex-api` (узкий sudoers разрешает только это)
6. Smoke-test `/health`

Падает на любом шаге → деплой откатывается (рестарт сервиса не делается, prev binary продолжает работать).

## Ручные команды

| | |
|---|---|
| Применить апдейт без CI | `python deploy/push_secrets.py` (если поменял `.env` или firebase JSON) |
| Посмотреть логи | `python deploy/check.py` |
| Перезапустить руками | через `_ssh.py`: `python -c "import sys; sys.path.insert(0,'deploy'); from _ssh import run; run('systemctl restart methodex-api')"` |

## Что ещё надо сделать

- [ ] Купить домен (`metodex.ru` или похожий)
- [ ] DNS-A на `216.57.108.153`
- [ ] `certbot --nginx` для HTTPS
- [ ] Поменять `API_BASE_URL` в release-сборке мобилки на новый домен
- [ ] Сменить root-пароль VPS (был засвечен), отключить root-логин по SSH
