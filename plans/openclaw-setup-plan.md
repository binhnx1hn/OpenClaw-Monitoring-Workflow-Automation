# OpenClaw (n8n) Server Setup Plan

## Server Information
| Field | Value |
|-------|-------|
| IP | 213.160.77.197 |
| OS | Ubuntu 22.04.5 LTS |
| User | root |
| Password | Catherine110! |
| Specs | 2 CPU, 4GB RAM, 80GB SSD |
| Blocked Port | 25 (use 587/465 for email) |

---

## ✅ Deployment Status (2026-04-06)

### Running Services
| Container | Image | Status | Ports |
|-----------|-------|--------|-------|
| `openclaw_n8n` | `n8nio/n8n:latest` (v2.14.2) | ✅ Up | `0.0.0.0:5678->5678` |
| `openclaw_postgres` | `postgres:15-alpine` | ✅ Up | `5432/tcp` (internal) |
| `openclaw_minio` | `minio/minio:latest` | ✅ Up | `0.0.0.0:9000-9001->9000-9001` |

### Access URLs
| Service | URL | Credentials |
|---------|-----|-------------|
| n8n Dashboard | https://213.160.77.197 | admin@openclaw.io / OpenClaw2024! |
| n8n Direct | http://213.160.77.197:5678 | admin / OpenClaw2024! |
| MinIO Console | http://213.160.77.197:9001 | minioadmin / MinioPass2024! |

### Telegram Bot
| Field | Value |
|-------|-------|
| Bot Name | OpenClaw Assistant Test |
| Username | @OpenClawAssistantbinhtest_bot |
| URL | t.me/OpenClawAssistantbinhtest_bot |
| Token | 8787727906:AAEZWhJqmV53IR563jSoxJZTlc_4cM3Nx1M |
| Webhook | https://213.160.77.197/webhook/openclaw-telegram |
| n8n Credential ID | 8rvHrkiGjHElEu4f |
| n8n Workflow ID | Ay4PiqO6lQVp8iy1 |
| Status | ✅ Active |

### Supported Bot Commands
- `/start` - Welcome message
- `/status` - Check system status
- `/help` - List available commands

### Technical Notes
- Nginx reverse proxy với self-signed SSL cert cho HTTPS webhook
- UFW Firewall: ports 22, 80, 443, 5678, 9000, 9001 open
- Generic Webhook node dùng thay TelegramTrigger (tránh secret token validation issue)
- Timezone: Europe/Berlin

---

## Phase 1: Infrastructure & Docker Setup ✅ COMPLETED

### Step 1: System Update ✅
```bash
apt update && apt upgrade -y
apt install -y curl wget git nano ufw
```

### Step 2: Install Docker ✅
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
docker --version
```

### Step 3: Install Docker Compose Plugin ✅
```bash
apt install docker-compose-plugin -y
docker compose version
```

### Step 4: Configure Firewall ✅
```bash
ufw allow 22/tcp      # SSH
ufw allow 80/tcp      # HTTP
ufw allow 443/tcp     # HTTPS
ufw allow 5678/tcp    # n8n (OpenClaw)
ufw allow 9000/tcp    # MinIO API
ufw allow 9001/tcp    # MinIO Console
ufw --force enable
ufw status
```

### Step 5: Create Directory Structure ✅
```bash
mkdir -p /opt/openclaw/{n8n,postgres,minio,nginx}
cd /opt/openclaw
```

### Step 6: docker-compose.yml ✅
Location: `/opt/openclaw/docker-compose.yml`

### Step 7: Start All Services ✅
```bash
cd /opt/openclaw
docker compose up -d
docker compose ps
docker compose logs n8n --tail=50
```

---

## Phase 2: Telegram Integration ✅ COMPLETED

### Telegram Credential (n8n)
- **Credential ID**: `8rvHrkiGjHElEu4f`
- **Name**: OpenClaw Telegram Bot
- **Type**: telegramApi
- Created via n8n API: `POST /api/v1/credentials`

### Webhook Workflow
- **Workflow ID**: `Ay4PiqO6lQVp8iy1`
- **Webhook URL**: `https://213.160.77.197/webhook/openclaw-telegram`
- **Flow**: Webhook Trigger → Process Message (Code) → Send Reply (Telegram)
- **Status**: ✅ Active

### Telegram Webhook Registration
```bash
curl -X POST "https://api.telegram.org/bot8787727906:AAEZWhJqmV53IR563jSoxJZTlc_4cM3Nx1M/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://213.160.77.197/webhook/openclaw-telegram"}'
```

---

## Phase 3: OCR Demo (Invoice Processing) 🔄 IN PROGRESS

### Requirements
- [ ] Sample invoices (PDF or images) from client
- [ ] Claude API key (for vision-based extraction)

### n8n Workflow Design
```
Webhook / Email Trigger
    ↓
Download Attachment (PDF/Image)
    ↓
Store in MinIO
    ↓
Send to Claude Vision API
    ↓
Extract: Vendor, Invoice#, Date, VAT, Amount
    ↓
Save to PostgreSQL
    ↓
Send Telegram notification with extracted data
```

---

## Phase 4: Full Project Roadmap

### Milestone 1 - Phase 1 (€250) ✅ COMPLETED
- [x] Server provisioned
- [x] Docker + n8n + PostgreSQL + MinIO running
- [x] Telegram bot connected and active
- [ ] OCR demo: invoice → structured data (in progress)

### Milestone 2 - Email Intake + OCR Pipeline
- [ ] IMAP email integration (port 587/465)
- [ ] Auto-download invoice attachments
- [ ] Full OCR extraction pipeline
- [ ] Data stored in PostgreSQL

### Milestone 3 - Bank Integration
- [ ] PSD2/FinTS API integration
- [ ] Automated bank statement retrieval
- [ ] Invoice ↔ payment matching
- [ ] Mismatch flagging

### Milestone 4 - Accounting Logic
- [ ] SKR03 account assignment
- [ ] Duplicate detection
- [ ] VAT/tax data preparation
- [ ] Self-learning from historical data

### Milestone 5 - Automation Workflows
- [ ] Payment reminders (3 days before/after due)
- [ ] Dunning process
- [ ] Weekly reports (payment overview, outstanding invoices)
- [ ] Monthly tax reports

### Milestone 6 - React Dashboard
- [ ] Document processing status
- [ ] Payment matching view
- [ ] Exception handling UI
- [ ] CSV/Excel/PDF export

### Milestone 7 - Testing & Deployment
- [ ] End-to-end testing
- [ ] Multi-tenant setup documentation
- [ ] Final handover & training

---

## Important Notes

- **Port 25 blocked** → Use SMTP port **587 (STARTTLS)** or **465 (SSL)** for email
- **SSH access**: `ssh root@213.160.77.197` (password: Catherine110!)
- **Change root password** after initial setup complete
- **Enable backup** in hosting panel for production use
- **SSL**: Self-signed cert currently, upgrade to Let's Encrypt for production
- **Clone cost**: €50 per additional server deployment
