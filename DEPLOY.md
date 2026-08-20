# Deploying the platform

Everything here was measured on the running system, not estimated. The figures
under "What the server needs" come from the live deployment at
`ai-detector.madaldb.com`.

There are two paths. Take the second one if the machine is already running
something you care about.

| | |
|---|---|
| **A fresh VPS**, nothing else on it | `deploy/setup.sh` |
| **A server already running other applications** | `deploy/setup-shared.sh` |

## Why the models are not in git

The trained weights are 7.6 GB. GitHub's free Git LFS tier allows 1 GB, so the
push uploaded the pointer files and silently dropped the objects behind them: a
`git clone` produced 135-byte stubs where the models should be, and the platform
would not start. Weights are not source. Git carries the code that loads them
(25 MB, a few seconds to clone) and the weights travel separately.

## What the server needs

Measured with all 26 classifiers present:

| | |
|---|---|
| RAM, real (anonymous), after every model has been used | **1,334 MB** |
| RAM reported by `systemd` | 4,289 MB — mostly page cache of the weights, reclaimable |
| Disk | 12.9 GB installed, ~18 GB with the OS |
| Start-up | ~20 s |
| Default classifier (LinearSVC, 94.79%) | 39–100 ms |
| BiLSTM / MiniTransformer | 1.5–2.3 s |
| Fine-tuned transformer, 512 tokens | 3–9 s |

A 6 GB / 4 vCPU / 30 GB Ubuntu 24.04 box runs this comfortably. **4 GB is enough**
if MongoDB's cache is capped — see below. More RAM only keeps more transformers
warm between requests; it does not raise throughput, which is bound by the single
worker.

Read `systemd`'s memory figure carefully. It counts the page cache of the 7.5 GB
of weights the process has read, which the kernel reclaims on demand. The number
that matters is `RssAnon` in `/proc/<pid>/status`.

### Why memory is bounded regardless of traffic

Models load on demand. The four sklearn classifiers are pinned — 53 MB, and they
serve the default prediction and the whole link-analysis path — while
transformers and BiLSTMs load on first use and are held two at a time under an
LRU (`MAX_RESIDENT_DEEP_MODELS`). A third request evicts the least recently used.

With one uvicorn worker, that makes peak memory a property of the cache size, not
of how many people are using the site. Ten simultaneous users cost the same as
one; requests queue instead. Loading all 26 eagerly would cost 5.4 GB.

### MongoDB will take 2.5 GB if you let it

WiredTiger's default cache is `max(50% × (RAM − 1 GB), 256 MB)` — 2.5 GB on a
6 GB box, more than this platform's entire peak. The database holds users, a
prediction log and an activity log: a few MB. `setup-shared.sh` caps it at
256 MB. On a fresh box under `setup.sh`, do it by hand:

```bash
sed -i '/^storage:/a\  wiredTiger:\n    engineConfig:\n      cacheSizeGB: 0.25' /etc/mongod.conf
systemctl restart mongod
mongosh --quiet --eval 'print(db.serverStatus().wiredTiger.cache["maximum bytes configured"])'
```

That last line should print `268435456`. Grep for `cacheSizeGB`, not for
`wiredTiger` — Ubuntu ships a commented-out `#  wiredTiger:` stanza that a
careless guard will match.

---

## Path A — a fresh VPS

```bash
sudo bash deploy/setup.sh
```

Installs Python, MongoDB 8, Node, Nginx and a 4 GB swap file; clones the code;
builds the frontend; writes a fresh `SECRET_KEY`; installs the systemd unit and
the Nginx site; enables `ufw`. Safe to re-run.

The CPU-only PyTorch wheel is deliberate: the default build pulls ~2.5 GB of
CUDA libraries that a VPS with no GPU cannot use.

---

## Path B — a server already running other applications

`setup.sh` targets an empty machine and is destructive on a shared one. It
replaces the system Node with 20.x, enables `ufw` with only 22/80/443 open,
deletes the Nginx default site, and installs a `server_name _` catch-all that
takes every request whose Host header matches no other vhost. On a box hosting
live applications that is several outages, not a deployment.

```bash
sudo DOMAIN=ai-detector.example.com bash deploy/setup-shared.sh
```

The same platform, installed without touching any of it:

- **Node is never installed or upgraded.** The frontend is built on the
  workstation and sent as static files, which Nginx serves directly.
- **`ufw` is never enabled, disabled, or given a rule.**
- **The Nginx default site is left alone**, and the vhost added here answers only
  for the exact domain given — never `_`.
- **MongoDB's cache is capped before it first starts.**
- If the new vhost fails `nginx -t`, it is **removed rather than reloaded**, so a
  bad config cannot take the other applications down.

It refuses to start if the box differs from what it expects: too little disk or
RAM, port 8000 already in use, or port 80 held by something that is not Nginx.

Containerised hosts (OpenVZ, LXC, Virtuozzo) share the host kernel and refuse
`swapon`. That is reported and stepped over — swap is insurance here, not a
requirement, since the memory ceiling is bounded by the model cache.

---

## Sending the models

From the machine that trained them, in the repository root.

**With `rsync`** (Linux, macOS, WSL):

```bash
bash deploy/sync-models.sh root@YOUR_SERVER_IP
```

**Without `rsync`** (Git Bash on Windows does not ship it):

```bash
KEY=~/.ssh/your_key bash deploy/push-models.sh root@YOUR_SERVER_IP
```

`push-models.sh` moves the same files over `tar | ssh`, in two tiers, in an order
that makes the site useful early:

| Tier | Size | What it carries |
|---|---|---|
| 1 | 297 MB | The LinearSVC that scores 94.79% — the best model on the platform — every BiLSTM, both tokenisers, the test splits, the comparison tables |
| 2 | 7.5 GB | The ten fine-tuned transformers, best-first |

Tier 1 takes a few minutes and the site is fully usable when it lands. Tier 2
sends AfriBERTa (84.0%) and SomBERTa (83.1%) first, because they are both the
most accurate of the ten and the smallest — the first 911 MB buys the two a
demonstration actually wants. mBERT (65.9%) goes last.

Measured at ~19 Mbps, tier 2 took 48 minutes end to end. Re-running skips
anything already transferred, comparing `model.safetensors` byte for byte, so an
interrupted transfer resumes at the model it stopped on.

Pass `RESTART=1` to restart the service after each model, making each one live as
it lands.

> **The dropdown lists all 26 whether or not the weights are there.**
> `/api/models` is built from the comparison CSVs, not from what is on disk, and
> every entry is reported `status: "active"`. A transformer whose weights have not
> arrived is offered to the user and returns 404 when chosen. Finish tier 2 before
> anyone uses the site.

Then, on the server:

```bash
chown -R somali:somali /opt/somali-nlp
systemctl start somali-nlp
journalctl -u somali-nlp -f
```

## Creating the first administrator

Registration through the site always produces a `viewer` — `register_user()`
hard-codes the role — so a fresh deployment has an admin area nobody can open.

```bash
sudo bash deploy/make-admin.sh you@example.com                # promote or create, super_admin
sudo bash deploy/make-admin.sh you@example.com 'a-password'   # set the password too
sudo bash deploy/make-admin.sh you@example.com '' admin       # a plain admin
```

`super_admin` can change roles, delete users and export the submitted-article
corpus; `admin` gets the admin pages without those three. Passwords are hashed
with the application's own `hash_password()`, so an account made here logs in
exactly like one made through the site. With no password given for a new account,
one is generated and printed once.

**There is no shared demo account unless you ask for one.** The platform used to
seed `demo@somalinlp.io` as `super_admin` with a password written in this public
repository, recreated on every start-up. To offer a sign-in to a supervisor or an
examiner, opt in through `.env`:

```
DEMO_USER_PASSWORD=<something strong>
DEMO_USER_ROLE=viewer
```

`viewer` is enough to sign in and classify text, which is what a demonstration
needs.

## A domain and HTTPS

Point the domain at the server, then:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com --redirect
```

Certbot edits the Nginx site in place and renews on a timer. Worth doing before a
live demonstration — browsers mark plain `http://` as "Not secure".

Behind Cloudflare this works with the proxy left on; the ACME challenge passes
through. Two things to know:

- Cloudflare cuts a request off at **100 seconds**. `deploy/nginx.conf` allows
  300 s because a cold transformer load and a link analysis both take time. The
  slowest measured request was 9 s, so there is headroom, but it is a ceiling the
  origin does not have.
- Cloudflare resolves the name to different anycast IPs for different clients,
  and some networks cannot reach some of those ranges — a symptom that looks like
  the site being down (`ERR_CONNECTION_RESET`) while it answers perfectly from
  elsewhere. Test with `--resolve` against each address before concluding the
  server is at fault:

  ```bash
  for ip in $(dig +short your-domain.com); do
    printf '%-16s ' "$ip"
    curl -s -o /dev/null -w '%{http_code}\n' https://your-domain.com/ --resolve your-domain.com:443:$ip --max-time 15
  done
  ```

  Turning the proxy off (grey cloud) removes Cloudflare from the path entirely.
  The origin holds its own Let's Encrypt certificate and serves the site directly.

## Checking it works

```bash
curl -s localhost:8000/api/models | python3 -c 'import json,sys; print(len(json.load(sys.stdin)), "models")'
```

Should print `26 models`. That counts the catalogue, not the weights on disk — to
check the weights really arrived, classify with each one. `RssAnon` after a full
sweep of all 26 should be near 1,334 MB:

```bash
awk '/^RssAnon/{printf "%.0f MB\n", $2/1024}' /proc/$(systemctl show somali-nlp -p MainPID --value)/status
```

## Updating afterwards

```bash
cd /opt/somali-nlp && git pull && systemctl restart somali-nlp
```

Seconds. Models are only re-sent if they are retrained, and both transfer scripts
then send just what changed.

## Removing it from a shared server

```bash
sudo bash deploy/teardown-shared.sh
```

Removes the service, its vhost, the database, the application user and
`/opt/somali-nlp`, after asking for the hostname as confirmation. It does not
touch Node, `ufw`, any other vhost, or MongoDB itself — that may have predated the
platform, and it will not guess.

`KEEP_MODELS=1` leaves the 7.5 GB of weights behind, so bringing the platform back
does not mean another 48-minute upload.
