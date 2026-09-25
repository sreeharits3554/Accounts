# Self-Hosting ERPNext for Mechotronix — Complete Setup Guide (erp.mechotronix.in)

This is a start-to-finish walkthrough: buying a server, pointing your domain
at it, installing the stack, creating your company, and going live. Follow
it top to bottom in order — each step assumes the one before it worked.

**Time needed:** roughly 2–3 hours for the technical setup (steps 1–8),
spread over a day or two once you count DNS propagation waiting time.

---

## Part 0 — What you're building

| Component | Technology | Why |
|---|---|---|
| Database | **MariaDB** | ERPNext's default and only well-supported DB |
| Cache / job queue / live updates | **Redis** | Required by Frappe framework |
| App server | **Frappe** (Python) + **ERPNext** app | The accounting/stock/HR system itself |
| Compliance | **India Compliance** app | GST, e-invoice, e-way bill, TDS, PF/ESI |
| Web server | **Nginx** | Serves the site, handles HTTPS |
| SSL | **Let's Encrypt** (via Certbot) | Free auto-renewing HTTPS certificate |
| Everything runs in | **Docker containers** | Isolated, reproducible, easy to update |

You do not install MariaDB/Redis/Nginx yourself — Docker Compose starts all
of them as containers that talk to each other. Your job is to configure and
run a handful of commands.

---

## Part 1 — Buy and set up the server

### 1.1 Choose a provider and plan
Any of these work well (pick one — no need to compare deeply):
- **Hetzner Cloud** — cheapest, EU-based, good performance (CX22: 2 vCPU/4GB ≈ €4/mo)
- **DigitalOcean** — easy UI, good docs (Basic Droplet: 2 vCPU/4GB ≈ $18/mo)
- **AWS Lightsail** — if you already use AWS (2 vCPU/4GB plan)

**Spec to choose:** Ubuntu 22.04 LTS, **2 vCPU / 4 GB RAM / 40+ GB SSD** minimum
for 8 users. Pick a data center region close to India (Singapore/Mumbai if
offered) for lower latency.

### 1.2 Create the server
On your provider's dashboard:
1. Create a new server/droplet/instance
2. Image: **Ubuntu 22.04 LTS**
3. Add your **SSH public key** (if you don't have one, generate on your laptop:
   `ssh-keygen -t ed25519 -C "you@mechotronix.in"`, then paste
   `~/.ssh/id_ed25519.pub` into the provider's "SSH Keys" field)
4. Launch it. Note down the **public IP address** it gives you, e.g. `142.93.x.x`

### 1.3 Point your domain at the server (DNS)
Log in wherever `mechotronix.in` is registered/managed (GoDaddy, BigRock,
Cloudflare, whoever you bought/manage the domain through) and open **DNS
Management / DNS Records**.

Add:
| Type | Host/Name | Value | TTL |
|---|---|---|---|
| A | `erp` | `<your server's public IP>` | Auto / 3600 |

This makes `erp.mechotronix.in` resolve to your server. Save it.

**Wait and verify** (can take a few minutes to a few hours):
```bash
# run this from your own laptop
nslookup erp.mechotronix.in
# or
dig erp.mechotronix.in +short
```
It should print your server's IP. Don't move to Part 2 until this works —
Let's Encrypt (step 5) will fail otherwise.

---

## Part 2 — Prepare the server

SSH in (replace with your IP or, once DNS resolves, the hostname):
```bash
ssh root@<server-ip>
```

### 2.1 Update the system and create a non-root user
```bash
apt update && apt upgrade -y

adduser deploy          # set a strong password when prompted
usermod -aG sudo deploy

# switch to it
su - deploy
```
From here on, run commands as `deploy`, not `root`.

### 2.2 Firewall
```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp     # HTTP (needed for Let's Encrypt validation)
sudo ufw allow 443/tcp    # HTTPS
sudo ufw enable           # type 'y' to confirm
sudo ufw status
```

### 2.3 Install Docker
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```
**Log out and log back in** (`exit`, then `ssh deploy@<server-ip>` again) so
the docker group membership takes effect. Then verify:
```bash
docker --version
docker compose version
```
Both should print version numbers with no errors.

---

## Part 3 — Get the deployment files

```bash
git clone https://github.com/frappe/frappe_docker
cd frappe_docker
```

### 3.1 Create your environment file
```bash
cp example.env .env
nano .env
```
Edit/confirm these values (delete or comment out anything conflicting):
```
ERPNEXT_VERSION=version-15
FRAPPE_VERSION=version-15
DB_PASSWORD=<generate a long random password>
LETSENCRYPT_EMAIL=you@mechotronix.in
SITES=`erp.mechotronix.in`
```
**Generate a strong DB password** with:
```bash
openssl rand -base64 24
```
Copy that into `DB_PASSWORD=`. **Save this password somewhere safe** (password
manager) — you'll need it again in Part 4.

Save and exit nano: `Ctrl+O`, `Enter`, `Ctrl+X`.

---

## Part 4 — Bring up the stack

```bash
docker compose -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.https.yaml \
  --env-file .env \
  up -d
```

This pulls the images (MariaDB, Redis, Frappe backend, worker, scheduler,
Nginx frontend, Certbot) and starts them in the background. **First run
takes 5–10 minutes** depending on your connection.

### 4.1 Verify everything is running
```bash
docker compose ps
```
You should see containers like `frappe_docker-backend-1`,
`frappe_docker-db-1`, `frappe_docker-redis-cache-1`,
`frappe_docker-redis-queue-1`, `frappe_docker-frontend-1`,
`frappe_docker-scheduler-1`, `frappe_docker-websocket-1`, `frappe_docker-queue-long-1`,
`frappe_docker-queue-short-1` — all with status `Up` or `running`.

If something shows `Exited` or `Restarting`, check its logs:
```bash
docker compose logs <container-name> --tail=100
```

### 4.2 Watch it come fully up
```bash
docker compose logs -f
```
Press `Ctrl+C` once you see the backend and Nginx settle (stop restarting).

---

## Part 5 — Create your site

Still inside `frappe_docker/`:
```bash
docker compose exec backend bench new-site erp.mechotronix.in \
  --mariadb-root-password <the DB_PASSWORD from your .env> \
  --admin-password <choose a strong admin password, save it> \
  --install-app erpnext \
  --set-default
```
This:
- Creates a MariaDB database for `erp.mechotronix.in`
- Installs the ERPNext app (accounting, stock, sales, purchase, HR/payroll, CRM)
- Sets it as the default site for this container

Takes a couple of minutes. On success it prints `*** Scheduler is disabled ***`
or similar — that's expected at this stage (fixed by the running scheduler
container).

### 5.1 Install the India Compliance app (GST/TDS/PF/ESI for India)
```bash
docker compose exec backend bench get-app india_compliance \
  https://github.com/resilient-tech/india-compliance

docker compose exec backend bench --site erp.mechotronix.in install-app india_compliance
```

---

## Part 6 — Verify HTTPS is working

Because you configured `compose.https.yaml` with `LETSENCRYPT_EMAIL`, Certbot
should have already obtained a free SSL certificate for `erp.mechotronix.in`
(this only works if DNS from step 1.3 was already resolving *before* you ran
`up -d` in Part 4 — if it wasn't, see Troubleshooting below).

Open a browser and visit:
```
https://erp.mechotronix.in
```
You should see the ERPNext login page with a valid padlock/HTTPS. Log in:
- **Username:** `Administrator`
- **Password:** the `--admin-password` you set in Part 5

---

## Part 7 — Run the Setup Wizard

On first login, ERPNext walks you through setup:
1. **Region:** India, **Currency:** INR
2. **Company name:** Mechotronix
3. **Company abbreviation:** e.g. `MX`
4. **Chart of accounts:** choose the standard **India** template — it maps to
   the structure already documented in `DESIGN.md`
5. Fill company address (Karnataka), and later add:
   - **GSTIN:** `29APHPS6234A1ZV`
   - PAN, and once entered, TAN (for TDS) under Company settings
6. **Fiscal year:** April to March
7. Skip or fill sample-data prompts as you prefer (recommend skipping demo data)

---

## Part 8 — Post-setup configuration (compliance & structure)

Do these next, using `DESIGN.md` as the reference for what each should contain:

1. **Settings → Company → GST Settings**
   - Confirm GSTIN, set e-invoicing/e-way bill toggles if your turnover requires them
   - Set HSN code digit requirement
2. **Accounts → Tax Withholding Category**
   - Set up TDS sections you actually use (contractor payments, professional
     fees, rent, etc.) — India Compliance ships most standard ones; confirm
     current rates with your CA (rates/sections change under the new
     Income-tax Act effective April 2026)
3. **HR → Employee**
   - Add your 8 employees: PAN, Aadhaar, UAN, ESI number, date of joining
4. **HR → Payroll**
   - Set up Salary Structures; enable PF/ESI/Professional Tax computation
     (India Compliance / HR module handles the statutory math)
5. **Stock → Warehouse**
   - Create your godowns/locations (e.g. Main Store, Workshop)
6. **Users → New User** (one per employee, not everyone as Administrator)
   - Assign roles: Accounts Manager, Accounts User, Stock User, HR Manager,
     Sales User, etc. — least privilege per person
7. **System Settings → Backup**
   - Configure automatic cloud backup destination (S3/Dropbox/Google Drive) — see Part 9

---

## Part 9 — Backups (do this before entering real data)

### Manual backup, to confirm it works
```bash
cd ~/frappe_docker
docker compose exec backend bench --site erp.mechotronix.in backup --with-files
```
This writes a DB dump + a files archive inside the container's site folder.

### Automate nightly backups + off-site copy
1. In ERPNext: **Settings → System Settings → Backup** — set backup frequency
   and connect an S3/Dropbox/Google Drive destination for automatic **off-site**
   backups. Do this now, don't postpone it.
2. Additionally, add a host-level cron job as a second safety net:
   ```bash
   crontab -e
   ```
   Add:
   ```
   0 2 * * * cd /home/deploy/frappe_docker && docker compose exec -T backend bench --site erp.mechotronix.in backup --with-files
   ```
   (runs nightly at 2 AM)

**Test a restore once**, on a throwaway site, so you know the process works
before you actually need it.

---

## Part 10 — Updates

Before any update:
```bash
docker compose exec backend bench --site erp.mechotronix.in backup --with-files
```
Then:
```bash
cd ~/frappe_docker
git pull
docker compose exec backend bench --site erp.mechotronix.in migrate
```
For a major version bump (e.g. version-15 → version-16), check
`frappe_docker`'s release notes first — sometimes the `.env` image tags need
updating and containers need recreating (`docker compose up -d` again after
changing `.env`).

---

## Part 11 — Ongoing maintenance checklist

- [ ] Let's Encrypt renews automatically via the Certbot container — spot-check every few months that HTTPS is still valid
- [ ] `docker system df` monthly; `docker image prune` to reclaim space from old images
- [ ] Review **Settings → Audit Trail / User List** periodically
- [ ] Keep `india_compliance` app updated (`bench update` picks it up) — GST/TDS rules change yearly
- [ ] Confirm off-site backups are actually landing in S3/Drive, not just running locally
- [ ] Rotate the `Administrator` password and don't use that account day-to-day

---

## Troubleshooting

**HTTPS/Certbot failed to issue a certificate**
Almost always because DNS wasn't pointing at the server yet when the stack
started. Fix DNS (Part 1.3), confirm with `dig erp.mechotronix.in +short`,
then restart just the proxy/certbot piece:
```bash
docker compose -f compose.yaml -f overrides/compose.https.yaml --env-file .env up -d --force-recreate
```

**A container keeps restarting**
```bash
docker compose logs <container-name> --tail=200
```
Most common causes: wrong `DB_PASSWORD` in `.env` not matching what MariaDB
was initialized with (if you changed it after first boot, you'll need to
reset the DB volume or use the original password), or insufficient RAM (swap
helps on a 4 GB box — see below).

**Site paginates slowly / server feels underpowered**
Add swap so background jobs don't OOM-kill:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

**Forgot the Administrator password**
```bash
docker compose exec backend bench --site erp.mechotronix.in set-admin-password <new-password>
```

---

## Alternative: skip server management entirely
If steps above feel like more ops work than you want to own, **Frappe
Cloud** (the framework's official managed hosting) runs the identical
ERPNext + India Compliance stack for you — updates, backups, scaling
included. You'd just create a site there and point `erp.mechotronix.in` at
it with a CNAME instead of an A record. Say the word and I'll write that
path out in the same level of detail.
