#!/usr/bin/env bash
#
# One-time server setup for the Somali AI-text-detection platform.
#
# Target: a fresh Ubuntu 24.04 VPS with 6 GB RAM, 4 vCPU and 30 GB disk. Run it
# once as root; it is safe to re-run, because every step checks before acting.
#
#   bash deploy/setup.sh
#
# What it does NOT do is copy the trained models. Those are 7.7 GB and are sent
# separately with deploy/sync-models.sh from the machine that trained them --
# git holds the code, not the weights.
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/somali-nlp}"
APP_USER="${APP_USER:-somali}"
REPO="${REPO:-https://github.com/Eng-Muscab/SOMALI-NLP-RESEARCH.git}"
BRANCH="${BRANCH:-dev}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

[[ $EUID -eq 0 ]] || { echo "Run as root: sudo bash $0" >&2; exit 1; }

log "System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  python3 python3-venv python3-dev build-essential \
  git curl gnupg nginx rsync ufw

log "MongoDB 8.0"
if ! command -v mongod >/dev/null; then
  curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc \
    | gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
  echo "deb [signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" \
    > /etc/apt/sources.list.d/mongodb-org-8.0.list
  apt-get update -qq
  apt-get install -y -qq mongodb-org
fi
systemctl enable --now mongod

log "Node.js 20 (to build the frontend)"
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
  apt-get install -y -qq nodejs
fi

log "Swap"
# Never expected to be touched: the backend peaks at ~1.7 GB of the 6 GB. It is
# here so that two people selecting different transformers at the same moment
# get a slow response instead of an out-of-memory kill.
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap -q /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

log "Application user and directory"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR"

log "Source"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  # LFS pointers from before the weights were removed from git still exist in
  # older commits; skipping the smudge filter stops git trying to fetch objects
  # that were never uploaded, and --depth 1 avoids that history altogether.
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --branch "$BRANCH" "$REPO" "$APP_DIR"
fi

log "Python environment"
cd "$APP_DIR"
[[ -d .venv ]] || python3 -m venv .venv
# CPU-only wheels: the GPU builds of torch pull ~2.5 GB of CUDA libraries that
# cannot be used on a VPS with no GPU, and would not fit the 30 GB disk.
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
./.venv/bin/pip install --quiet -r web/backend/requirements.txt
./.venv/bin/pip install --quiet "tensorflow-cpu>=2.16" transformers safetensors gunicorn

log "Secrets"
ENV_FILE="$APP_DIR/web/backend/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$APP_DIR/web/backend/.env.example" "$ENV_FILE" 2>/dev/null || touch "$ENV_FILE"
  # A fresh signing key, generated here and never committed. The placeholder that
  # used to sit in git would let anyone mint an admin token.
  SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
  {
    grep -v '^SECRET_KEY=' "$ENV_FILE" 2>/dev/null || true
    echo "SECRET_KEY=$SECRET"
    echo "ENVIRONMENT=production"
    echo "LOAD_DEEP_MODELS=true"
    echo "MAX_RESIDENT_DEEP_MODELS=2"
  } > "$ENV_FILE.new"
  mv "$ENV_FILE.new" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

log "Frontend build"
cd "$APP_DIR/web/frontend"
npm ci --silent 2>/dev/null || npm install --silent
npm run build --silent
# node_modules is 127 MB of build-time-only files; the disk is better spent on
# the models, and `npm ci` restores it whenever the frontend changes.
rm -rf node_modules

log "Permissions"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

log "systemd service"
install -m 644 "$APP_DIR/deploy/somali-nlp.service" /etc/systemd/system/somali-nlp.service
sed -i "s|__APP_DIR__|$APP_DIR|g; s|__APP_USER__|$APP_USER|g" /etc/systemd/system/somali-nlp.service
systemctl daemon-reload
systemctl enable somali-nlp

log "Nginx"
install -m 644 "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/somali-nlp
sed -i "s|__APP_DIR__|$APP_DIR|g" /etc/nginx/sites-available/somali-nlp
ln -sf /etc/nginx/sites-available/somali-nlp /etc/nginx/sites-enabled/somali-nlp
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

log "Firewall"
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable >/dev/null

cat <<EOF

  Setup complete. The models are not here yet.

  From the machine that holds them, run:

      bash deploy/sync-models.sh root@$(curl -s -4 ifconfig.me 2>/dev/null || echo YOUR_SERVER_IP)

  then back here:

      systemctl start somali-nlp
      systemctl status somali-nlp

  The site will answer on  http://$(curl -s -4 ifconfig.me 2>/dev/null || echo YOUR_SERVER_IP)

EOF
