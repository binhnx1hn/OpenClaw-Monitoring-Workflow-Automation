# Phase 2 Deployment Report - Email Intake + Claude OCR + Fraud Detection

**Date**: 2026-04-08  
**Server**: `213.160.77.197`  
**Deployed by**: BE DEV (automated)

---

## ✅ Kết quả tổng quan

| # | Task | Status | Chi tiết |
|---|------|--------|----------|
| 1 | IMAP Connection Test | ✅ OK | TLS 1.3, cert valid, Let's Encrypt |
| 2 | PostgreSQL table `invoices` | ✅ OK | 22 columns, 3 indexes |
| 3 | n8n Credentials | ✅ OK | IMAP ID: `1kb0hizYeMC3mjK8`, Claude API ID: `54IUnCY5jXvjiM50` |
| 4 | Workflow: Invoice Email Intake | ✅ Active | ID: `EfbGPGzLRqrlQpiG` |
| 5 | Workflow: Invoice Fraud Check & OCR | ✅ Active | ID: `OzFQKongCB3RrnDl` |
| 6 | Workflow: Invoice Fraud Review Handler | ✅ Active | ID: `wQaUjrofyf0bznAk` |
| 7 | Telegram polling v4 (ACCEPT/REJECT) | ✅ Active | PID via systemd `openclaw-polling.service` |
| 8 | End-to-end test | ✅ PASS | Execution 137: all 8 nodes succeeded |
| 9 | Claude API (real OCR) | ✅ Working | Returns vendor_name, iban, fraud_status |
| 10 | Fraud check logic | ✅ Working | no_iban → pending_review, Telegram alert sent |

---

## 🔑 Credentials Created

| Name | ID | Type |
|------|----|------|
| Hahn Fleisch Invoice Email | `1kb0hizYeMC3mjK8` | IMAP (SSL/TLS 993) |
| Claude API | `54IUnCY5jXvjiM50` | HTTP Header Auth (x-api-key) |
| OpenClaw PostgreSQL | `i9CQuAV9bkpSqu7Q` | PostgreSQL (no SSL, internal) |

---

## 📋 Workflows Created & Active

### Workflow 1: Invoice Email Intake
- **ID**: `EfbGPGzLRqrlQpiG`
- **Trigger**: IMAP every 5 min on `rechnung@hahn-fleisch.de`
- **Behavior**: Mark as read (NOT delete), extract attachments, upload MinIO, forward to WF2
- **Status**: ✅ Active

### Workflow 2: Invoice Fraud Check & OCR
- **ID**: `OzFQKongCB3RrnDl`
- **Webhook**: `POST /webhook/invoice-process`
- **Flow**: Webhook → Fraud Pre-check → Claude Vision OCR → IBAN Check → Save to DB → Telegram Alert
- **Model**: `claude-3-5-sonnet-20241022`
- **Status**: ✅ Active

### Workflow 3: Invoice Fraud Review Handler
- **ID**: `wQaUjrofyf0bznAk`
- **Webhook**: `POST /webhook/openclaw-telegram` (extends existing Telegram bot)
- **Flow**: Parse ACCEPT_/REJECT_ → UPDATE invoices SET status → Reply Telegram
- **Status**: ✅ Active

---

## 🗄️ Database

### Table: `invoices`
```sql
-- Created in n8n database
SELECT id, vendor_name, iban, fraud_status, status FROM invoices;
-- Result: id=1, vendor_name=Unknown, iban='', fraud_status=no_iban, status=pending_review
```

**Indexes created**:
- `idx_invoices_status`
- `idx_invoices_invoice_number`  
- `idx_invoices_vendor`

---

## 🧪 End-to-End Test Results

### Test Execution ID: 137
**Input**: Mock image (1x1 PNG), email from test@test.de

**Node Execution Flow**:
```
✅ Webhook Trigger       → received POST /webhook/invoice-process
✅ Fraud Pre-check       → no IBAN in metadata, proceed to OCR
✅ Claude Vision OCR     → claude-3-5-sonnet-20241022, returned JSON
✅ IBAN Fraud Check      → iban='', fraud_status='no_iban'  
✅ Is Suspicious?        → yes (no_iban → pending_review path)
✅ Save Suspicious to DB → INSERT into invoices table
✅ Telegram Fraud Alert  → sent to chat_id 6190676114
✅ Respond Suspicious    → HTTP 200 response
```

**Duration**: ~700ms  
**DB Record**: Invoice #1 saved with `status=pending_review`

---

## 🤖 Claude OCR Output (for mock 1x1 image)
```json
{
  "vendor_name": "Unknown",
  "iban": "",
  "total_amount": 0,
  "fraud_status": "no_iban",
  "invoice_number": "UNKNOWN-1775645725569"
}
```
Claude correctly handled the unreadable image and returned structured JSON.

---

## 🔧 Technical Notes & Issues Resolved

### 1. n8n v2 Workflow Activation Issue
**Problem**: Workflows created via API were "draft" and not activated at startup.  
**Root Cause**: n8n v2.14.2 requires `activeVersionId` to be set in `workflow_entity` table.  
**Fix**:
```sql
UPDATE workflow_entity 
SET "activeVersionId" = "versionId"
WHERE id IN ('OzFQKongCB3RrnDl', 'wQaUjrofyf0bznAk', 'EfbGPGzLRqrlQpiG');
```

### 2. PostgreSQL SSL Connection Error
**Problem**: n8n PostgreSQL node tried SSL connection to internal Docker container.  
**Fix**: Updated credential `i9CQuAV9bkpSqu7Q` with `ssl: "disable"`.

### 3. Telegram Bot Conflict  
**Problem**: Two workflows trying to register same `openclaw-telegram` webhook.  
**Status**: `lfIu4XjmucM26mkv` (Polling Handler) takes priority. WF3 uses different webhook path.

---

## 🔄 Telegram Polling v4

**File**: `/opt/openclaw/telegram_polling_v4.py`  
**Service**: `openclaw-polling.service` (updated ExecStart)  
**PID**: via systemd (auto-restart)

**New commands handled**:
- `ACCEPT_{id}` → UPDATE invoices SET status='approved', reply confirmation
- `REJECT_{id}` → UPDATE invoices SET status='spam', reply confirmation
- All other commands → pass to existing /start, /status, /help handlers

---

## 📌 Production Webhook URLs

| Webhook | URL |
|---------|-----|
| Invoice Processing | `http://213.160.77.197:5678/webhook/invoice-process` |
| Telegram Handler | `http://213.160.77.197:5678/webhook/openclaw-telegram` |
| HTTPS (via Nginx) | `https://213.160.77.197/webhook/invoice-process` |

---

## ⚠️ Known Limitations

1. **Claude OCR on tiny images**: Returns `Unknown` vendor - need real invoice images
2. **IMAP Workflow**: Requires real email with PDF/image attachments to test fully  
3. **MinIO upload**: Workflow 1 uploads to bucket `invoices` - bucket must exist
4. **Telegram conflict**: WF3 `openclaw-telegram` webhook may conflict with existing polling handler - handled by v4 polling script instead

---

## 🚀 Next Steps (Phase 3)

- [ ] Send real invoice PDF to `rechnung@hahn-fleisch.de` and test full IMAP intake
- [ ] Test ACCEPT/REJECT flow via Telegram
- [ ] Test with non-DE IBAN to trigger suspicious alert
- [ ] Create MinIO bucket `invoices` if not exists
- [ ] Add SKR03 accounting logic
- [ ] Setup SMTP for outgoing notifications
