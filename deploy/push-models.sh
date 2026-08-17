#!/usr/bin/env bash
#
# Send the trained models from a Windows workstation, in tiers, using only ssh
# and tar.
#
# deploy/sync-models.sh needs rsync, which Git Bash does not ship. This does the
# same job over `tar | ssh`, and adds something rsync did not: it sends the
# platform in an order that makes it useful early.
#
#   bash deploy/push-models.sh root@203.0.113.10
#   KEY=~/.ssh/mykey bash deploy/push-models.sh root@203.0.113.10
#
# Tier 1 is 297 MB and takes a few minutes. It carries the LinearSVC that scores
# 94.79% -- the best model on the platform -- every BiLSTM, both tokenisers, the
# held-out test splits and the comparison tables. The site is fully usable when
# it lands.
#
# Tier 2 is the ten fine-tuned transformers, 7.5 GB, sent best-first: AfriBERTa
# (84.0%) and SomBERTa (83.1%) lead because they are both the most accurate of
# the ten and the smallest, so the first 911 MB buys the two that a demonstration
# actually wants. mBERT (65.9%) goes last.
#
# The catalogue is built from the files present on disk, so a transformer that
# has not arrived is simply absent from the dropdown rather than listed and
# broken -- stopping this script early leaves a working site, not a damaged one.
# Restart the service to pick up what has landed:
#
#   systemctl restart somali-nlp
#
set -euo pipefail

TARGET="${1:-}"
APP_DIR="${APP_DIR:-/opt/somali-nlp}"
KEY="${KEY:-}"
ONLY="${ONLY:-}"          # "tier1" or "tier2" to send just one
RESTART="${RESTART:-0}"   # 1 = restart the service after each transformer

[[ -n "$TARGET" ]] || { echo "usage: bash deploy/push-models.sh user@server-ip" >&2; exit 1; }
[[ -d experiments ]] || { echo "run this from the repository root" >&2; exit 1; }

SSH_OPTS=()
[[ -n "$KEY" ]] && SSH_OPTS=(-i "$KEY" -o IdentitiesOnly=yes)

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }

rsh() { ssh "${SSH_OPTS[@]}" "$TARGET" "$@"; }

# tar over ssh: one connection per call, directory structure preserved, and no
# dependency on rsync being installed anywhere.
send() {
  local root="$1"; shift
  tar czf - -C "$root" "$@" | rsh "mkdir -p '$APP_DIR' && tar xzf - -C '$APP_DIR'"
}

human() { numfmt --to=iec --suffix=B "$1" 2>/dev/null || echo "$1 bytes"; }

log "Checking the connection"
# $APP_DIR expands here, deliberately; df must not, or it would report this
# workstation's disk rather than the server's.
FREE=$(rsh "mkdir -p '$APP_DIR' && df -BG --output=avail / | tail -1 | tr -d ' '") \
  || { echo "cannot reach $TARGET" >&2; exit 1; }
info "reachable, $FREE free on the server"

# ---------------------------------------------------------------------------
# Tier 1 -- everything that is not a fine-tuned transformer.
# ---------------------------------------------------------------------------
if [[ "$ONLY" != "tier2" ]]; then
  log "Tier 1: the platform itself (~297 MB)"

  TIER1=()
  for e in experiment_1_stopwords_included experiment_2_stopwords_removed; do
    [[ -d "experiments/$e" ]] || continue
    TIER1+=("experiments/$e/results")
    TIER1+=("experiments/$e/models/traditional_ml")
    TIER1+=("experiments/$e/models/deep_learning")
    for f in data/tokenizer.joblib data/clean_test.csv data/full_labeled_dataset.csv \
             models/transformers/MiniTransformer_Keras.keras; do
      [[ -f "experiments/$e/$f" ]] && TIER1+=("experiments/$e/$f")
    done
  done
  [[ -f models/category_classifier.joblib ]] && TIER1+=("models/category_classifier.joblib")

  info "${#TIER1[@]} paths"
  send . "${TIER1[@]}"
  info "sent"

  log "Tier 1 is enough to run the site"
  cat <<EOF
    On the server:

        chown -R somali:somali $APP_DIR
        systemctl restart somali-nlp
        curl -s localhost:8000/api/models | python3 -c 'import json,sys; print(len(json.load(sys.stdin)),"models")'

    Leave this script running; the transformers are next.
EOF
fi

# ---------------------------------------------------------------------------
# Tier 2 -- the fine-tuned transformers, best-first.
#
# The _balanced_refresh and _pre_483 directories are deliberately absent: they
# were superseded by the 483-stopword retrain and are not published.
# ---------------------------------------------------------------------------
if [[ "$ONLY" != "tier1" ]]; then
  E1=experiments/experiment_1_stopwords_included/models/transformers
  E2=experiments/experiment_2_stopwords_removed/models/transformers

  MODELS=(
    "$E2/AfriBERTa_FineTuned"    # 84.0%, 430 MB -- best and smallest
    "$E2/SomBERTa_FineTuned"     # 83.1%, 481 MB
    "$E1/AfriBERTa_FineTuned"
    "$E1/SomBERTa_FineTuned"
    "$E2/AfroXLMR_FineTuned"     # 79.7%, 1.1 GB
    "$E1/AfroXLMR_FineTuned"
    "$E2/xlm-roberta-base"       # 69.8%, 1.1 GB
    "$E1/xlm-roberta-base"
    "$E2/mBERT_FineTuned"        # 65.9%, 682 MB -- weakest, sent last
    "$E1/mBERT_FineTuned"
  )

  log "Tier 2: ${#MODELS[@]} transformers, best-first"

  n=0
  for dir in "${MODELS[@]}"; do
    n=$((n + 1))
    [[ -d "$dir" ]] || { info "[$n/${#MODELS[@]}] $dir -- not present locally, skipped"; continue; }

    weights="$dir/model.safetensors"
    [[ -f "$weights" ]] || { info "[$n/${#MODELS[@]}] $dir -- no model.safetensors, skipped"; continue; }

    local_bytes=$(stat -c%s "$weights")
    remote_bytes=$(rsh "stat -c%s '$APP_DIR/$weights' 2>/dev/null || echo 0")

    exp=$(echo "$dir" | grep -o 'experiment_[0-9]')
    label="[$n/${#MODELS[@]}] $exp/$(basename "$dir")"

    if [[ "$local_bytes" == "$remote_bytes" ]]; then
      info "$label -- already there ($(human "$local_bytes")), skipped"
      continue
    fi

    info "$label -- sending $(human "$local_bytes")"
    started=$(date +%s)
    # The training log is a few KB of loss curves the platform never reads, and
    # checkpoint-* directories are optimizer state from mid-training.
    tar czf - --exclude='*_training_log.csv' --exclude='checkpoint-*' --exclude='optimizer.pt' \
        -C . "$dir" \
      | rsh "tar xzf - -C '$APP_DIR'"
    elapsed=$(( $(date +%s) - started ))
    info "$label -- done in $((elapsed / 60))m $((elapsed % 60))s"

    if [[ "$RESTART" == "1" ]]; then
      rsh "chown -R somali:somali '$APP_DIR' && systemctl restart somali-nlp" || true
      info "$label -- service restarted, model is live"
    fi
  done
fi

log "Finished"
cat <<EOF
    On the server:

        chown -R somali:somali $APP_DIR
        systemctl restart somali-nlp
        curl -s localhost:8000/api/models | python3 -c 'import json,sys; print(len(json.load(sys.stdin)),"models")'

    This script is safe to re-run: anything already transferred is skipped by
    size, so an interrupted transfer resumes at the model it was on.
EOF
