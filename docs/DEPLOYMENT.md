# Deploying aceData to production

A safe, repeatable path to take the ACE site live. Work top to bottom — the
**Pre-deploy checklist** must be fully green before the **Deployment steps**.

> **Golden rule:** never deploy straight to production from your laptop. Stand
> up a **staging** environment first (same steps, throwaway domain, Stripe
> *test* keys), confirm everything works there, then repeat against production.

---

## 0. Where things stand (from the handoff)

| Item | Status |
| --- | --- |
| Code-level production hardening (debug toolbar gated, WhiteNoise, security headers) | ✅ Done in code |
| Backend audit (auth, password change, logout, webhook) | ✅ Audited + fixed |
| Git / version control | ⛔ git not installed; nothing committed yet — **do first** |
| Secret rotation (Stripe, Gmail, `SECRET_KEY`) | ⛔ Outstanding |
| Real SMTP email | ⛔ Console backend still default |
| Live Stripe keys + public webhook | ⛔ Test mode |
| Hosting + PostgreSQL | ⛔ Not provisioned |

---

## 1. Pre-deploy checklist

Tick every box. Anything unchecked is a go-live blocker.

### Source control
- [ ] **Install git** and initialize the repo (work is currently local-only and at risk).
- [ ] Confirm `.env`, `db.sqlite3`, `*.log`, and `staticfiles/` are git-ignored (they are in `.gitignore` — verify nothing sensitive is already staged).
- [ ] Commit and push to the remote. Verify the pushed tree contains **no** `.env` and **no** secrets.

### Secrets (rotate everything that was ever public)
- [ ] Generate a fresh `DJANGO_SECRET_KEY`:
      `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- [ ] **Rotate the Stripe keys** in the Stripe dashboard (the old test keys were public). Get new **live** keys.
- [ ] **Rotate the Gmail App Password** (or move to a transactional email provider — see §4).
- [ ] Store all secrets in the **host's secret manager / env-var settings**, never in a committed file. Do not paste secrets into chat, tickets, or logs.

### App configuration (production `.env` / host env vars)
- [ ] `DJANGO_DEBUG=False`
- [ ] `DJANGO_SECRET_KEY=<new strong key>`
- [ ] `DJANGO_ALLOWED_HOSTS=acedata.example.com` (your real domain(s), comma-separated)
- [ ] `BASE_URL=acedata.example.com`
- [ ] Database env vars set (see §3) — pointing at PostgreSQL, not SQLite.
- [ ] Email env vars set with a real SMTP backend (see §4).
- [ ] Stripe **live** env vars set: `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (see §5).
- [ ] `STRIPE_CURRENCY` and tier amounts confirmed (`TIER_2_AMOUNT_CENTS`, `TIER_3_AMOUNT_CENTS`).

### Dependencies
- [ ] Add a production WSGI server to `requirements.txt`: `gunicorn>=21.0` (Linux hosts; gunicorn does not run on Windows).
- [ ] `whitenoise>=6.0` is already in `requirements.txt`.
- [ ] Add the Postgres driver: `psycopg[binary]>=3.1` (or `psycopg2-binary` if you prefer v2).

### Verification (run locally first, with prod-like env)
- [ ] `python manage.py check --deploy` returns no warnings (given a strong `SECRET_KEY` and `DEBUG=False`).
- [ ] `python manage.py test playground` — all tests pass.
- [ ] `python manage.py collectstatic --noinput` succeeds and produces a WhiteNoise manifest.

---

## 2. Production settings recap (already in code)

These are wired up in [`project/settings.py`](../project/settings.py) and activate
automatically when `DEBUG=False`:

- `debug_toolbar` is **not** loaded (apps, middleware, and `/_debug_/` URL all gated on `DEBUG`).
- WhiteNoise serves compressed, hashed static files via `CompressedManifestStaticFilesStorage`.
- Security headers: `SECURE_SSL_REDIRECT`, secure session/CSRF cookies, HSTS (1 year, preload, subdomains), `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=DENY`.
- `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` — assumes the site runs **behind a proxy/load balancer that terminates TLS** and sets `X-Forwarded-Proto`. This is true for virtually all managed hosts. If yours does **not**, remove this line (otherwise Django may misjudge whether a request is secure).

Optional overrides: `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`.

---

## 3. Database: SQLite → PostgreSQL

SQLite is fine for dev but not for production (concurrency, durability, most PaaS
filesystems are ephemeral). Switch to managed PostgreSQL.

1. Provision a managed Postgres instance (your host's add-on, or a service like
   Neon/Supabase/RDS). Capture its connection details as env vars.
2. Update `DATABASES` in `settings.py` to read from the environment. A common,
   12‑factor-friendly approach is `dj-database-url`:
   - Add `dj-database-url>=2.1` to `requirements.txt`.
   - In `settings.py`:
     ```python
     import dj_database_url
     DATABASES = {
         'default': dj_database_url.config(
             default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",  # dev fallback
             conn_max_age=600,
             ssl_require=not DEBUG,
         )
     }
     ```
   - Set `DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME` in prod env.
3. There is **no data to migrate** (dev SQLite holds only test data). On the new
   DB, just run migrations fresh (§6).
   *(If you ever do need to move real data: `dumpdata` → switch DB → `loaddata`,
   or use `pg_dump`/`pg_restore` for Postgres-to-Postgres.)*

---

## 4. Email: console → real SMTP

Currently `EMAIL_BACKEND` defaults to the console backend, so contact-form
messages and purchase receipts only print to the server log — nobody receives
them. For production, set real SMTP creds via env:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.yourprovider.com
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp username>
EMAIL_HOST_PASSWORD=<smtp password / app password>   # store in secret manager
DEFAULT_FROM_EMAIL=hello@acedata.example.com
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
```

Recommendations:
- Prefer a **transactional email provider** (SendGrid, Postmark, Amazon SES,
  Mailgun) over a personal Gmail account — better deliverability, no app-password
  fragility, proper SPF/DKIM/DMARC.
- Set SPF/DKIM/DMARC DNS records for your sending domain.
- Note: the contact form sends with `fail_silently=True`, so a misconfigured SMTP
  **silently drops leads**. Send yourself a test message after deploy (§7) and
  consider wiring up email-delivery monitoring.

---

## 5. Stripe: test → live + webhook

1. Switch to **live** API keys in the prod env (`STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`).
2. In the Stripe dashboard → Developers → Webhooks, add an endpoint pointing at
   `https://acedata.example.com/webhook/`, subscribed to `checkout.session.completed`.
3. Copy that endpoint's **signing secret** into `STRIPE_WEBHOOK_SECRET`.
   - The webhook now **requires** this secret: with it unset, the endpoint
     returns HTTP 400 and records nothing (it refuses to trust unsigned events).
4. Do a real low-value test purchase end-to-end and confirm a `Purchase` row is
   created and the receipt email is sent.

> **Idempotency:** the webhook is idempotent — `Purchase.event_id` is unique and
> retried `checkout.session.completed` events are skipped, so Stripe's repeated
> deliveries can't create duplicate purchases.

---

## 6. Deployment steps

This is written for a managed PaaS (Render, Railway, Fly.io, Heroku-style) — the
simplest path for a solo brand. VPS notes follow.

1. **Push code** to the remote git repo the host builds from.
2. **Create the app/service** on the host and connect the repo + branch (`aceDataMain`).
3. **Add the managed PostgreSQL** add-on; note its `DATABASE_URL`.
4. **Set all environment variables** from the checklist (§1) in the host's
   config UI / secret store. Double-check `DEBUG=False` and `ALLOWED_HOSTS`.
5. **Build command:**
   ```
   pip install -r requirements.txt && python manage.py collectstatic --noinput
   ```
6. **Release/pre-start command** (runs once per deploy, after build):
   ```
   python manage.py migrate --noinput
   ```
7. **Start command:**
   ```
   gunicorn project.wsgi:application --bind 0.0.0.0:$PORT
   ```
   (WhiteNoise serves static files in-process, so no separate static server is
   required for a single-service deploy.)
8. **Domain + TLS:** point your domain at the host and enable managed HTTPS
   (Let's Encrypt). Confirm the host sets `X-Forwarded-Proto` (it should).
9. **Create an admin user** (one-off, via the host's shell):
   ```
   python manage.py createsuperuser
   ```

### VPS variant (Ubuntu + Nginx)
- Run gunicorn under **systemd** (auto-restart on crash/reboot), bound to a unix socket.
- Put **Nginx** in front as the TLS-terminating reverse proxy; it must set
  `proxy_set_header X-Forwarded-Proto $scheme;`.
- Use **certbot** for Let's Encrypt certificates with auto-renewal.
- Run `collectstatic` and `migrate` on each deploy (a small deploy script or
  CI step).

---

## 6a. Render walkthrough (chosen host — domain `acedataworks.com`)

A [`render.yaml`](../render.yaml) Blueprint is included; it defines the web
service + managed Postgres and wires the env vars. Secret values
(`STRIPE_*`, `EMAIL_HOST*`) are marked `sync: false`, so they are entered in the
Render dashboard and never committed.

**Prerequisites:** the cleanup branch is merged into `aceDataMain`, and you've
rotated the secrets (§1) so you're entering fresh values below.

1. **Create the Blueprint.** Render Dashboard → **New +** → **Blueprint** →
   connect the GitHub repo → it reads `render.yaml`. Review the web service and
   `acedata-db` it proposes. (Confirm the `plan` names are current; adjust if Render
   has renamed them.)
2. **Fill the `sync: false` secrets** when prompted (or under the service →
   **Environment** afterwards):
   - `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY` — your **live** keys.
   - `STRIPE_WEBHOOK_SECRET` — added in step 6.
   - `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` — see step 5.
3. **First deploy.** Render runs the build (`pip install` + `collectstatic`),
   then `preDeployCommand` (`migrate`), then starts gunicorn. Watch the logs
   until it's live on the temporary `…onrender.com` URL (auto-allowed via
   `RENDER_EXTERNAL_HOSTNAME`). Visit it to confirm the site renders.
4. **Create the admin user.** Service → **Shell**:
   ```
   python manage.py createsuperuser
   ```
5. **Email (`contact@acedataworks.com`, hosted at Hostinger).** The blueprint
   already sets `EMAIL_HOST=smtp.hostinger.com`, `EMAIL_PORT=587`,
   `EMAIL_USE_TLS=True`, and `EMAIL_HOST_USER=contact@acedataworks.com`. The only
   secret to enter in the dashboard is `EMAIL_HOST_PASSWORD` = the mailbox password.
   - If your Hostinger plan uses **Titan** email instead, change `EMAIL_HOST` to
     `smtp.titan.email` (same port/TLS). Confirm in hPanel → Emails → the mailbox →
     connection settings.
   - Make sure Hostinger's **SPF/DKIM/DMARC** records exist for the domain (hPanel
     shows them) so mail isn't spam-filtered.
6. **Stripe live webhook.** In Stripe → Developers → Webhooks, add
   `https://acedataworks.com/webhook/` subscribed to `checkout.session.completed`,
   copy its signing secret into `STRIPE_WEBHOOK_SECRET`, and redeploy.
7. **Custom domain + TLS.** Service → **Settings → Custom Domains** → add
   `acedataworks.com` and `www.acedataworks.com`. Render shows the exact DNS
   records to create at your **registrar**:
   - apex `acedataworks.com` → the **A record** (or ALIAS/ANAME) Render provides,
   - `www` → a **CNAME** to your `…onrender.com` host.
   Once DNS propagates, Render issues Let's Encrypt TLS automatically. The app's
   `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` already include both names. Render sets
   `X-Forwarded-Proto`, which the app's `SECURE_PROXY_SSL_HEADER` relies on.

   > **Don't break email when repointing DNS.** `contact@acedataworks.com` is on
   > Hostinger, so the domain's **MX** records (and the email **SPF/DKIM/DMARC**
   > records) must stay pointed at Hostinger. You're only adding/updating the web
   > `A` (apex) and `www` `CNAME` records for Render — leave all mail-related
   > records untouched. Removing the MX records would stop email delivery.
8. **Backups:** enable automatic backups on the `acedata-db` instance.

Deploys are automatic on every push to `aceDataMain` (build → migrate → gunicorn).

---

## 7. Post-deploy verification (smoke test)

- [ ] Home page loads over **HTTPS**; `http://` redirects to `https://`.
- [ ] Static assets (logo, CSS, favicon) load — confirms WhiteNoise + collectstatic.
- [ ] Sign up → you're logged in → **Log out** works (it's a POST now).
- [ ] Log in with **both** username and email.
- [ ] Change password: weak password is rejected; a strong one works and you stay logged in.
- [ ] Contact form sends a real email to the owner inbox.
- [ ] Pricing → a paid tier → Stripe Checkout → completes → `Purchase` recorded → receipt email received.
- [ ] `https://.../admin/` loads and the superuser can log in.
- [ ] `https://.../_debug_/` returns **404** (debug toolbar must be off in prod).
- [ ] Hit `/webhook/` without a signature → **400** (refuses unsigned events).

---

## 8. Safety, rollback & ongoing

- **Backups:** enable automated daily backups on the managed Postgres; verify a restore once.
- **Rollback:** keep the previous release deployable. On a bad deploy, roll back
  to the prior git tag/release; migrations should be backward-compatible (avoid
  destructive migrations in the same release as code that still needs the old schema).
- **Monitoring:** turn on the host's logging/metrics; add error tracking (e.g.
  Sentry) so silent failures (email, webhook) surface.
- **Secret hygiene:** rotate keys on a schedule and immediately if exposure is
  suspected. Never commit secrets; keep them only in the host secret store.
- **Dependencies:** the repo pins `Django>=4.2,<5.0`. Before bumping to Django
  5.0, note that GET-based logout was removed — the UI already uses POST logout,
  so it's compatible, but re-run the full test suite on any major bump.
