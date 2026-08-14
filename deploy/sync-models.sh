#!/usr/bin/env bash
#
# Send the trained models to the server. Run from the machine that trained them,
# from the repository root:
#
#     bash deploy/sync-models.sh root@203.0.113.10
#
# Weights are not in git: the project carries 7.7 GB and GitHub's free LFS tier
# allows 1 GB, so pushing them produced pointer stubs and a clone that could not
# start. They travel here instead, over rsync, which costs nothing and resumes
# where it stopped if the connection drops.
#
# Only what the platform serves is sent. The experiments directory also holds
# training-time artefacts -- fastText and word2vec embeddings, tokenised caches,
# optimizer checkpoints, and the pre-483 backups -- which together are larger
# than the models themselves and are never read at inference.
#
set -euo pipefail

TARGET="${1:-}"
APP_DIR="${APP_DIR:-/opt/somali-nlp}"

if [[ -z "$TARGET" ]]; then
  echo "usage: bash deploy/sync-models.sh user@server-ip" >&2
  exit 1
fi
[[ -d experiments ]] || { echo "run this from the repository root" >&2; exit 1; }

echo "Sending models to $TARGET:$APP_DIR"
echo

# --include rules are read in order and the trailing --exclude='*' drops the rest,
# so directories must be admitted before the files inside them can match.
rsync -avz --partial --progress --human-readable \
  --include='*/' \
  \
  `# traditional ML: the champion LinearSVC (94.79%) and its three companions` \
  --include='experiment_*/models/traditional_ml/*.joblib' \
  \
  `# BiLSTM and MiniTransformer, embeddings already baked into the graph` \
  --include='experiment_*/models/deep_learning/*.keras' \
  --include='experiment_*/models/transformers/MiniTransformer_Keras.keras' \
  \
  `# fine-tuned transformers: weights, config and tokeniser, nothing else` \
  --include='experiment_*/models/transformers/*/model.safetensors' \
  --include='experiment_*/models/transformers/*/config.json' \
  --include='experiment_*/models/transformers/*/tokenizer*' \
  --include='experiment_*/models/transformers/*/vocab*' \
  --include='experiment_*/models/transformers/*/merges.txt' \
  --include='experiment_*/models/transformers/*/special_tokens_map.json' \
  --include='experiment_*/models/transformers/*/sentencepiece.bpe.model' \
  --include='experiment_*/models/transformers/*/spiece.model' \
  \
  `# the Keras word index, and the test split the paragraph measurement used` \
  --include='experiment_*/data/tokenizer.joblib' \
  --include='experiment_*/data/clean_test.csv' \
  --include='experiment_*/data/full_labeled_dataset.csv' \
  \
  `# per-model accuracy tables the comparison pages read` \
  --include='experiment_*/results/**' \
  --include='paragraph_accuracy.json' \
  \
  `# superseded by the 483-stopword retrain, and training-only artefacts` \
  --exclude='*_balanced_refresh/' \
  --exclude='BiLSTM_MultilingualEmbeddings*' \
  --exclude='_pre_483*' \
  --exclude='checkpoint-*' \
  --exclude='*' \
  \
  experiments/ "$TARGET:$APP_DIR/experiments/"

# The topic classifier is separate from the two experiments and is what puts
# "Politics" or "Sports" beside a verdict.
rsync -avz --partial --progress models/category_classifier.joblib \
  "$TARGET:$APP_DIR/models/" 2>/dev/null || true

echo
echo "  Done. On the server:"
echo
echo "      chown -R somali:somali $APP_DIR"
echo "      systemctl restart somali-nlp"
echo "      journalctl -u somali-nlp -f     # watch it load"
echo
