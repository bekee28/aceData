# ACE site — session handoff

**Project:** `aceData` — a Django 4.2 site for "ACE," a solo data-consulting brand
(data warehouse architecture, data pipelines, automated dataflows, AI integration).

**Location:** `c:\ClaudeProjects\DjangoProject\aceData-aceDataMain` (Windows, PowerShell). Virtualenv at `.venv`.

**Origin:** github.com/bekee28/aceData, branch `aceDataMain` — fetched as a **zip** because **git is not installed** on this machine.

**Structure:** app = `playground`, config = `project`, "Space" Bootstrap 5 theme.

**Common commands:**
- Run tests: `.\.venv\Scripts\python.exe manage.py test playground`
- Run server: `.\.venv\Scripts\python.exe manage.py runserver`

---

## What the previous session accomplished

- Got the project running (fixed `bootstrap5` → `django_bootstrap5` in `INSTALLED_APPS`), moved all secrets to a git-ignored `.env`, added `requirements.txt` + a 9-test suite (all passing).
- Built the missing pages (`account`, `paymentpage`, `success`, `cancel`) and a **3-tier offering**:
  - **Discovery** (free → routes to the contact page)
  - **Build** ($149) and **Build Pro** ($349) via **Stripe inline `price_data`** (no dashboard products needed; amounts set in `TIER_2_AMOUNT_CENTS` / `TIER_3_AMOUNT_CENTS` env vars).
- Added `Purchase.user` FK (the webhook links purchases to accounts via `user_id` in Stripe metadata); made the contact form email the site owner.
- Rebranded every page to "ACE" with a professional "We" voice; removed Hire-Us & Help-Center (templates, views, URLs, links, tests); fixed all dead links; replaced stock people photos with the theme's abstract illustrations.
- Built a full logo system: a custom "A" whose crossbar is an **upward green trendline**, applied to `logo.svg`, `logo-white.svg`, `logo-icon.svg` (boxed app-icon used in header + footer), `favicon.svg`, and a multi-resolution `favicon.ico`. Added a sticky header, a slim single-row footer, and a LinkedIn link.
- Docs written: `README.md` and `docs/ARCHITECTURE.md`.

---

## Backend audit (done this session)

Auth/login/logout/security reviewed and hardened (tests now 9 → 14, all passing):
- Custom auth backend returns `None` instead of raising (Django contract) and handles email/username collisions.
- `change_password` now enforces the password validators, blocks empty/unchanged passwords, and keeps the session alive (`update_session_auth_hash`).
- Logout switched to POST forms (GET logout is removed in Django 5.0).
- Webhook now **requires** the signing secret and rejects unsigned events; purchase-recording no longer hidden behind the secret check; `print()` (which crashed on Windows cp1252) replaced with logging.
- Webhook is now **idempotent** — `Purchase.event_id` is unique, retried events are skipped (migration `0003`); duplicate `Purchase` rows can no longer be created.
- Contact form no longer uses `fail_silently` — a failed send now shows the user an error (with a fallback email) instead of a false "sent" message.
- Removed the unused `reset_token` field from `CustomUser`; collapsed the duplicate `/home` route (canonical home is now `/`; `/home/` 301-redirects to it).

**Deploy guide:** see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — full pre-deploy checklist + step-by-step.

---

## Outstanding work to go live (priority order)

1. **Version control** — git is now installed (portable **MinGit** at `%LOCALAPPDATA%\Programs\MinGit`, added to the user PATH). All work is **committed locally** on branch `cleanup/prep-for-launch` (remote `origin` = github.com/bekee28/aceData; `.env`/`db.sqlite3`/logs confirmed not tracked). **Still to do:** run the authenticated `git push -u origin cleanup/prep-for-launch` and open a PR into `aceDataMain` (the remote's existing history is unrelated to this ZIP-based copy).
2. **Rotate exposed secrets** — the Stripe test keys, the Gmail app password, and the Django `SECRET_KEY` were public in the repo history. Rotate them all and set the new values only via `.env`.
3. **Email** — currently uses the **console backend** (contact-form messages and purchase receipts only print to the server terminal; nobody receives them). Switch to a real SMTP backend and credentials.
4. **Stripe** — in **test mode**. Needs live keys + a publicly reachable `/webhook/` endpoint with its signing secret (`STRIPE_WEBHOOK_SECRET`).
5. **Production config + hosting** — *code-level hardening done (see below); the rest is operational.*
   - **Done in code:** `debug_toolbar` (app, middleware, `/_debug_/` URL) is now gated on `DEBUG`, so it never loads in production. WhiteNoise is wired in (middleware + `CompressedManifestStaticFilesStorage`, applied only when `DEBUG=False`); `whitenoise>=6.0` added to `requirements.txt`. A `if not DEBUG:` block enables `SECURE_SSL_REDIRECT` (overridable via `DJANGO_SECURE_SSL_REDIRECT`), secure session/CSRF cookies, HSTS, `SECURE_PROXY_SSL_HEADER`, nosniff, and `X_FRAME_OPTIONS='DENY'`. `manage.py check --deploy` is clean given a strong `SECRET_KEY`; `collectstatic` produces a WhiteNoise manifest.
   - **Still operational (needs you):** set `DEBUG=False`, a strong `SECRET_KEY`, real `ALLOWED_HOSTS`, and HTTPS in the prod `.env`; run `collectstatic` on deploy; migrate SQLite → PostgreSQL; deploy to a host + domain.
   - **Note:** the prod env must serve over HTTPS behind a proxy that sets `X-Forwarded-Proto` (assumed by `SECURE_PROXY_SSL_HEADER`); adjust if your host differs.

---

## Gotchas for the next instance

- `.env` currently has `DJANGO_DEBUG=TRUE`. Note: with `DEBUG=False`, Django **caches templates** in memory — template edits won't appear without a server restart.
- **Recurring issue:** a stray *system-Python* `runserver` (at `C:\Users\ealuo\AppData\Local\Programs\Python\Python312\python.exe`) keeps seizing port 8000 and serving stale/cached pages. If edits don't show up, run `Get-Process python | Stop-Process -Force`, then start a single server from `.venv`.
- `Pillow` was installed in the venv purely as a build-time tool to generate the favicon — it is **not** a runtime dependency and is intentionally absent from `requirements.txt`.
- Logo assets live in `playground/static/playground/assets/` (`svg/logos/*.svg`, `favicon.svg`, `favicon.ico`). The header and footer both use `logo-icon.svg` (black tile, white A, green trendline).
