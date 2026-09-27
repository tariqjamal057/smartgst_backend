# SmartGST Backend

This repository contains the backend source code for the SmartGST platform, a cloud-based GST compliance and accounting SaaS application designed for CAs, GST practitioners, and businesses.

## Overview

SmartGST is a comprehensive platform that automates GST compliance, accounting processes, and client communication. It is built as a modular monolithic Django application to ensure data consistency, operational simplicity, and high security. The system provides a complete workflow for filing GST returns, generating e-invoices and e-way bills, managing clients, and handling core accounting tasks.

## Core Features

- **GST Compliance Automation**: Automated preparation of GSTR-1 & GSTR-3B, GSTR-2B reconciliation, and direct filing via GSP APIs.
- **Accounting Management**: Features a full accounting suite including a chart of accounts, sales/purchase vouchers, ledgers, P&L statements, and balance sheets.
- **E-Invoicing & E-Way Bills**: Seamless generation of IRNs, QR codes, and e-way bills from invoice data.
- **Multi-Tenancy SaaS**: Securely manage multiple CA firms and their clients from a single platform with strict data isolation.
- **Client & Document Management**: Centralized client database, document uploading, and staff assignments.
- **Resilient Task Handling**: Asynchronous task queue ensures that GST API downtime does not interrupt user workflows, guaranteeing zero data loss.
- **Automated Communication**: WhatsApp and email reminders for due dates, missing documents, and filing confirmations.
- **Comprehensive Reporting**: Generation of GST, accounting, reconciliation, and client activity reports in PDF and Excel formats.
- **Subscription & Billing**: Yearly subscription plans managed via a built-in billing module.

## Architecture

The backend is a **Modular Monolithic Django Application**. This architecture was chosen to ensure strong data consistency (ACID transactions), operational simplicity, and rapid development speed, which are critical for a financial compliance platform.

### Core Design Principles

1.  **Backend-First Logic**: All business logic, calculations, and validations reside in the Django backend. The frontend is stateless.
2.  **No Dependency on GST API Availability**: Critical user actions are queued and executed asynchronously by background workers, making the system resilient to external API failures.
3.  **Persistent Action Before Execution**: Every critical action is saved to the database *before* being dispatched to an external service, eliminating data loss risk.
4.  **Multi-Tenant Data Isolation**: A shared database schema is used, with a `tenant_id` foreign key in every relevant table to enforce strict data separation between tenants (CA firms).

## Technology Stack

### Backend
- **Framework**: Django 4.2+
- **Database**: PostgreSQL 14+
- **API**: Django REST Framework
- **Asynchronous Tasks**: Celery with Redis as the broker
- **WSGI Server**: Gunicorn / uWSGI

### Frontend (for reference)
- **Framework**: React JS or Next JS

### Deployment
- **Cloud**: AWS / Digital Ocean
- **Containerization**: Docker
- **CI/CD**: GitHub Actions

## Project Structure

The project follows a modular structure to enforce separation of concerns:

```
smart_gst/
├── core/         # Tenant management, users, roles
├── accounting/   # Accounting engine, ledgers, vouchers
├── gst_engine/   # GST computation logic (GSTR-1, 3B)
├── gsp_integration/ # Handles communication with GSP APIs (e.g., Vayana)
├── action_queue/ # Persistent asynchronous task queue for resilience
├── documents/    # File uploads and storage (S3/GCS)
├── automation/   # Reminders and scheduled tasks
├── reports/      # PDF and Excel report generation
├── billing/      # Subscription and payment management
├── audit_logs/   # Compliance and activity logging
├── api/          # Aggregated REST API layer (urls, middleware)
└── settings/     # Django settings (base, development, production)
```

## Local Development Setup

Follow these steps to set up the project for local development.

### 1. Prerequisites
- Python 3.10+
- Poetry for dependency management
- PostgreSQL 14+
- Redis

### 2. Clone the Repository
```bash
git clone <repository-url>
cd smart_backend
```

### 3. Install Dependencies
Install the required Python packages using Poetry.
```bash
poetry install
```

### 4. Configure Environment
Create a `.env` file in the root directory and configure your database, Redis, and other settings.
```
DEBUG=True
SECRET_KEY='your-secret-key'
DATABASE_URL='postgres://user:password@localhost:5432/smartgst_db'
REDIS_URL='redis://localhost:6379/0'
```

### 5. Set Up the Database
Run the initial database migrations.
```bash
poetry run python manage.py migrate
```

### 6. Seed Subscription Plans

Manage subscription plans using the interactive plan manager.

```bash
poetry run python manage.py manage_plans
```

Options:
- `1` — Add predefined plans (Starter / Professional / Enterprise).
- `2` — Add dynamic plans: enter a count, then provide details for each plan one by one (name, price, period, clients, users, support).
- `3` — List all existing plans.
- `4` — Delete a plan (by ID, with confirmation). Plans that have linked subscriptions or payments cannot be deleted.

Supported plan periods: `year` (Year), `month` (Month), and `custom` (Custom Days, between 1 and 30 days).

Alternatively, seed only the predefined plans (non-interactive):
```bash
poetry run python manage.py seed_plans
```

### 7. Run the Development Server
Start the Django development server. The server runs under ASGI (Daphne, via the
`channels` app), so it serves both the HTTP API and the WebSocket endpoint
(`ws://localhost:8000/ws/notifications/`).
```bash
poetry run python manage.py runserver
```

### 8. Run Celery Workers
In a separate terminal, start the Celery worker to process background tasks.
```bash
poetry run celery -A smart_gst worker -l info
```

## Notifications & WebSocket

The portal supports real-time in-app notifications pushed over Redis
(`CHANNEL_LAYERS` reuses `REDIS_URL`). A logged-in user's browser connects to
`/ws/notifications/?token=<access_token>` and receives a `notification.new`
payload whenever a notification is created for them.

Creating a notification also broadcasts the push (works from Django views,
management commands, and future Celery tasks alike):

```python
from gst_portal.services import create_notification

create_notification(user=user, title="Title", message="Body", notification_type="Info")
```

Test helpers:

```bash
# Seed a batch of sample notifications across all types (Live push as it runs):
poetry run python manage.py seed_notifications --user user@example.com --count 6

# Send a single live notification:
poetry run python manage.py notify_test user@example.com "Your title" "Your message" "Warning"
```

`notification_type` values the frontend styles: `Info`, `Success`, `Warning`,
`Deadline`, `Upload`. Example `notify_test` commands, one per type, with a
custom message (a live push hits the user's browser instantly while the
dashboard is open):

```bash
# Success - filing completed
poetry run python manage.py notify_test user@example.com "GSTR-1A filed successfully" "Your GSTR-1A for FEB 2026 has been submitted to GSTN." "Success"

# Deadline - filing reminder
poetry run python manage.py notify_test user@example.com "Filing deadline approaching" "GSTR-1 is due in 2 days - file before 11th to avoid late fees." "Deadline"

# Upload - document/statement ready
poetry run python manage.py notify_test user@example.com "Client statement uploaded" "Prepared GSTR-2B statement for M/s ABC Traders is ready to download." "Upload"

# Warning - reconciliation alert
poetry run python manage.py notify_test user@example.com "ITC mismatch warning" "ITC mismatch found in GSTR-2A for M/s XYZ Enterprises - reconcile soon." "Warning"

# Info - general announcement
poetry run python manage.py notify_test user@example.com "New update available" "SmartGST 2.3 released - see the What's New section." "Info"
```

If a browser was not connected at push time it picks the notification up on the
next page load (or within ~20s, since the dashboard also polls at a low rate).

REST endpoints: `GET/POST /gst-app/notifications/`,
`POST /gst-app/notifications/mark-read/` (`{"ids": [...]}`),
`POST /gst-app/notifications/mark-all-read/`.

## News & Updates Seeding

The News & Updates page (`/gst-app/news/`, `GET`) is 100% API-driven — the
React app hardcodes no articles. The `NewsArticle` table holds the feed:

```bash
# Seed the predefined dataset (idempotent - existing titles are skipped):
poetry run python manage.py seed_news

# Wipe the table, then seed the predefined dataset:
poetry run python manage.py seed_news --delete-all --seed

# Generate 40 synthetic articles (all six types, 2017-2026) for demos/testing:
poetry run python manage.py seed_news --delete-all --dynamic --count 40

# Just empty the feed (page shows "No news published yet."):
poetry run python manage.py seed_news --delete-all
```

## Dashboard Links & Portals Seeding

The `/user` dashboard "Important Links" and "Important Portals" sections are
API-driven from the `DashboardLink` model (`/gst-app/dashboard-links/?kind=link|portal`).
A single seeder with exactly two modes manages both:

```bash
# Seed the static dataset (4 links + 5 govt. portals; idempotent):
poetry run python manage.py seed_links

# Generate many dynamic entries (links + portals) for demos/testing:
poetry run python manage.py seed_links --dynamic --count 50
```

## Running Tests

The project uses `pytest` for testing. To run the test suite:
```bash
poetry run pytest
```

## Deployment

The application is designed to be deployed using Docker. A `Dockerfile` and `docker-compose.yml` should be used to build and orchestrate the necessary services (Nginx, Gunicorn, Celery, Redis, PostgreSQL). Refer to the deployment checklist in the architecture documentation before deploying to production.
