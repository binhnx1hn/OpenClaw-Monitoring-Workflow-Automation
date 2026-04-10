# OpenClaw Phase 2 – Test Guide
## Email Intake (IMAP) + Real OCR Pipeline (Claude Vision)

> **Server:** `213.160.77.197` | **n8n:** v2.14.2 | **Date:** April 2026

---

## Tổng quan Pipeline Phase 2

```
📧 Email (rechnung@hahn-fleisch.de)
        │  IMAP every 5 min (Mark as Read, NOT deleted)
        ▼
[WF1] Invoice Email Intake
        │  Extract PDF/image attachment → Upload MinIO
        ▼
[WF2] Invoice Fraud Check & OCR  (POST /webhook/invoice-process)
        │  Claude Vision API → Extract: vendor, IBAN, amount...
        │  IBAN Check: DE → approved | non-DE → suspicious | empty → no_iban
        ▼
[PostgreSQL] invoices table
        │
        ▼
[Telegram Bot] Alert → ACCEPT_{id} / REJECT_{id}
```

---

## Kiểm tra trạng thái ban đầu

Trước khi test, xác nhận hệ thống đang chạy:

### 1. Kiểm tra Docker containers

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Kết quả mong đợi:
```
NAMES               STATUS          PORTS
openclaw_n8n        Up XX hours     0.0.0.0:5678->5678/tcp
openclaw_postgres   Up XX hours     5432/tcp
openclaw_minio      Up XX hours     0.0.0.0:9000-9001->9000-9001/tcp
```

### 2. Kiểm tra Telegram Polling v4

```bash
systemctl status openclaw-polling.service
```

Kết quả mong đợi: `Active: active (running)`

### 3. Kiểm tra n8n workflows đang active

```bash
docker exec openclaw_postgres psql -U n8n n8n -c \
  "SELECT name, active FROM workflow_entity WHERE active=true ORDER BY name;"
```

Cần có 3 workflows Phase 2:
- `Invoice Email Intake` → active = t
- `Invoice Fraud Check & OCR` → active = t
- `Invoice Fraud Review Handler` → active = t

---

## TEST 1: Pipeline OCR & Fraud Check (Webhook trực tiếp)

**Mục đích:** Test toàn bộ pipeline OCR + lưu DB + Telegram alert mà không cần email thật.

### Test 1A: Invoice không có IBAN (→ pending_review)

```bash
curl -X POST http://213.160.77.197:5678/webhook/invoice-process \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test_no_iban.pdf",
    "minio_path": "invoices/2026-04-09/test_no_iban.pdf",
    "source": "manual_test",
    "email_from": "supplier@test.de",
    "email_subject": "Rechnung April 2026",
    "mime_type": "application/pdf",
    "base64_data": ""
  }'
```

**Kết quả mong đợi:**
```json
{
  "status": "pending_review",
  "message": "Invoice flagged for fraud review",
  "invoice_id": 3,
  "fraud_status": "no_iban",
  "reason": "No IBAN found in invoice"
}
```

✅ **Telegram Bot** sẽ gửi alert:
```
⚠️ Suspicious Invoice Detected
Vendor: Unknown
IBAN: (empty)
Reason: No IBAN found in invoice
Reply: ACCEPT_3 or REJECT_3
```

---

### Test 1B: Invoice với IBAN Đức (→ approved tự động)

> ⚠️ **Lưu ý quan trọng:** Pipeline `/webhook/invoice-process` dùng Claude Vision để đọc ảnh từ `base64_data`. Nếu `base64_data` rỗng hoặc là ảnh 1x1px, Claude **không đọc được IBAN** → luôn trả `no_iban`.  
> Để test đúng `approved` hoặc `suspicious`, dùng **một trong 2 cách sau:**

**Cách 1 – Product Bot (đơn giản nhất):**
1. Mở `@OpenclawHahnbot` trên Telegram
2. Gửi ảnh chụp hóa đơn có **IBAN bắt đầu bằng `DE`** (VD: hóa đơn Hahn Fleisch thật)
3. Bot OCR → IBAN `DE...` → **tự động approved** → nhận Telegram thông báo ✅

**Cách 2 – Webhook với ảnh base64 thật (từ server):**

```bash
# Bước 1: Tạo ảnh invoice test có IBAN Đức
convert -size 800x600 xc:white \
  -font "DejaVu-Sans" -pointsize 18 \
  -annotate +50+60  "RECHNUNG" \
  -annotate +50+140 "Rechnungsnummer: MF-2026-0042" \
  -annotate +50+380 "Gesamtbetrag: 267.50 EUR" \
  -annotate +50+480 "IBAN: DE89370400440532013000" \
  -annotate +50+520 "BIC: COBADEFFXXX" \
  /tmp/approved_de.jpg

# Bước 2: Encode và gửi
python3 -c "
import base64, json
b64 = base64.b64encode(open('/tmp/approved_de.jpg','rb').read()).decode()
json.dump({'filename':'approved_de.jpg','minio_path':'invoices/test/approved_de.jpg',
           'source':'manual_test','email_from':'lieferant@muster.de',
           'email_subject':'Rechnung April 2026','mime_type':'image/jpeg',
           'base64_data': b64}, open('/tmp/p.json','w'))
print('OK, size:', len(b64))
"

curl -X POST http://213.160.77.197:5678/webhook/invoice-process \
  -H "Content-Type: application/json" \
  -d @/tmp/p.json
```

**Kết quả mong đợi (IBAN Đức):**
```json
{"status": "approved", "vendor_name": "...", "invoice_number": "MF-2026-0042"}
```
✅ **Telegram** nhận: `✅ Invoice Processed Successfully`

---

### Test 1C: Invoice với IBAN nước ngoài (→ suspicious)

**Cách 1 – Product Bot:**
1. Mở `@OpenclawHahnbot`
2. Gửi ảnh hóa đơn có **IBAN không phải `DE`** (VD: `FR`, `GB`, `PL`...)
3. Bot OCR → IBAN non-DE → flagged **suspicious** → nhận Telegram alert ⚠️

**Cách 2 – Webhook với ảnh base64 thật (từ server):**

```bash
# Bước 1: Tạo ảnh invoice có IBAN Pháp
convert -size 800x600 xc:white \
  -font "DejaVu-Sans" -pointsize 18 \
  -annotate +50+60  "INVOICE" \
  -annotate +50+140 "Invoice Number: OT-2026-9988" \
  -annotate +50+380 "TOTAL: 6000.00 EUR" \
  -annotate +50+480 "IBAN: FR7630006000011234567890189" \
  -annotate +50+520 "BIC: BNPAFRPPXXX" \
  /tmp/suspicious_fr.jpg

# Bước 2: Encode và gửi
python3 -c "
import base64, json
b64 = base64.b64encode(open('/tmp/suspicious_fr.jpg','rb').read()).decode()
json.dump({'filename':'suspicious_fr.jpg','minio_path':'invoices/test/suspicious_fr.jpg',
           'source':'manual_test','email_from':'unknown@offshore.io',
           'email_subject':'Payment Required','mime_type':'image/jpeg',
           'base64_data': b64}, open('/tmp/p.json','w'))
print('OK, size:', len(b64))
"

curl -X POST http://213.160.77.197:5678/webhook/invoice-process \
  -H "Content-Type: application/json" \
  -d @/tmp/p.json
```

**Kết quả mong đợi (IBAN nước ngoài):**
```json
{"status": "pending_review", "fraud_status": "suspicious", "reason": "Non-German IBAN detected: FR76..."}
```
⚠️ **Telegram** nhận alert yêu cầu ACCEPT/REJECT

---

## TEST 2: ACCEPT / REJECT qua Telegram Bot

Sau khi nhận được alert Telegram ở Test 1, reply vào bot:

### Accept invoice:
```
ACCEPT_3
```

**Kết quả mong đợi:**
```
✅ Invoice #3 accepted and queued for processing
Vendor: Unknown
Status updated to: approved ✓
```

### Reject invoice:
```
REJECT_3
```

**Kết quả mong đợi:**
```
❌ Invoice #3 rejected and marked as spam
Status updated to: spam ✗
```

### Xác nhận trong DB:
```bash
docker exec openclaw_postgres psql -U n8n n8n -c \
  "SELECT id, vendor_name, fraud_status, status FROM invoices ORDER BY id DESC LIMIT 5;"
```

---

## TEST 3: IMAP Email Intake (Email thật)

> **Quan trọng:** Email **KHÔNG bị xóa** sau khi đọc.  
> Workflow dùng `postProcessAction: "read"` → chỉ đánh dấu **đã đọc (Seen)**, email vẫn còn trong hộp thư.

### Cách gửi email test:

1. Gửi email có attachment PDF hoặc ảnh invoice đến:
   ```
   rechnung@hahn-fleisch.de
   ```

2. Workflow sẽ tự động xử lý trong vòng **5 phút** (polling interval)

3. Theo dõi log:
```bash
# Log n8n
docker logs openclaw_n8n --tail=50 -f

# Log polling bot
tail -f /opt/openclaw/polling_v4.log
```

### Theo dõi workflow trong n8n Dashboard:

1. Mở: http://213.160.77.197:5678
2. Login: `admin@openclaw.io` / `OpenClaw2024!`
3. Vào **Workflow** → `Invoice Email Intake`
4. Click **Executions** để xem lịch sử chạy

### Kiểm tra file trong MinIO:

Sau khi email được xử lý, attachment sẽ được upload vào MinIO:
- MinIO Console: http://213.160.77.197:9001
- Login: `minioadmin` / `MinioPass2024!`
- Bucket: `invoices/` → folder theo ngày `2026-04-09/`

Hoặc kiểm tra bằng CLI:
```bash
docker exec openclaw_minio mc ls local/invoices/ --recursive
```

---

## TEST 4: Kiểm tra Database

```bash
docker exec openclaw_postgres psql -U n8n n8n -c "
SELECT 
  id, 
  vendor_name, 
  iban, 
  fraud_status, 
  status, 
  email_from,
  filename,
  to_char(created_at, 'YYYY-MM-DD HH24:MI') as created
FROM invoices 
ORDER BY id DESC 
LIMIT 10;"
```

**Ý nghĩa các giá trị:**

| `fraud_status` | `status` | Ý nghĩa |
|---|---|---|
| `approved` | `approved` | IBAN Đức → tự động approved |
| `no_iban` | `pending_review` | Không có IBAN → chờ review thủ công |
| `suspicious` | `pending_review` | IBAN nước ngoài → chờ review thủ công |
| `approved` | `approved` | Đã ACCEPT qua Telegram |
| `rejected` | `spam` | Đã REJECT qua Telegram |

---

## TEST 5: Telegram Bot Commands

Mở Telegram → `@OpenClawAssistantbinhtest_bot`

| Command | Mô tả |
|---|---|
| `/start` | Xem welcome message |
| `/status` | Xem stats invoice từ DB (count theo status) |
| `/help` | Danh sách commands |
| `ACCEPT_N` | Accept invoice ID = N |
| `REJECT_N` | Reject invoice ID = N |

---

## Checklist Test Đầy Đủ ✅

- [ ] **Test 1A** – Webhook không có IBAN → nhận alert Telegram với `pending_review`
- [ ] **Test 1B** – Webhook với base64 image → Claude OCR chạy (có thể trả `no_iban` nếu ảnh nhỏ)
- [ ] **Test 2A** – Reply `ACCEPT_N` trong Telegram → DB cập nhật `status=approved`
- [ ] **Test 2B** – Reply `REJECT_N` trong Telegram → DB cập nhật `status=spam`
- [ ] **Test 3** – Gửi email thật đến `rechnung@hahn-fleisch.de` → email còn trong hộp thư (không bị xóa), file lên MinIO, Telegram nhận alert
- [ ] **Test 4** – Kiểm tra bảng `invoices` trong DB có đủ dữ liệu
- [ ] **Test 5** – `/status` bot trả về số lượng invoice theo status

---

## Troubleshooting

### n8n workflow không chạy

```bash
# Restart n8n
docker restart openclaw_n8n
sleep 5

# Kích hoạt lại workflows nếu cần
docker exec openclaw_postgres psql -U n8n n8n -c "
UPDATE workflow_entity 
SET \"activeVersionId\" = \"versionId\"
WHERE id IN ('OzFQKongCB3RrnDl', 'wQaUjrofyf0bznAk', 'EfbGPGzLRqrlQpiG');"
```

### Telegram bot không respond

```bash
# Kiểm tra polling service
systemctl status openclaw-polling.service

# Restart nếu cần
systemctl restart openclaw-polling.service

# Xem log
tail -50 /opt/openclaw/polling_v4.log
```

### Webhook trả lỗi 404

```bash
# Kiểm tra workflow active
docker exec openclaw_postgres psql -U n8n n8n -c \
  "SELECT id, name, active FROM workflow_entity WHERE name LIKE '%Fraud%';"
```

### IMAP không fetch email mới

- Kiểm tra email đã được đánh dấu **Unread** trong hộp thư (workflow chỉ fetch UNSEEN)
- Nếu email đã đọc thì mark lại là Unread trong email client, sau đó đợi 5 phút
- Hoặc test trực tiếp bằng webhook (Test 1)

---

## Connection Details

| Service | URL | Login |
|---|---|---|
| n8n Dashboard | http://213.160.77.197:5678 | admin@openclaw.io / OpenClaw2024! |
| MinIO Console | http://213.160.77.197:9001 | minioadmin / MinioPass2024! |
| Telegram Bot | @OpenclawHahnbot | — |
| Email Inbox | rechnung@hahn-fleisch.de | (IMAP: mail.hahn-fleisch.de:993) |

---

## Known Issues & Fixes Log

### [2026-04-10] `/status` silently fails — no reply from bot

**Symptom:** User sends `/status` to `@OpenclawHahnbot`, bot does not reply. `/help` and `/start` work fine.

**Root cause:** `client_telegram_polling.py` line 157 — DB status values like `pending_review` contain underscore `_`. When embedded in a Telegram Markdown message, `_text_` is parsed as italic formatting. The unpaired `_` caused Telegram API to return:
```
Bad Request: can't parse entities: Can't find end of the entity starting at byte offset 99
```
The message was silently dropped (logged as `Send error` but no fallback).

**Fix applied:** `r[0].replace('_', ' ')` before inserting status labels into the Markdown string:
```python
# Before (broken):
stats = '\n'.join([f"  • {r[0]}: {r[1]}" for r in rows])

# After (fixed):
stats = '\n'.join([f"  • {r[0].replace('_', ' ')}: {r[1]}" for r in rows])
```
**File:** `/opt/openclaw/client_telegram_polling.py` line 157

**Lesson:** Any DB field value used inside a Markdown Telegram message must have `_` escaped or replaced. Use `parse_mode=None` (plain text) when values are dynamic and uncontrolled.

---

### [2026-04-10] Wrong bot responding to @OpenclawHahnbot messages

**Symptom:** Photo sent to `@OpenclawHahnbot` was handled by a different bot (`@OpenClawAssistantbinhtest_bot`).

**Root cause:** Two separate polling services were running simultaneously:
- `openclaw-client-polling.service` — `/opt/openclaw/client_telegram_polling.py` → correct bot `@OpenclawHahnbot`
- `openclaw-polling.service` — `/opt/openclaw/telegram_polling_v4.py` → dev bot `@OpenClawAssistantbinhtest_bot`

When `openclaw-polling.service` was restarted with `TELEGRAM_BOT_TOKEN` pointing to `@OpenclawHahnbot`, both services were temporarily polling the same bot → Telegram delivered each update to only one of them non-deterministically.

**Fix applied:** Stopped and disabled `openclaw-polling.service`. Only `openclaw-client-polling.service` now handles `@OpenclawHahnbot`.

**Active service:** `openclaw-client-polling.service` (enabled, auto-restart)
**Disabled service:** `openclaw-polling.service` (inactive, disabled)

---

### [2026-04-10] WF2 Claude Vision OCR always returns `no_iban`

**Symptom:** All invoices flagged as `fraud_status: no_iban` even with real invoice photos containing a valid German IBAN.

**Root cause:** WF2 used an HTTP Request node with n8n expression `{{ $json.base64_data }}` inside a raw JSON body string (`specifyBody: "json"`). n8n does not evaluate expressions inside manually-typed JSON strings in this node mode — the base64 image data was never sent to Claude.

**Fix applied:** Replaced the HTTP Request node with a **Code node** using `this.helpers.httpRequest()` (JavaScript), which allows building the request body dynamically with full access to input data — identical pattern to the working OCR Demo Client workflow.

**File:** WF2 node `Claude Vision OCR` — type changed from `n8n-nodes-base.httpRequest` → `n8n-nodes-base.code`

---

*Phase 2 – Email Intake + Claude OCR Pipeline – Ready for Testing* 🚀
