# OpenClaw Phase 2 – Client Test Guide

> **Bot:** `@OpenclawHahnbot` | **Server:** `213.160.77.197` | **Date:** April 2026

---

## Overview – What Phase 2 delivers

| Feature | Status |
|---|---|
| 📧 IMAP – Auto-reads new emails from `rechnung@hahn-fleisch.de` | ✅ Active |
| 🔍 Real OCR – Reads invoices using AI Vision (Claude) | ✅ Active |
| 🚨 Fraud detection – Validates IBAN (German vs foreign) | ✅ Active |
| 📱 Telegram review – ACCEPT/REJECT invoices via bot | ✅ Active |

---

## Test 1: Send an invoice photo via Telegram Bot ⭐

The simplest and most realistic way to test.

**Step 1:** Open Telegram → search `@OpenclawHahnbot` → tap Start

**Step 2:** Send an invoice photo (JPEG or PNG) directly to the bot

**Step 3:** Within ~10–20 seconds the bot replies with the extracted data:

```
🧾 Invoice Extracted

🏢 Vendor: Hahn Fleischgroßhandel OHG
   Zenettistraße 10, 80377 München
   Tax ID: DE286551585

🔢 Invoice#: 700000
📅 Date:     2026-04-08

📋 Line Items:
  • Schweine Schlegel  ×0.1 @ 4.71 EUR = 0.47 EUR

💰 Subtotal:  0.44 EUR
🏷  VAT 7%:   0.03 EUR
✅ Total:     0.47 EUR

🏦 IBAN: DE85700202706020146859
   BIC:  HYVEDEMMXXX

Status: ✅ Approved automatically (German IBAN)
```

> **This is the actual result** from `IMG_6214.jpeg` tested on 2026-04-10.

**Tips for best results:**
- Photo should be straight-on, well-lit, and in focus
- Supported formats: JPEG, PNG (send as photo or as document)
- Processing time: ~10–20 seconds

---

## Test 2: IMAP Email Intake

Send an email with an invoice attachment (PDF or image) to:

```
rechnung@hahn-fleisch.de
```

The system will:
1. Check for new emails every **5 minutes**
2. Upload the attachment to MinIO storage
3. Run the full OCR pipeline automatically
4. Send a Telegram alert with the extracted result

> **Emails are never deleted** — they are only marked as Read in the inbox.

---

## Test 3: Fraud Detection & Review Flow

The system automatically checks the IBAN found in each invoice:

| IBAN | Result | Action |
|---|---|---|
| `DE...` (German IBAN) | ✅ Auto-approved | Telegram success notification |
| No IBAN found | ⚠️ `no_iban` | Telegram alert → manual review required |
| Foreign IBAN (FR, GB, PL…) | 🚨 `suspicious` | Telegram alert → manual review required |

**When you receive a "Suspicious Invoice" alert:**

```
⚠️ Suspicious Invoice Detected

Vendor: Unknown Supplier
IBAN: FR7630006000011234567890189
Amount: 5000.00 EUR
Invoice#: OT-2026-9988
From: unknown@offshore.io
Reason: Non-German IBAN detected: FR7630006000011234567890189

DB ID: 29

Reply to review:
ACCEPT_29 — approve invoice
REJECT_29 — mark as spam
```

Reply in the bot chat:
- `ACCEPT_29` → marks invoice as **approved**, queued for payment
- `REJECT_29` → marks invoice as **spam**, blocked

---

## Test 4: Telegram Bot Commands

| Command | Response |
|---|---|
| `/start` | Welcome message |
| `/status` | Invoice stats: pending / approved / spam counts |
| `/help` | Full command list |
| `ACCEPT_N` | Approve invoice #N |
| `REJECT_N` | Reject invoice #N as spam |

---

## Test Checklist ✅

- [ ] Open `@OpenclawHahnbot` → `/start` → receive welcome message
- [ ] `/status` → see invoice statistics
- [ ] Send an invoice photo → receive OCR result within ~20 seconds
- [ ] Send email to `rechnung@hahn-fleisch.de` → receive Telegram alert within ≤5 min
- [ ] Reply `ACCEPT_N` or `REJECT_N` → bot confirms the status update
- [ ] `/status` again → approved count increases

---

## Real Test Result – `IMG_6214.jpeg` (2026-04-10)

Tested with a real Hahn Fleischhandel invoice photo:

| Field | Extracted Value |
|---|---|
| Vendor | Hahn Fleischgroßhandel OHG |
| Address | Zenettistraße 10, 80377 München |
| Tax ID | DE286551585 |
| Invoice# | 700000 |
| Invoice Date | 2026-04-08 |
| IBAN | DE85700202706020146859 |
| BIC | HYVEDEMMXXX |
| Line Item | Schweine Schlegel × 0.1 @ 4.71 EUR |
| Subtotal | 0.44 EUR |
| VAT (7%) | 0.03 EUR |
| **Total** | **0.47 EUR** |
| Invoice Type | customer |
| Fraud Status | ✅ **approved** (German IBAN — auto-approved) |

---

## Connection Details

| Service | URL / Contact |
|---|---|
| **Telegram Bot** | `@OpenclawHahnbot` |
| **n8n Dashboard** | http://213.160.77.197:5678 (admin only) |
| **MinIO Storage** | http://213.160.77.197:9001 (admin only) |
| **Invoice Inbox** | `rechnung@hahn-fleisch.de` |

---

*Phase 2 – Email Intake + AI OCR + Fraud Detection – Ready for Testing* 🚀
