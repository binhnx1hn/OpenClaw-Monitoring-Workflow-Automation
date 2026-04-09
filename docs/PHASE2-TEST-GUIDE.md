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

```bash
curl -X POST http://213.160.77.197:5678/webhook/invoice-process \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "invoice_de_iban.pdf",
    "minio_path": "invoices/2026-04-09/invoice_de_iban.pdf",
    "source": "manual_test",
    "email_from": "lieferant@firma.de",
    "email_subject": "Rechnung 2026-04",
    "mime_type": "application/pdf",
    "base64_data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
  }'
```

> Note: `base64_data` là ảnh 1x1 pixel - Claude sẽ không đọc được IBAN → sẽ trả về `no_iban`. Để test **approved** thật sự cần gửi ảnh invoice thật có IBAN bắt đầu bằng `DE`.

---

### Test 1C: Invoice với IBAN nước ngoài (→ suspicious)

```bash
curl -X POST http://213.160.77.197:5678/webhook/invoice-process \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "suspicious_invoice.pdf",
    "minio_path": "invoices/2026-04-09/suspicious_invoice.pdf",
    "source": "manual_test",
    "email_from": "unknown@offshore.io",
    "email_subject": "Payment Required",
    "mime_type": "image/jpeg",
    "base64_data": ""
  }'
```

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

## Thông tin kết nối

| Service | URL | Login |
|---|---|---|
| n8n Dashboard | http://213.160.77.197:5678 | admin@openclaw.io / OpenClaw2024! |
| MinIO Console | http://213.160.77.197:9001 | minioadmin / MinioPass2024! |
| Telegram Bot | @OpenClawAssistantbinhtest_bot | — |
| Email Inbox | rechnung@hahn-fleisch.de | (IMAP: mail.hahn-fleisch.de:993) |

---

*Phase 2 – Email Intake + Claude OCR Pipeline – Ready for Testing* 🚀
