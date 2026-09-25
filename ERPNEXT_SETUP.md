# Self-Hosting ERPNext for Mechotronix (erp.mechotronix.in)

## Database question first
ERPNext (built on the **Frappe framework**) uses **MariaDB** as its database by
default — this is what almost everyone runs in production, and what the official
Docker images ship with. Frappe also has experimental **PostgreSQL** support, but
it is not the well-trodden path (fewer apps test against it, some features assume
MariaDB). **Use MariaDB.**

Alongside MariaDB, the stack also needs:
- **Redis** — caching, background job queue, and real-time updates (Socket.IO)
- **Node.js** — only needed at build/setup time, for compiling frontend assets

You don't manage any of this by hand — the Docker setup below runs MariaDB, Redis,
the app server, a background worker, and an Nginx frontend as separate containers.

---

## Recommended deployment method: Docker (frappe_docker)

Frappe's own team maintains `frappe_docker`, which is the standard way to
self-host in production today (the older manual `bench` install on bare Ubuntu
still works but is more fragile to maintain). We'll use Docker Compose.

### 0. What you need before starting
- A Linux server (Ubuntu 22.04 LTS recommended) — a VPS from any Indian/global
  provider (DigitalOcean, Hetzner, AWS Lightsail, etc.)
  - **Minimum:** 2 vCPU, 4 GB RAM, 40 GB SSD — fine for 8 users
  - **Comfortable:** 4 vCPU, 8 GB RAM — headroom for payroll runs, reports, backups
- Root/sudo SSH access to that server
- A subdomain pointed at the server: e.g. **erp.mechotronix.in**
  - In your domain DNS (wherever mechotronix.in is managed), add an
    **A record**: `erp` → `<your server's public IP>`
  - Wait for DNS to propagate (`nslookup erp.mechotronix.in` should return your IP)

---

### 1. Prepare the server
```bash
ssh root@<server-ip>

# Basic hardening
apt update && apt upgrade -y
adduser deploy && usermod -aG sudo deploy
# (log back in as `deploy` from here on)

# Firewall: allow SSH, HTTP, HTTPS only
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### 2. Install Docker
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# log out and back in so the group applies
docker --version
docker compose version
```

### 3. Get frappe_docker
```bash
git clone https://github.com/frappe/frappe_docker
cd frappe_docker
```

### 4. Configure environment
```bash
cp example.env .env
nano .env
```
Set at minimum:
```
ERPNEXT_VERSION=version-15          # current stable ERPNext branch
DB_PASSWORD=<generate a strong password — save it in a password manager>
LETSENCRYPT_EMAIL=you@mechotronix.in
SITES=`erp.mechotronix.in`
```

### 5. Bring up the stack with SSL (Let's Encrypt), using the official compose overlay
```bash
docker compose -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.https.yaml \
  --env-file .env \
  up -d
```
This starts: MariaDB, Redis (cache + queue), the backend app server, a
background worker, a scheduler, Nginx, and Certbot for automatic HTTPS on
`erp.mechotronix.in`. First boot takes a few minutes while images download.

Check everything is healthy:
```bash
docker compose ps
docker compose logs -f
```

### 6. Create your site and install ERPNext
```bash
docker compose exec backend bench new-site erp.mechotronix.in \
  --mariadb-root-password <the DB_PASSWORD you set> \
  --admin-password <choose a strong admin password> \
  --install-app erpnext
```
This creates the MariaDB database for the site and installs the ERPNext app
(accounting, inventory, sales, purchase, HR/payroll modules) into it.

### 7. Install the India Compliance app (GST, e-invoice, e-way bill, TDS)
```bash
docker compose exec backend bench get-app india_compliance \
  https://github.com/resilient-tech/india-compliance
docker compose exec backend bench --site erp.mechotronix.in install-app india_compliance
```

### 8. Log in
Browse to `https://erp.mechotronix.in`, log in as `Administrator` with the
admin password you set in step 6.

Then run the **Setup Wizard**:
- Company name: Mechotronix, country: India, currency: INR
- Enter GSTIN `29APHPS6234A1ZV`, PAN, address (Karnataka)
- Chart of accounts: choose the standard Indian CoA template (it mirrors what
  was proposed in `DESIGN.md`) — you can rename/add heads afterward
- Fiscal year: April–March

---

## 9. Configure for your compliance needs
Do these inside ERPNext after setup, referencing `DESIGN.md`:
1. **Company → GST Settings**: enable e-invoicing/e-way bill if turnover crosses
   the threshold; set HSN digit requirement.
2. **Accounts → Tax Withholding Category**: set up your TDS sections and rates
   (India Compliance ships most standard ones; verify current rates with your CA).
3. **HR → HR Settings / Payroll**: add your 8 employees, salary structures, PF/ESI
   settings (India Compliance adds PF/ESI/PT computation for Indian payroll).
4. **Stock → Warehouse**: create your godowns/locations.
5. **Users**: create one login per employee, assign roles (Accounts Manager,
   Stock User, HR Manager, etc.) instead of everyone using Administrator.

---

## 10. Backups (critical — do this before going live)
```bash
# Manual backup (creates a DB dump + files archive)
docker compose exec backend bench --site erp.mechotronix.in backup --with-files
```
Automate it:
- Add a cron job on the host to run the above nightly and `rsync`/upload the
  backup folder to off-server storage (S3, Backblaze, Google Drive, etc.)
- ERPNext also has a built-in **Dropbox/S3/Google Drive backup** setting
  under System Settings → so it can push encrypted backups automatically —
  configure that as your primary off-site backup.

## 11. Updates
```bash
cd frappe_docker
docker compose exec backend bench --site erp.mechotronix.in migrate
# or pull new images for a version bump, following frappe_docker's release notes
```
Always take a backup (step 10) before updating.

## 12. Ongoing maintenance checklist
- Renew is automatic (Certbot container renews Let's Encrypt certs).
- Monitor disk space — `docker system df` and prune old images periodically.
- Review the audit log and user list periodically (ERPNext has this built in).
- Keep `india_compliance` app updated — GST/TDS rule changes ship as updates.

---

## If you'd rather not manage a server yourself
Frappe offers **Frappe Cloud** (official managed hosting) — same ERPNext/India
Compliance stack, but they run the servers, backups, and updates; you just
point `erp.mechotronix.in` at them via CNAME. Worth considering if you don't
have in-house server admin time. Let me know if you want that path compared
in detail instead.

---

## Summary: database & stack
| Component | Technology |
|---|---|
| Database | **MariaDB** (default & recommended) |
| Cache / queue / real-time | Redis |
| App framework | Frappe (Python) |
| Frontend build | Node.js (build-time only) |
| Web server | Nginx (in the Docker setup) |
| SSL | Let's Encrypt via Certbot |
| Deployment | Docker Compose (`frappe_docker`) |
