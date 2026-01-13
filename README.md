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

### 6. Run the Development Server
Start the Django development server.
```bash
poetry run python manage.py runserver
```

### 7. Run Celery Workers
In a separate terminal, start the Celery worker to process background tasks.
```bash
poetry run celery -A smart_gst worker -l info
```

## Running Tests

The project uses `pytest` for testing. To run the test suite:
```bash
poetry run pytest
```

## Deployment

The application is designed to be deployed using Docker. A `Dockerfile` and `docker-compose.yml` should be used to build and orchestrate the necessary services (Nginx, Gunicorn, Celery, Redis, PostgreSQL). Refer to the deployment checklist in the architecture documentation before deploying to production.
