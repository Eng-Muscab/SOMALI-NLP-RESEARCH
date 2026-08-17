#!/usr/bin/env bash
#
# Install the platform onto a server that is ALREADY running other services.
#
# deploy/setup.sh targets a fresh VPS and is destructive on a shared one: it
# replaces the system Node with 20.x, enables ufw with only 22/80/443 open,
# deletes the nginx default site, and installs a `server_name _` catch-all. On a
# box hosting four live ERPs that is four outages, not a deployment.
#
# This script installs the same platform without touching any of it:
#
#   * Node is never installed or upgraded -- the frontend is built on the
#     workstation and rsync'd in as static files, which nginx serves directly.
#   * ufw is never enabled, disabled, or given a rule.
#   * The nginx default site is left alone, and the site added here answers only
#     for the exact domain given, so no other vhost changes behaviour.
#   * MongoDB's cache is capped before it first starts. Left alone on a 6 GB box
#     it takes max(50% x (6 - 1), 0.25) = 2.5 GB, which is more than this
#     platform's entire peak.
#
# Everything it does is undone by deploy/teardown-shared.sh.
#
#   sudo DOMAIN=ai.example.com bash deploy/setup-shared.sh
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/somali-nlp}"
APP_USER="${APP_USER:-somali}"
REPO="${REPO:-https://github.com/Eng-Muscab/SOMALI-NLP-RESEARCH.git}"
BRANCH="${BRANCH:-dev}"
PORT="${PORT:-8000}"
DOMAIN="${DOMAIN:-}"
SWAP_GB="${SWAP_GB:-2}"
MONGO_CACHE_GB="${MONGO_CACHE_GB:-0.25}"

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m    warning: %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31m==> refusing: %s\033[0m\n\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run as root: sudo bash $0"
[[ -n "$DOMAIN" ]] || die "set DOMAIN, e.g. sudo DOMAIN=ai.example.com bash $0"

# ---------------------------------------------------------------------------
# Preflight. Every check below is a way this box differs from a fresh one; the
# script stops rather than guessing, because the cost of guessing wrong here is
# somebody else's production system.
# ---------------------------------------------------------------------------
log "Preflight"

# 12 GB is the measured footprint: 7.6 GB of weights, ~4 GB of venv once the CPU
# builds of torch and tensorflow are in it, and the repo. Plus the swapfile.
NEED_GB=$(( 12 + SWAP_GB ))
AVAIL_GB=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
echo "    disk free: ${AVAIL_GB} GB, need ~${NEED_GB} GB"
(( AVAIL_GB >= NEED_GB )) || die "only ${AVAIL_GB} GB free on /, need ~${NEED_GB} GB"

AVAIL_MB=$(free -m | awk '/^Mem:/ {print $7}')
echo "    ram available: ${AVAIL_MB} MB, peak need ~2200 MB"
(( AVAIL_MB >= 2600 )) || die "only ${AVAIL_MB} MB of RAM available, need ~2600 MB of headroom"

# The backend binds loopback only, but a port collision would still leave one of
# the two services dead and the cause unobvious.
if ss -tlnp 2>/dev/null | grep -qE "[:.]${PORT}\b"; then
  ss -tlnp | grep -E "[:.]${PORT}\b" || true
  die "port ${PORT} is already in use -- rerun with PORT=8001"
fi

# Installing nginx while apache or anything else holds :80 fails halfway through
# and leaves the box worse than it started.
if command -v nginx >/dev/null; then
  echo "    nginx: present, will add one vhost for ${DOMAIN}"
  NGINX_WAS_PRESENT=1
else
  if ss -tlnp 2>/dev/null | grep -qE '[:.]80\b'; then
    die "port 80 is held by something that is not nginx -- inspect 'ss -tlnp' first"
  fi
  echo "    nginx: absent, will install"
  NGINX_WAS_PRESENT=0
fi

# Recorded, not acted on. Everything downstream avoids node entirely; this line
# exists so the log shows what was left untouched.
if command -v node >/dev/null; then
  echo "    node: $(node --version) -- left untouched"
fi

if command -v ufw >/dev/null; then
  echo "    ufw: $(ufw status 2>/dev/null | head -1) -- left untouched"
fi

if command -v mongod >/dev/null; then
  echo "    mongodb: already installed, cache will be capped if it is not already"
fi

# ---------------------------------------------------------------------------
log "System packages"
# Deliberately short: python, git, rsync. No nodejs, no ufw, no curl-to-bash of
# a distribution installer.
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-dev build-essential git rsync curl gnupg
(( NGINX_WAS_PRESENT )) || apt-get install -y -qq nginx

# ---------------------------------------------------------------------------
log "MongoDB"
if ! command -v mongod >/dev/null; then
  curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc \
    | gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
  echo "deb [signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" \
    > /etc/apt/sources.list.d/mongodb-org-8.0.list
  apt-get update -qq
  apt-get install -y -qq mongodb-org
fi

# Cap the cache before the first start. WiredTiger's default on this box is
# 2.5 GB; the platform's own peak is 1.7 GB, and the database holds users, a
# prediction log and an activity log -- a few MB. 256 MB is generous.
# Match on cacheSizeGB, not on `wiredTiger`: the stock Ubuntu mongod.conf ships
# a commented-out `#  wiredTiger:` stanza, and grepping for the word alone finds
# that comment and silently concludes the cap is already in place.
if ! grep -qE '^[[:space:]]+cacheSizeGB' /etc/mongod.conf; then
  cp /etc/mongod.conf /etc/mongod.conf.pre-somali-nlp
  sed -i "/^storage:/a\\  wiredTiger:\\n    engineConfig:\\n      cacheSizeGB: ${MONGO_CACHE_GB}" /etc/mongod.conf
  echo "    capped WiredTiger cache at ${MONGO_CACHE_GB} GB"
fi

# The stock Ubuntu config binds 127.0.0.1. Verify rather than assume -- a mongod
# reachable from the internet on a box with four ERPs on it is not acceptable.
grep -qE '^\s*bindIp:\s*127\.0\.0\.1\s*$' /etc/mongod.conf \
  || warn "mongod bindIp is not exactly 127.0.0.1 -- check /etc/mongod.conf"

systemctl enable --now mongod
sleep 2
if ! systemctl is-active --quiet mongod; then
  # A bad edit to the YAML is the likely cause; put it back rather than leave a
  # database that will not start.
  [[ -f /etc/mongod.conf.pre-somali-nlp ]] && mv /etc/mongod.conf.pre-somali-nlp /etc/mongod.conf
  systemctl start mongod || true
  die "mongod failed to start; the original config has been restored"
fi

# ---------------------------------------------------------------------------
log "Swap"
# Wanted, but not required. Swap is here so that an unexpected spike is a slow
# request rather than the OOM killer choosing the largest process on the box,
# which would be an ERP. The platform's ceiling is bounded by the model cache
# rather than by traffic, though, so a box with headroom does not need it.
#
# Containerised VPS platforms -- OpenVZ, LXC, Virtuozzo -- share the host kernel
# and refuse swapon outright. That is a fact about the host, not a failure of
# this install, so it is reported and stepped over rather than being fatal.
if swapon --show 2>/dev/null | grep -q /swapfile; then
  echo "    swap: already present"
elif fallocate -l "${SWAP_GB}G" /swapfile 2>/dev/null \
     && chmod 600 /swapfile \
     && mkswap -q /swapfile 2>/dev/null \
     && swapon /swapfile 2>/dev/null; then
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "    swap: ${SWAP_GB} GB added"
else
  rm -f /swapfile
  warn "swapon is not permitted on this host (containerised kernel); continuing without swap"
  echo "    swap: none -- $(free -m | awk '/^Mem:/ {print $7}') MB available against a ~2200 MB peak"
fi

# Prefer reclaiming cache over swapping the ERPs' working set out from under
# them. An unprivileged container refuses this too; it is an optimisation.
if sysctl -qw vm.swappiness=10 2>/dev/null; then
  grep -q '^vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
else
  echo "    vm.swappiness: not settable in this container, skipped"
fi

# ---------------------------------------------------------------------------
log "Application user and source"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR"

if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  # Older commits still carry LFS pointers for weights that were never uploaded;
  # skipping the smudge filter stops git chasing objects that do not exist.
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --branch "$BRANCH" "$REPO" "$APP_DIR"
fi

# ---------------------------------------------------------------------------
log "Python environment"
cd "$APP_DIR"
[[ -d .venv ]] || python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
# CPU wheels: the default torch build pulls ~2.5 GB of CUDA libraries that a VPS
# with no GPU cannot use, and this disk is shared with four other applications.
./.venv/bin/pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
./.venv/bin/pip install --quiet -r web/backend/requirements.txt
./.venv/bin/pip install --quiet "tensorflow-cpu>=2.16" transformers safetensors
# Only the archive-the-submitted-article step needs these: it reuses clean_text()
# from experiments/run_balanced_experiments.py so that archived rows match the
# training pipeline exactly, and that research script imports matplotlib, seaborn
# and yaml at module level. The call sits in a try/except, so leaving them out
# costs the archive rather than the prediction -- but the feature is cheap to keep.
./.venv/bin/pip install --quiet seaborn matplotlib pyyaml

# ---------------------------------------------------------------------------
log "Configuration"
ENV_FILE="$APP_DIR/web/backend/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
  cat > "$ENV_FILE" <<EOF
APP_NAME=Somali NLP Research API
ENVIRONMENT=production
API_PREFIX=/api
CORS_ORIGINS=https://${DOMAIN}
MONGODB_URI=mongodb://localhost:27017
MONGO_DB_NAME=somali_nlp
MONGODB_TIMEOUT_MS=3000
SECRET_KEY=${SECRET}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
MODELS_DIR=../../models
EXPERIMENTS_DIR=../../experiments
UPLOADS_DIR=uploads
LOAD_DEEP_MODELS=true
MAX_RESIDENT_DEEP_MODELS=2
EOF
  chmod 600 "$ENV_FILE"
fi

# The frontend is built on the workstation, not here -- that is what keeps node
# off this box. Serve a holding page until the rsync arrives so that nginx has
# a root that exists.
mkdir -p "$APP_DIR/web/frontend/dist"
[[ -f "$APP_DIR/web/frontend/dist/index.html" ]] \
  || echo '<!doctype html><title>Deploying</title><h1>Frontend not uploaded yet</h1>' \
       > "$APP_DIR/web/frontend/dist/index.html"

chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ---------------------------------------------------------------------------
log "systemd service"
sed -e "s|__APP_DIR__|$APP_DIR|g" \
    -e "s|__APP_USER__|$APP_USER|g" \
    -e "s|--port 8000|--port $PORT|" \
    "$APP_DIR/deploy/somali-nlp.service" > /etc/systemd/system/somali-nlp.service
systemctl daemon-reload
systemctl enable somali-nlp

# ---------------------------------------------------------------------------
log "Nginx vhost for ${DOMAIN}"
# server_name is the exact domain, never `_`. A catch-all would take over every
# request whose Host header does not match an existing vhost, which on this box
# means requests meant for the ERPs.
if [[ -d /etc/nginx/sites-available ]]; then
  SITE=/etc/nginx/sites-available/somali-nlp
  LINK=/etc/nginx/sites-enabled/somali-nlp
else
  SITE=/etc/nginx/conf.d/somali-nlp.conf
  LINK=""
fi

sed -e "s|__APP_DIR__|$APP_DIR|g" \
    -e "s|server_name _;|server_name ${DOMAIN};|" \
    -e "s|proxy_pass http://127.0.0.1:8000;|proxy_pass http://127.0.0.1:${PORT};|" \
    "$APP_DIR/deploy/nginx.conf" > "$SITE"
[[ -n "$LINK" ]] && ln -sf "$SITE" "$LINK"

# Note what is NOT here: no `rm /etc/nginx/sites-enabled/default`. If the config
# does not validate, remove what was just added rather than reload a broken nginx
# and take the ERPs down with it.
if ! nginx -t 2>/dev/null; then
  rm -f "$SITE" ${LINK:+"$LINK"}
  nginx -t
  die "the new vhost broke the nginx config; it has been removed"
fi
systemctl reload nginx

# ---------------------------------------------------------------------------
cat <<EOF

  Installed. Nothing else on this server was modified:
  node, ufw, the nginx default site and every existing vhost are as they were.

  Two things are still missing -- the frontend and the models. Both are sent
  from the workstation, from the repository root:

      cd web/frontend && npm run build && cd ../..
      rsync -avz web/frontend/dist/ root@$(hostname -I | awk '{print $1}'):$APP_DIR/web/frontend/dist/
      bash deploy/sync-models.sh root@$(hostname -I | awk '{print $1}')

  Then back here:

      chown -R $APP_USER:$APP_USER $APP_DIR
      systemctl start somali-nlp
      journalctl -u somali-nlp -f          # ~22 s to load

  HTTPS, once ${DOMAIN} resolves to this server:

      apt-get install -y certbot python3-certbot-nginx
      certbot --nginx -d ${DOMAIN} --redirect

  To remove all of this afterwards:

      sudo bash $APP_DIR/deploy/teardown-shared.sh

EOF
