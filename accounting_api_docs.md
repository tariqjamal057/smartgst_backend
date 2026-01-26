# Accounting Module API Documentation

This document provides details on the API endpoints for the Accounting module.

**Base URL**: `/api/accounting/`

---

## 1. Financial Years

**Endpoint**: `financial-years/`

### List Financial Years
- **Method**: `GET`
- **URL**: `/api/accounting/financial-years/`
- **Description**: Retrieves a list of all financial years.

### Create Financial Year
- **Method**: `POST`
- **URL**: `/api/accounting/financial-years/`
- **Description**: Creates a new financial year.
- **Request Body**:
  ```json
  {
    "start_date": "2024-04-01",
    "end_date": "2025-03-31",
    "is_locked": false
  }
  ```

### Retrieve, Update, and Delete a Financial Year
- **URL**: `/api/accounting/financial-years/{id}/`
- **Methods**:
  - `GET`: Retrieve a specific financial year.
  - `PUT`/`PATCH`: Update a financial year.
  - `DELETE`: Delete a financial year.
- **Request Body for `PUT`/`PATCH`**:
  ```json
  {
    "is_locked": true
  }
  ```

---

## 2. Chart of Accounts

**Endpoint**: `accounts/`

### List Accounts
- **Method**: `GET`
- **URL**: `/api/accounting/accounts/`

### Create Account
- **Method**: `POST`
- **URL**: `/api/accounting/accounts/`
- **Request Body**:
  ```json
  {
    "name": "Cash Account",
    "account_type": "ASSET",
    "parent": null,
    "is_default": false
  }
  ```
  *   `account_type` choices: `ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`, `EXPENSE`.

### Retrieve, Update, and Delete an Account
- **URL**: `/api/accounting/accounts/{id}/`
- **Methods**: `GET`, `PUT`, `PATCH`, `DELETE`

---

## 3. Parties (Customers/Vendors)

**Endpoint**: `parties/`

### List Parties
- **Method**: `GET`
- **URL**: `/api/accounting/parties/`

### Create Party
- **Method**: `POST`
- **URL**: `/api/accounting/parties/`
- **Description**: Creates a new Party (customer or vendor). An associated ledger account will be created automatically.
- **Request Body**:
  ```json
  {
    "name": "Test Customer Inc.",
    "party_type": "CUSTOMER",
    "gstin": "29ABCDE1234F1Z5",
    "pan": "ABCDE1234F",
    "address": "123 Test Lane, Bangalore"
  }
  ```
  *   `party_type` choices: `CUSTOMER`, `VENDOR`.

### Retrieve, Update, and Delete a Party
- **URL**: `/api/accounting/parties/{id}/`
- **Methods**: `GET`, `PUT`, `PATCH`, `DELETE`

---

## 4. Items

**Endpoint**: `items/`

### List Items
- **Method**: `GET`
- **URL**: `/api/accounting/items/`

### Create Item
- **Method**: `POST`
- **URL**: `/api/accounting/items/`
- **Request Body**:
  ```json
  {
    "name": "Standard Service",
    "hsn_code": "998314",
    "gst_rate": "18.00"
  }
  ```

### Retrieve, Update, and Delete an Item
- **URL**: `/api/accounting/items/{id}/`
- **Methods**: `GET`, `PUT`, `PATCH`, `DELETE`

---

## 5. Sales Invoices

**Endpoint**: `sales-invoices/`

### List Sales Invoices
- **Method**: `GET`
- **URL**: `/api/accounting/sales-invoices/`

### Create Sales Invoice
- **Method**: `POST`
- **URL**: `/api/accounting/sales-invoices/`
- **Request Body**:
  ```json
  {
    "financial_year": 1,
    "voucher_number": "INV-001",
    "date": "2024-07-29",
    "narration": "Sale of services",
    "customer": 1,
    "total_amount": "1180.00",
    "items": [
      {
        "item": 1,
        "quantity": "1.00",
        "rate": "1000.00",
        "amount": "1000.00"
      }
    ]
  }
  ```

### Retrieve, Update, and Delete a Sales Invoice
- **URL**: `/api/accounting/sales-invoices/{id}/`
- **Methods**: `GET`, `PUT`, `PATCH`, `DELETE`
- **Note**: Cannot be updated or deleted if `is_posted` is true or the financial year is locked.

### Post a Sales Invoice
- **Method**: `POST`
- **URL**: `/api/accounting/sales-invoices/{id}/post/`
- **Description**: Posts the invoice to the ledger, creating all necessary debit/credit entries.

---

## 6. Purchase Bills

**Endpoint**: `purchase-bills/`

### List Purchase Bills
- **Method**: `GET`
- **URL**: `/api/accounting/purchase-bills/`

### Create Purchase Bill
- **Method**: `POST`
- **URL**: `/api/accounting/purchase-bills/`
- **Request Body**:
  ```json
  {
    "financial_year": 1,
    "voucher_number": "PB-001",
    "date": "2024-07-29",
    "narration": "Purchase of materials",
    "vendor": 2,
    "total_amount": "590.00",
    "items": [
      {
        "item": 2,
        "quantity": "10.00",
        "rate": "50.00",
        "amount": "500.00"
      }
    ]
  }
  ```

### Retrieve, Update, and Delete a Purchase Bill
- **URL**: `/api/accounting/purchase-bills/{id}/`
- **Methods**: `GET`, `PUT`, `PATCH`, `DELETE`

### Post a Purchase Bill
- **Method**: `POST`
- **URL**: `/api/accounting/purchase-bills/{id}/post/`
- **Description**: Posts the bill to the ledger.

---

## 7. Receipt Vouchers

**Endpoint**: `receipt-vouchers/`

### List Receipt Vouchers
- **Method**: `GET`
- **URL**: `/api/accounting/receipt-vouchers/`

### Create Receipt Voucher
- **Method**: `POST`
- **URL**: `/api/accounting/receipt-vouchers/`
- **Request Body**:
  ```json
  {
    "financial_year": 1,
    "voucher_number": "REC-001",
    "date": "2024-07-30",
    "narration": "Payment received from Test Customer Inc.",
    "party": 1,
    "received_in": 2,
    "amount": "1180.00"
  }
  ```

### Retrieve, Update, and Delete a Receipt Voucher
- **URL**: `/api/accounting/receipt-vouchers/{id}/`
- **Methods**: `GET`, `PUT`, `PATCH`, `DELETE`

### Post a Receipt Voucher
- **Method**: `POST`
- **URL**: `/api/accounting/receipt-vouchers/{id}/post/`
- **Description**: Posts the receipt to the ledger.

---

## 8. Payment Vouchers

**Endpoint**: `payment-vouchers/`

### List Payment Vouchers
- **Method**: `GET`
- **URL**: `/api/accounting/payment-vouchers/`

### Create Payment Voucher
- **Method**: `POST`
- **URL**: `/api/accounting/payment-vouchers/`
- **Request Body**:
  ```json
  {
    "financial_year": 1,
    "voucher_number": "PAY-001",
    "date": "2024-07-30",
    "narration": "Payment made to Test Vendor",
    "party": 2,
    "paid_from": 2,
    "amount": "590.00"
  }
  ```

### Retrieve, Update, and Delete a Payment Voucher
- **URL**: `/api/accounting/payment-vouchers/{id}/`
- **Methods**: `GET`, `PUT`, `PATCH`, `DELETE`

### Post a Payment Voucher
- **Method**: `POST`
- **URL**: `/api/accounting/payment-vouchers/{id}/post/`
- **Description**: Posts the payment to the ledger.

---

## 9. Journal Vouchers

**Endpoint**: `journal-vouchers/`

### List Journal Vouchers
- **Method**: `GET`
- **URL**: `/api/accounting/journal-vouchers/`

### Create Journal Voucher
- **Method**: `POST`
- **URL**: `/api/accounting/journal-vouchers/`
- **Description**: Creates a journal voucher. The API validates that total debits equal total credits.
- **Request Body**:
  ```json
  {
    "financial_year": 1,
    "voucher_number": "JV-001",
    "date": "2024-07-31",
    "narration": "Depreciation for the month",
    "entries": [
      {
        "account": 5,
        "debit": "1500.00",
        "credit": "0.00"
      },
      {
        "account": 6,
        "debit": "0.00",
        "credit": "1500.00"
      }
    ]
  }
  ```

### Retrieve, Update, and Delete a Journal Voucher
- **URL**: `/api/accounting/journal-vouchers/{id}/`
- **Methods**: `GET`, `PUT`, `PATCH`, `DELETE`

### Post a Journal Voucher
- **Method**: `POST`
- **URL**: `/api/accounting/journal-vouchers/{id}/post/`
- **Description**: Posts the journal to the ledger.
