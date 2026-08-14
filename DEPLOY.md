# Deploying the platform

Everything here was measured on the running system, not estimated.

## Why the models are not in git

The trained weights are 7.6 GB. GitHub's free Git LFS tier allows 1 GB, so the
push uploaded the pointer files and silently dropped the objects behind them: a
`git clone` produced 135-byte stubs where the models should be, and the platform
would not start. Weights are not source. Git carries the code that loads them
(25 MB, a few seconds to clone) and the weights travel separately over `rsync`,
which costs nothing and resumes if the connection drops.

## What the server needs

Measured on the deployed configuration, with all 26 classifiers available:

| | |
|---|---|
| RAM at rest | 493 MB |
| RAM after every model has been used | 1,683 MB |
| Disk | 12.9 GB |
| Start-up | ~22 s |
| Throughput, default classifier | ~21 predictions/second |

A 6 GB / 4 vCPU / 30 GB Ubuntu 24.04 box runs this with room to spare. More RAM
buys only that more transformers stay warm between requests; it does not raise
throughput, which is bound by the single worker rather than by memory.

Models load on demand rather than all at once. The four sklearn classifiers stay
resident — they are 53 MB and they serve the default prediction and the whole
link-analysis path — while transformers and BiLSTMs are loaded when first
selected and held two at a time. Loading all 26 eagerly costs 5.4 GB once each
has run an inference, which does not fit; on a larger machine, raise
`MAX_RESIDENT_DEEP_MODELS` in `.env`.

## Deploying

**1. On the server, once**

```bash
sudo bash deploy/setup.sh
```

Installs Python, MongoDB 8, Node, Nginx and a 4 GB swap file; clones the code;
builds the frontend; writes a fresh `SECRET_KEY`; installs the systemd unit and
the Nginx site. Safe to re-run.

The CPU-only PyTorch wheel is used deliberately: the default build pulls ~2.5 GB
of CUDA libraries that a VPS with no GPU cannot use.

**2. From the machine that trained the models**

```bash
bash deploy/sync-models.sh root@YOUR_SERVER_IP
```

Sends 71 files, 7.58 GB — the 26 published classifiers, both Keras tokenisers,
the held-out test splits and the comparison tables. It leaves 8.8 GB of
training-only artefacts behind: the fastText and word2vec embedding files (their
weights are already baked into the `.keras` graphs), the tokenised caches, the
optimizer checkpoints, and the `_pre_483` backups superseded by the
483-stopword retrain.

Transfer time depends on your upload speed: roughly 1.7 hours at 10 Mbps, 50
minutes at 20 Mbps. It happens once.

**3. Back on the server**

```bash
chown -R somali:somali /opt/somali-nlp
systemctl start somali-nlp
journalctl -u somali-nlp -f
```

The site answers on `http://YOUR_SERVER_IP`.

## Updating afterwards

```bash
cd /opt/somali-nlp && git pull && systemctl restart somali-nlp
```

Seconds. Models are only re-sent if they are retrained, and `rsync` then
transfers just the files that changed.

## A domain and HTTPS

With a domain pointed at the server:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

Certbot edits the Nginx site in place and renews automatically. Worth doing
before a live demonstration — browsers mark plain `http://` as "Not secure",
which is a distraction in front of an audience.

## Checking it works

```bash
curl -s localhost:8000/api/models | python3 -c 'import json,sys; print(len(json.load(sys.stdin)), "models")'
```

Should print `26 models`. If it prints fewer, the transfer is incomplete —
`sync-models.sh` is safe to run again and will send only what is missing.
