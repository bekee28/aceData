# Architecture

This document explains how aceData is put together and how a request flows
through it.

## Apps

There is one Django project (`project/`) and one application (`playground/`).
The project is intentionally small; `playground` holds all the site logic.

## Data model (`playground/models.py`)

### `CustomUser`
Extends Django's `AbstractUser` and is wired in via `AUTH_USER_MODEL =
'playground.CustomUser'`. Adds:
- `reset_token` — a UUID used for password-reset purposes.

It is registered with a customized `UserAdmin` (`admin.py`).

### `Purchase`
A record of a completed Stripe checkout:
- `user` — FK to `CustomUser` (`SET_NULL`, nullable), set by the webhook from
  the `user_id` carried in Stripe metadata. Query a user's purchases via
  `request.user.purchases`.
- `user_name` — denormalized username label, kept as a fallback for legacy/guest rows.
- `item_name` — `Build` / `Build Pro`.
- `amount_paid` — decimal amount.
- `date_of_purchase`, `time_of_purchase` — derived from the Stripe event timestamp.

Purchases are created **only** by the webhook handler, never by the checkout
views directly — this guarantees a record exists only after Stripe confirms
payment.

## Authentication

- **Registration** — `RegisterForm` (`forms.py`) extends `UserCreationForm`,
  requires email, and enforces unique username/email.
- **Login** — `CustomAuthenticationBackend` (`custom_auth_backend.py`) lets a
  user log in with **either** their username or their email in the username
  field. It is the only backend in `AUTHENTICATION_BACKENDS`.
- **Password reset** — uses Django's built-in class-based views
  (`PasswordResetConfirmView`, `PasswordResetCompleteView`) plus a themed
  `ResetPasswordView`, with custom templates.

## Pages & routing (`playground/urls.py`)

All public marketing pages are simple `render()` views. `account` and
`checkoutT2` are `@login_required`. `webhook` is `@csrf_exempt` (Stripe posts
to it server-to-server).

## Tiers & payment flow

Three tiers, defined once and surfaced on both `/pricing` (marketing) and
`/paymentpage` (checkout):

- **Discovery** — free. Its CTA links to `/contacts` (no Stripe involved).
- **Build** ($149) and **Build Pro** ($349) — paid, login-required, Stripe Checkout.

```
/pricing ──► /paymentpage ──► POST /checkout/build  or  /checkout/build-pro
                                      │   (login required)
                                      ▼
                  stripe.checkout.Session.create(price_data=...)
                                      │  (redirect, 303)
                                      ▼
                            Stripe-hosted Checkout
                              │              │
                     success_url        cancel_url
                              ▼              ▼
                         /success        /cancel

   Stripe ── webhook (checkout.session.completed) ──► /webhook/
                                      │
                                      ▼
        verify signature → record Purchase (linked to user) → email receipt
```

Key points:
- Prices live in **code/config** via Stripe `price_data` (see `TIER_2_AMOUNT` /
  `TIER_3_AMOUNT` in settings), so changing a price is an env-var edit — no
  Stripe dashboard Product setup.
- Paid tiers require login; the buyer's `user_id` and username ride along in
  Stripe metadata so the webhook can link the resulting `Purchase` to the account.
- `success_url` / `cancel_url` are built with `request.build_absolute_uri(...)`
  so they work in any environment (no hard-coded `localhost`).
- The webhook verifies the Stripe signature against `STRIPE_WEBHOOK_SECRET`
  before trusting the payload, then normalizes the event object so the same
  code handles both signed (`StripeObject`) and unsigned (`dict`) shapes.

## Templates

The theme renders each page as a **full HTML document** (not via a single base
template with `{% extends %}`). Shared chrome is pulled in with includes:

- `header.html` — top navigation (different menu for authenticated users).
- `footer.html` — site footer.
- `secondary.html` — login/signup modals and the "go to top" widget.

When adding a page, copy the head/`{% include %}`/JS-init scaffold from an
existing page (e.g. `change-password.html`) to stay consistent.

## Configuration (`project/settings.py`)

Settings are environment-driven via `python-dotenv`. `.env` is loaded at the top
of `settings.py`; every secret and environment-specific value reads from
`os.environ` with a safe local-dev fallback. See the README for the variable
list.

## Ideas for further work

- **`update_session_auth_hash`** after a password change so the user isn't
  logged out (today the UI asks them to re-login).
- **Backfill the FK** on any legacy `Purchase` rows by matching `user_name` to
  a username (the account page already falls back to `user_name`, so this is
  cosmetic/cleanup).
- **Booking integration** for the free Discovery tier (e.g. Calendly) instead
  of the generic contact page, if you want scheduled calls.
- **Prune theme filler** on the pricing page below the tier cards (the feature
  comparison table / FAQ are inherited from the "Space" theme and still mention
  generic plan names).
- **Production hardening** — PostgreSQL, `collectstatic` + WhiteNoise/CDN,
  HTTPS-only cookies, error monitoring.
