# phoneCase254

A Django + SQLite storefront for selling silicon phone cases, with accounts, cart, wishlist, order tracking, password reset, stock control, delivery fees, and an M-Pesa-ready checkout.

## Run locally

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py manage.py migrate
py manage.py seed_store
py manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

## Email and M-Pesa setup

Development email uses Django's console backend, so password-reset links appear in the terminal. Email confirmation is optional locally and controlled by `REQUIRE_EMAIL_CONFIRMATION`; set it to `True` when SMTP is configured for real activation emails. For real email, set `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL` in the environment.

Order notifications are sent immediately to `ORDER_NOTIFICATION_EMAIL` in `config/settings.py`, currently defaulting to `phonecase254.shop@gmail.com`. Configure SMTP for real delivery; during development, notifications appear in the terminal with Django's console email backend.

Set sandbox Daraja values in the ignored `config/credentials.py` file, based on `config/credentials.py.example`, or use environment variables. The current sandbox shortcode is `174379`; set a public HTTPS callback before testing STK Push.

Never commit `.env`, `config/credentials.py`, `db.sqlite3`, `media/`, or private keys. Before pushing to GitHub, copy `.env.example` to `.env` locally and fill in secrets only in the local `.env` or in Render's environment-variable dashboard. The example files intentionally contain placeholders only.

Daraja STK Push is now connected through `shop/services/mpesa.py`. Set `MPESA_CALLBACK_URL` to a public HTTPS URL ending in `/mpesa/callback/` before testing payments. A localhost URL cannot receive Safaricom's callback; use a deployed domain or an HTTPS tunnel during development. Keep the supplied consumer secret and passkey private, and rotate them in the Daraja portal if they have been exposed anywhere public.

## Product photos

The starter catalog uses hosted photos from Unsplash and Pexels through `Product.image_url`. Replace these URLs with your own product photography whenever you are ready. The current references are the [Unsplash phone-case collection](https://unsplash.com/s/photos/phone-case) and [Pexels phone-case collection](https://www.pexels.com/search/phone%20case/).

## Deploy to Render

This project includes `render.yaml` and `build.sh`. Push the `phoneCase254` folder to a Git repository, create a new Render Blueprint, and select that repository. Render will create the web service and a managed Postgres database, install dependencies, collect static files, run migrations, and seed the starter catalog.

After the first deploy, set these Render environment variables: `DJANGO_CSRF_TRUSTED_ORIGINS` to your full URL such as `https://phonecase254.onrender.com`, `MPESA_CALLBACK_URL` to `https://phonecase254.onrender.com/mpesa/callback/`, your SMTP values, and the M-Pesa secrets. Render services have ephemeral filesystems, so use `Product.image_url` or add durable object storage/persistent disk for uploaded photos. SQLite remains available for local development; Render uses Postgres when `DATABASE_URL` is present.
