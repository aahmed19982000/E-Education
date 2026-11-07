#!/usr/bin/env bash
# One-command deploy, run on the server (by hand or by the GitHub "Deploy" workflow).
# Backs up the database, pulls main, installs requirements, migrates, collects static files,
# restarts gunicorn and checks the site answers. Any failing step stops the deploy.
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/E-Education}"
SERVICE="${SERVICE:-gunicorn}"
cd "$APP_DIR"

set -a; . ./.env; set +a

echo "==> Database backup"
mkdir -p "$HOME/backups"
BACKUP="$HOME/backups/${DJANGO_DB_NAME}-$(date +%F-%H%M).sql"
sudo -n -u postgres pg_dump "$DJANGO_DB_NAME" > "$BACKUP"
test -s "$BACKUP"
ls -1t "$HOME"/backups/*.sql | tail -n +15 | xargs -r rm --   # keep the 14 newest

echo "==> Pull"
git pull --ff-only origin main
git log --oneline -1

echo "==> Requirements"
./venv/bin/pip install -q -r requirements.txt

echo "==> Migrate"
./venv/bin/python manage.py migrate --noinput

echo "==> Static files"
./venv/bin/python manage.py collectstatic --noinput | tail -n 1

echo "==> Restart"
sudo -n systemctl restart "$SERVICE"
sleep 3
systemctl is-active --quiet "$SERVICE"

echo "==> Health check"
curl -fsS -o /dev/null --max-time 20 http://127.0.0.1/ -H "Host: ${DEPLOY_HOST_HEADER:-137.184.222.204}"

echo "Deployed $(git rev-parse --short HEAD). Backup: $BACKUP"
