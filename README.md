# aceData

A marketing + e-commerce site for **ACE**, a personal data-consulting brand.
Visitors browse the brand's services, sign up for an account, and purchase
consulting service tiers through **Stripe Checkout**. Built with **Django 4.2**
and the "Space" Bootstrap 5 theme.

---

## Features

- **Marketing pages** — home, about, services, hire-us, pricing, contacts,
  help-center, privacy, terms-of-use (fully themed).
- **Accounts & auth** — custom user model, sign-up, login by **username _or_
  email** (custom auth backend), change password, and the full Django
  password-reset flow (request → email → confirm → done).
- **Three service tiers** — **Discovery** (free 30-min consultation, routes to
  the contact page), **Build** ($149, consultation + 1 hr implementation), and
  **Build Pro** ($349, consultation + 3 hrs). Paid tiers use Stripe Checkout
  with **inline pricing** (`price_data`) — no pre-created Stripe Products
  needed; amounts are set via env vars.
- **Payments** — a `success`/`cancel` flow and a signed-webhook handler that
  records each purchase (linked to the buyer's account) and emails a receipt.
- **Account dashboard** — profile details and purchase history.
- **Admin** — manage users and purchases via Django admin.

---

## Tech stack

| Area        | Choice                                              |
|-------------|-----------------------------------------------------|
| Framework   | Django 4.2 (Python 3.11+)                            |
| UI          | Bootstrap 5 "Space" theme, `django-bootstrap5`, `crispy-bootstrap5` |
| Payments    | Stripe (`stripe` Python SDK, Checkout + webhooks)   |
| Database    | SQLite (dev default)                                |
| Config      | `python-dotenv` (`.env` file)                       |
| Dev tools   | `django-debug-toolbar`                              |

---

## Project layout

```
.
├── manage.py
├── requirements.txt / Pipfile      # dependencies
├── .env.example                    # template for local config (copy to .env)
├── project/                        # Django project config
│   ├── settings.py                 # env-driven settings
│   ├── urls.py
│   └── wsgi.py / asgi.py
└── playground/                     # the single application
    ├── models.py                   # CustomUser, Purchase
    ├── views.py                    # pages, auth, Stripe checkout + webhook
    ├── urls.py
    ├── forms.py                    # RegisterForm
    ├── custom_auth_backend.py      # login by username or email
    ├── admin.py
    ├── tests.py                    # smoke tests
    ├── templates/                  # active page templates
    └── static/playground/          # theme assets (css/js/img/vendor)
```

> `playground/test_temps/` holds the original unstyled prototype pages and is
> **not** used by the app. The production templates live in
> `playground/templates/`.

---

## Local setup

### 1. Create a virtual environment & install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment

```powershell
copy .env.example .env            # cp on macOS/Linux
```

Edit `.env` and fill in your values. Generate a fresh secret key with:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

See [Environment variables](#environment-variables) below for the full list.

### 3. Migrate and run

```powershell
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin
python manage.py runserver
```

Visit <http://127.0.0.1:8000/>.

---

## Environment variables

All configuration lives in `.env` (loaded automatically; never committed).

| Variable | Purpose | Default |
|----------|---------|---------|
| `DJANGO_SECRET_KEY` | Django secret key | insecure dev key |
| `DJANGO_DEBUG` | Debug mode | `True` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
| `BASE_URL` | Site base URL | `localhost:8000` |
| `STRIPE_PUBLIC_KEY` | Stripe publishable key | _empty_ |
| `STRIPE_SECRET_KEY` | Stripe secret key | _empty_ |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | _empty_ |
| `STRIPE_TIER_1_PRICE_ID` / `STRIPE_TIER_1_PRODUCT_ID` | Tier 1 IDs | repo defaults |
| `STRIPE_TIER_2_PRICE_ID` / `STRIPE_TIER_2_PRODUCT_ID` | Tier 2 IDs | repo defaults |
| `EMAIL_BACKEND` | Email backend | console (prints to stdout) |
| `DEFAULT_FROM_EMAIL` | From address for receipts | — |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | SMTP settings | Gmail TLS defaults |

---

## Testing payments locally

1. Use **Stripe test keys** in `.env`.
2. Install the [Stripe CLI](https://stripe.com/docs/stripe-cli) and forward
   webhooks to the local server:

   ```bash
   stripe listen --forward-to localhost:8000/webhook/
   ```

   Copy the `whsec_...` value it prints into `STRIPE_WEBHOOK_SECRET`.
3. Start checkout from `/pricing` or `/paymentpage`, and complete payment with
   Stripe's test card `4242 4242 4242 4242` (any future expiry / CVC).
4. On `checkout.session.completed`, the webhook records a `Purchase` and (with
   the console email backend) prints the receipt email to the server console.

> The webhook **requires** a valid `STRIPE_WEBHOOK_SECRET`; events without a
> verifiable signature are ignored. This is intentional for security.

---

## Running tests

```powershell
python manage.py test playground
```

The suite covers page rendering, the username/email login flows, the account
dashboard, and the webhook's purchase-recording logic (with a signed payload).

---

## Security notes

- **Rotate the previously committed secrets.** Earlier revisions of this repo
  contained live Stripe test keys, a webhook secret, and a Gmail App Password.
  Anything that was ever public should be rotated in the Stripe dashboard and
  Google account, then set only via `.env`.
- `.env` is git-ignored; **never commit real secrets**. Use `.env.example` as
  the committed template.
- Before deploying: set `DJANGO_DEBUG=False`, a strong `DJANGO_SECRET_KEY`, real
  `DJANGO_ALLOWED_HOSTS`, run `python manage.py collectstatic`, serve over HTTPS,
  and switch to a production database (e.g. PostgreSQL).

---

## Status

The site runs end-to-end: all pages render, auth and the Stripe checkout flow
work, purchases are recorded, and the test suite passes. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a deeper walkthrough and
ideas for further work.
