#!/usr/bin/env bash
#
# Remove the platform from a shared server, leaving it as it was found.
#
# The counterpart to deploy/setup-shared.sh. It removes only what that script
# created, and it will not remove anything it cannot prove it installed -- if
# MongoDB was already on this box before the platform arrived, it stays.
#
#   sudo bash deploy/teardown-shared.sh
#
# The 7.6 GB of weights are the expensive part to replace: an rsync of roughly
# two hours. Take a snapshot before running this if the platform will be needed
# again, or keep the models and pass KEEP_MODELS=1.
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/somali-nlp}"
APP_USER="${APP_USER:-somali}"
KEEP_MODELS="${KEEP_MODELS:-0}"
KEEP_SWAP="${KEEP_SWAP:-1}"

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
skip() { printf '    skipped: %s\n' "$*"; }

[[ $EUID -eq 0 ]] || { echo "run as root: sudo bash $0" >&2; exit 1; }

cat <<EOF

  This removes the Somali NLP platform from $(hostname).

  Removed:   the somali-nlp service, its nginx vhost, the somali_nlp database,
             the ${APP_USER} user, and ${APP_DIR}$([[ $KEEP_MODELS == 1 ]] && echo " (models kept)")
  Untouched: node, ufw, every other nginx vhost, PostgreSQL, PM2, the ERPs,
             and MongoDB itself if it predated the platform

EOF
read -rp "  Type the hostname to confirm: " CONFIRM
[[ "$CONFIRM" == "$(hostname)" ]] || { echo "  aborted"; exit 1; }

# ---------------------------------------------------------------------------
log "Service"
if systemctl list-unit-files | grep -q '^somali-nlp.service'; then
  systemctl disable --now somali-nlp 2>/dev/null || true
  rm -f /etc/systemd/system/somali-nlp.service
  systemctl daemon-reload
else
  skip "somali-nlp.service was not installed"
fi

# ---------------------------------------------------------------------------
log "Nginx vhost"
# Only the vhost this platform added. The default site and every ERP vhost are
# left exactly as they are.
REMOVED_VHOST=0
for f in /etc/nginx/sites-enabled/somali-nlp \
         /etc/nginx/sites-available/somali-nlp \
         /etc/nginx/conf.d/somali-nlp.conf; do
  [[ -e "$f" ]] && { rm -f "$f"; REMOVED_VHOST=1; }
done
if (( REMOVED_VHOST )); then
  # certbot may have left a redirect block pointing at the vhost that just went.
  nginx -t && systemctl reload nginx
else
  skip "no somali-nlp vhost found"
fi

if [[ -d /etc/letsencrypt/live ]] && ls /etc/letsencrypt/live 2>/dev/null | grep -q .; then
  echo "    note: the TLS certificate is still installed; remove it with"
  echo "          certbot delete --cert-name <domain>"
fi

# ---------------------------------------------------------------------------
log "Database"
if command -v mongosh >/dev/null; then
  mongosh --quiet --eval 'db.getSiblingDB("somali_nlp").dropDatabase()' >/dev/null 2>&1 \
    && echo "    dropped somali_nlp" \
    || skip "could not reach mongod"
else
  skip "mongosh not found"
fi

# MongoDB itself is left running. It may well be that setup-shared.sh installed
# it, but proving that after the fact is not possible, and removing a database
# server from a box with four production applications on a guess is not a trade
# worth making. To remove it deliberately:
echo "    mongod left running. If the platform installed it and nothing else"
echo "    uses it:  apt-get purge -y mongodb-org* && rm -rf /var/lib/mongodb"
if [[ -f /etc/mongod.conf.pre-somali-nlp ]]; then
  echo "    the pre-platform mongod.conf is at /etc/mongod.conf.pre-somali-nlp"
fi

# ---------------------------------------------------------------------------
log "Files"
if [[ -d "$APP_DIR" ]]; then
  if [[ "$KEEP_MODELS" == "1" ]]; then
    find "$APP_DIR" -mindepth 1 -maxdepth 1 ! -name experiments ! -name models -exec rm -rf {} +
    echo "    kept $(du -sh "$APP_DIR" 2>/dev/null | cut -f1) of weights in $APP_DIR"
  else
    echo "    removing $(du -sh "$APP_DIR" 2>/dev/null | cut -f1)"
    rm -rf "$APP_DIR"
  fi
else
  skip "$APP_DIR does not exist"
fi

# ---------------------------------------------------------------------------
log "User"
if id -u "$APP_USER" >/dev/null 2>&1; then
  userdel -r "$APP_USER" 2>/dev/null || userdel "$APP_USER" 2>/dev/null || true
else
  skip "$APP_USER does not exist"
fi

# ---------------------------------------------------------------------------
log "Swap"
# Kept by default. This box had none, and 2 GB of headroom is worth more to the
# ERPs than the disk it occupies; pass KEEP_SWAP=0 to restore the original state.
if [[ "$KEEP_SWAP" == "0" ]] && swapon --show | grep -q /swapfile; then
  swapoff /swapfile
  rm -f /swapfile
  sed -i '\|^/swapfile|d' /etc/fstab
  echo "    removed"
else
  skip "swapfile kept (KEEP_SWAP=0 to remove)"
fi

log "Done"
free -h
df -h /
