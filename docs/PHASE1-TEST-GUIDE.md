# OpenClaw Phase 1 – Delivery & Test Guide

> **Delivery Date:** April 2026 | **Version:** 1.0 | **Environment:** Production (VPS)

---

## Overview

Phase 1 delivers a fully operational **document processing automation foundation** on your VPS (`213.160.77.197`), including:

- ✅ **n8n Workflow Engine** – 2 active workflows running 24/7
- ✅ **Telegram Bot** – Real-time notifications & system status queries
- ✅ **OCR Invoice Demo Pipeline** – Webhook-triggered invoice data extraction
- ✅ **MinIO Object Storage** – Secure file storage for processed documents
- ✅ **Dockerized Infrastructure** – All services containerized & auto-restart enabled

---

## 1. Access Credentials 🔑

| Service | URL | Email / Username | Password |
|---|---|---|---|
| **n8n Dashboard** | http://213.160.77.197:5678 | `admin@openclaw.io` | `OpenClaw2024!` |
| **MinIO Console** | http://213.160.77.197:9001 | `minioadmin` | `MinioPass2024!` |
| **Telegram Bot** | `@OpenClawAssistantbinhtest_bot` | — | — |

> ⚠️ **Note:** n8n v2 uses **email-based authentication**. Enter `admin@openclaw.io` in the **Email** field when logging in (not a username).

---

## 2. Test Checklist ✅

### Test 1: n8n Dashboard Access

1. Open → http://213.160.77.197:5678
2. Login với **Email:** `admin@openclaw.io` | **Password:** `OpenClaw2024!`
   > n8n v2 hiển thị field **"Email"** (không phải "Username") – nhập địa chỉ email đầy đủ
3. Navigate to **Workflows** tab
4. ✅ Verify **2 workflows** are visible and **Active**:
   - `Telegram Bot v2`
   - `OCR Invoice Demo`

---

### Test 2: Telegram Bot

1. Open Telegram → search `@OpenClawAssistantbinhtest_bot`
2. Click **Start** or type `/start`

| Command | Expected Response |
|---|---|
| `/start` | Welcome message with your **Chat ID** |
| `/status` | System status report (n8n, MinIO, uptime) |
| `/help` | Full command list |

✅ All 3 commands should respond within **5 seconds**.

---

### Test 3: OCR Demo Pipeline

**Option A – cURL (Terminal):**

```bash
curl -X POST http://213.160.77.197:5678/webhook/ocr-demo \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png",
    "filename": "test_invoice.png"
  }'
```

**Option B – Postman:**
- Method: `POST`
- URL: `http://213.160.77.197:5678/webhook/ocr-demo`
- Body: `raw / JSON` with the payload above

**Expected JSON Response:**

```json
{
  "success": true,
  "data": {
    "vendor_name": "Sample Vendor GmbH",
    "invoice_number": "INV-2026-001",
    "invoice_date": "2026-04-06",
    "total_amount": 8800000,
    "vat_rate": 10,
    "currency": "EUR"
  }
}
```

✅ Check your **Telegram Bot** – you should receive a notification with the extracted invoice data within seconds.

---

## 3. System Architecture 🏗️

```
                    ┌─────────────────────────────────┐
                    │         VPS 213.160.77.197       │
                    │                                  │
  Webhook/API ──────►  n8n (port 5678)                │
                    │    ├─ Telegram Bot Workflow      │
                    │    └─ OCR Invoice Workflow       │
                    │         │                        │
  Telegram ◄────────────────  │  ─────► MinIO (9000)  │
  (notifications)  │                    (file storage) │
                    └─────────────────────────────────┘
```

- All services run in **Docker containers** with `restart: always`
- Data persisted in Docker volumes (survives reboots)
- No external dependencies required for Phase 1 demo

---

## 4. What's Next – Phase 2 🚀

| Feature | Description |
|---|---|
| 🤖 **Real OCR Engine** | Claude Vision API key integration for accurate invoice reading |
| 📧 **Email Intake** | IMAP connector for automatic invoice processing from inbox |
| 🏦 **Bank Integration** | PSD2/FinTS connection for payment reconciliation |
| 📊 **Dashboard** | Web UI to view processed invoices and analytics |

---

## 5. Support Contact 📬

For questions or issues during testing, please reach out:

- **Project Lead:** [Your Name / Team]
- **Response Time:** Within 24 hours (business days)
- **Reference:** OpenClaw Phase 1 – `213.160.77.197`

---

*Thank you for reviewing Phase 1. All services are live and ready for your testing.* 🎉
