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

## Phase 1: Infrastructure & Docker Setup

### Step 1: System Update ✅ SSH Connected
```bash
apt update && apt upgrade -y
apt install -y curl wget git nano ufw
```

### Step 2: Install Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
docker --version
```

### Step 3: Install Docker Compose Plugin
```bash
apt install docker-compose-plugin -y
docker compose version
```

### Step 4: Configure Firewall
```bash
ufw allow 22/tcp      # SSH
ufw allow 80/tcp      # HTTP
ufw allow 443/tcp     # HTTPS
ufw allow 5678/tcp    # n8n (OpenClaw)
ufw enable
ufw status
```

### Step 5: Create Directory Structure
```bash
mkdir -p /opt/openclaw/{n8n,postgres,minio,nginx}
cd /opt/openclaw
```

### Step 6: Create docker-compose.yml
```bash
cat > /opt/openclaw/docker-compose.yml << 'EOF'
version: '3.8'

services:
  # n8n - OpenClaw Workflow Engine
  n8n:
    image: n8nio/n8n:latest
    container_name: openclaw_n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=OpenClaw2024!
      - WEBHOOK_URL=http://213.160.77.197:5678/
      - GENERIC_TIMEZONE=Europe/Berlin
      - TZ=Europe/Berlin
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=n8n
      - DB_POSTGRESDB_PASSWORD=n8npassword123!
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      - postgres
    networks:
      - openclaw_net

  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: openclaw_postgres
    restart: always
    environment:
      - POSTGRES_USER=n8n
      - POSTGRES_PASSWORD=n8npassword123!
      - POSTGRES_DB=n8n
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - openclaw_net

  # MinIO - S3 Storage for documents/invoices
  minio:
    image: minio/minio:latest
    container_name: openclaw_minio
    restart: always
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=MinioPass2024!
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    networks:
      - openclaw_net

volumes:
  n8n_data:
  postgres_data:
  minio_data:

networks:
  openclaw_net:
    driver: bridge
EOF
```

### Step 7: Start All Services
```bash
cd /opt/openclaw
docker compose up -d
docker compose ps
docker compose logs n8n --tail=50
```

### Step 8: Verify Services Running
```bash
# Check n8n
curl -I http://localhost:5678
# Expected: HTTP/1.1 200 OK or 401

# Check MinIO
curl -I http://localhost:9001
# Expected: HTTP/1.1 200 OK
```

---

## Phase 2: Access URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| n8n Dashboard | http://213.160.77.197:5678 | admin / OpenClaw2024! |
| MinIO Console | http://213.160.77.197:9001 | minioadmin / MinioPass2024! |

---

## Phase 3: Telegram Bot Integration

### Prerequisites from Client
- [ ] Telegram Bot Token (create via @BotFather)
- [ ] Telegram Chat ID or Group ID

### Setup Steps in n8n
1. Login to n8n dashboard: http://213.160.77.197:5678
2. Go to **Credentials** → Add New → **Telegram**
3. Enter Bot Token
4. Create workflow: **Telegram Trigger** → Process → **Telegram Send Message**
5. Test: Send message to bot → n8n receives and responds

---

## Phase 4: OCR Demo (Invoice Processing)

### Requirements from Client
- [ ] Sample invoices (PDF or images)
- [ ] Claude API key (for OpenClaude vision extraction)

### n8n Workflow Design
```
Email Trigger / Webhook
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

## Phase 5: Full Project Roadmap

### Milestone 1 - Phase 1 (€250) ✅ In Progress
- [x] Server provisioned
- [ ] Docker + n8n + PostgreSQL + MinIO running
- [ ] Telegram bot connected
- [ ] OCR demo: invoice → structured data

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
