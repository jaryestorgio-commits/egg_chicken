# Egg & Chicken E-Commerce Website

An e-commerce website for browsing and ordering fresh farm eggs, chicken, and product bundles. Customers can create accounts, manage a cart, check out, and track orders. The project also includes administration tools for managing products, inventory, and orders.

## Project background

The site is designed to connect customers with fresh products from trusted local farms. The frontend provides a responsive storefront and customer account pages. A Flask REST API handles authentication, catalog and cart operations, checkout, inventory, orders, and administration. Product, order, inventory, and payment data are stored in PostgreSQL.

## Technology

- Frontend: HTML, CSS, and vanilla JavaScript
- Backend: Python, Flask, Flask-SQLAlchemy, Flask-Migrate, and Flask-JWT-Extended
- Database: PostgreSQL with the Psycopg driver
- Online payments: Xendit hosted checkout for GCash and cards; COD is also available

## Requirements

- Python and pip
- PostgreSQL
- A Xendit test-mode account and webhook configuration to test online payments (optional; COD does not require Xendit)

## Local setup

1. Create a PostgreSQL database for the application, such as `egg_chicken_db`.
2. Create and activate a virtual environment, then install the backend dependencies:

   ```powershell
   cd backend
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

3. Create `backend/.env` and set the variables described below. Keep this file private and out of version control.
4. Apply the database migrations:

   ```powershell
   python -m flask --app app db upgrade
   ```

   For a new, empty database that has no migration history, initialize it with `python init_db.py`, then run `python -m flask --app app db stamp head`.
5. Optionally add the sample catalog:

   ```powershell
   python seed.py
   ```

6. Start the Flask application from the `backend` directory:

   ```powershell
   python app.py
   ```

   Open `http://127.0.0.1:5000`. Flask serves the frontend as well as the API. The API base URL used by the frontend is `http://127.0.0.1:5000/api/v1`.

The frontend can also be served separately with a local static server. The default CORS configuration allows common local origins on ports `5500` and `8000`.

## Environment configuration

Set these variables in `backend/.env`:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask application secret; use a unique, private value. |
| `JWT_SECRET_KEY` | Signs authentication tokens; use a unique, private value. |
| `DATABASE_URL` | PostgreSQL connection URL, for example `postgresql+psycopg://USER:PASSWORD@localhost:5432/egg_chicken_db`. URL-encode special characters in the password. |
| `CORS_ORIGINS` | Comma-separated frontend origins allowed to call the API. Local defaults include ports `5500` and `8000`. |
| `XENDIT_SECRET_KEY` | Xendit server-side test secret key. Sandbox checkout requires the `xnd_development-` or `xnd_development_` prefix. |
| `XENDIT_CALLBACK_TOKEN` | Secret callback token configured in Xendit and sent with invoice webhook requests. |
| `XENDIT_SUCCESS_URL` | Absolute HTTP(S) URL customers return to after successful hosted checkout. Use `{order_id}` where the order ID should appear. |
| `XENDIT_FAILURE_URL` | Absolute HTTP(S) URL customers return to after an unsuccessful or cancelled hosted checkout. Use `{order_id}` where the order ID should appear. |

Example redirect URL values for a local frontend:

```dotenv
XENDIT_SUCCESS_URL=http://127.0.0.1:5500/pages/order-details.html?id={order_id}&payment=success
XENDIT_FAILURE_URL=http://127.0.0.1:5500/pages/order-details.html?id={order_id}&payment=failed
```

### Xendit payment setup

1. Add your Xendit **test-mode** secret key to `XENDIT_SECRET_KEY`. Do not put secret keys in frontend code or commit them.
2. Configure a Xendit invoice/payment notification webhook to call:

   ```text
   https://YOUR_PUBLIC_BACKEND_HOST/api/v1/payments/xendit/webhook
   ```

   The backend must be publicly reachable by Xendit. For local testing, expose the backend through a secure development tunnel and use that public URL in the webhook configuration.
3. Set `XENDIT_CALLBACK_TOKEN` to the same callback token configured for that webhook. The backend verifies the callback and then retrieves the invoice directly from Xendit before updating the payment/order status.
4. Set the success and failure redirect URLs to pages served by your frontend. Redirects communicate the return state to the customer; the verified webhook/API invoice status is authoritative.
5. GCash and card details are entered on Xendit's hosted checkout page. This website does not collect or store card details or GCash credentials.

Online checkout requires all four Xendit variables above. If Xendit is not configured, customers can still use Cash on Delivery.

## API and database

The versioned API is under `/api/v1`. Main route groups include authentication, products, categories, cart, orders, payments, users, inventory, admin, and customer support chat.

Database schema changes are managed with Flask-Migrate/Alembic in `backend/migrations`. After configuring the database, use `python -m flask --app app db upgrade` to apply the checked-in migrations.

## Tests

Backend tests require a separate PostgreSQL test database named `egg_chicken_test_db`. Set `TEST_DATABASE_URL` or provide `DATABASE_URL` in the backend environment; tests are guarded to use only the test database. The test fixture drops and recreates tables, so **never point test configuration at a database containing data you need to keep**.

From the `backend` directory, with its virtual environment active:

```powershell
python -m pytest tests -q
```