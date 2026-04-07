# OpenClaw – Full Deployment Guide

> **Version**: 1.0  
> **Last Updated**: 2026-04-07  
> **Maintained by**: OpenClaw Team

---

## Overview

This guide provides step-by-step instructions to deploy the **OpenClaw Monitoring & Workflow Automation** system on a fresh Ubuntu server, or to clone the entire system to a new server.

**System Components:**
| Component | Version | Purpose |
|-----------|---------|---------|
| n8n | v2.14.2 | Workflow automation engine |
| PostgreSQL | 15 | n8n database backend |
| MinIO | latest | Object storage for invoices |
| Telegram Polling | v3 | Bot polling service (systemd) |
| Docker Compose | v2+ | Container orchestration |

**Two deployment scenarios covered:**
1. **Fresh Deploy** – Brand new server, install everything from scratch
2. **Clone to New Server** – Migrate existing system to a new VPS

---

## Prerequisites

### Hardware Requirements
| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| SSD | 20 GB | 80 GB |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### Access Requirements
- Root or sudo access to the server
- SSH access to the server
- A domain name (optional, required for HTTPS/SSL)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Variables Used Throughout This Guide
> Replace these values with your actual configuration before running commands.

```bash
# Set these variables in your shell session before running any commands
SERVER_IP="213.160.77.197"          # Your server's public IP address
BOT_TOKEN="YOUR_BOT_TOKEN_HERE"      # Telegram Bot Token from @BotFather
DOMAIN="your-domain.com"             # Optional: your domain name
```

---

## Part 1: Server Setup

### 1.1 System Update

Connect to your server via SSH and update the system:

```bash
ssh root@SERVER_IP

# Update package lists and upgrade installed packages
apt update && apt upgrade -y

# Install essential tools
apt install -y curl wget git unzip software-properties-common \
    apt-transport-https ca-certificates gnupg lsb-release ufw \
    python3 python3-pip htop nano
```

### 1.2 Install Docker + Docker Compose

```bash
# Remove old Docker versions if any
apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable and start Docker
systemctl enable docker
systemctl start docker

# Verify installation
docker --version
docker compose version
```

**Expected output:**
```
Docker version 24.x.x, build xxxxxxx
Docker Compose version v2.x.x
```

### 1.3 Configure Firewall (UFW)

```bash
# Reset UFW to defaults
ufw --force reset

# Set default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (critical - do this first!)
ufw allow 22/tcp comment 'SSH'

# Allow n8n web interface
ufw allow 5678/tcp comment 'n8n Web UI'

# Allow MinIO API and Console
ufw allow 9000/tcp comment 'MinIO API'
ufw allow 9001/tcp comment 'MinIO Console'

# Allow HTTP/HTTPS (optional, for Nginx reverse proxy)
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Enable firewall
ufw --force enable

# Verify status
ufw status verbose
```

---

## Part 2: Deploy Core Services

### 2.1 Create Directory Structure

```bash
# Create main OpenClaw directory and subdirectories
mkdir -p /opt/openclaw/{n8n,postgres,minio,nginx,scripts}

# Create data directories for persistent storage
mkdir -p /opt/openclaw/n8n/data
mkdir -p /opt/openclaw/postgres/data
mkdir -p /opt/openclaw/minio/data

# Set proper permissions
chmod -R 755 /opt/openclaw
chown -R root:root /opt/openclaw

# Verify structure
ls -la /opt/openclaw/
```

### 2.2 Create docker-compose.yml

Create the main Docker Compose configuration file:

```bash
cat > /opt/openclaw/docker-compose.yml << 'EOF'
version: "3.8"

# ─────────────────────────────────────────────
#  OpenClaw – Core Services Docker Compose
#  Components: n8n + PostgreSQL 15 + MinIO
# ─────────────────────────────────────────────

services:

  # ── PostgreSQL Database (n8n backend) ──────
  postgres:
    image: postgres:15-alpine
    container_name: openclaw-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: n8n
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD: n8n_password_2024
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - ./postgres/data:/var/lib/postgresql/data
    networks:
      - openclaw-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U n8n -d n8n"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── n8n Workflow Automation ─────────────────
  n8n:
    image: n8nio/n8n:2.14.2
    container_name: openclaw-n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      # Database configuration
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: n8n
      DB_POSTGRESDB_USER: n8n
      DB_POSTGRESDB_PASSWORD: n8n_password_2024

      # n8n basic settings
      N8N_HOST: 0.0.0.0
      N8N_PORT: 5678
      N8N_PROTOCOL: http
      WEBHOOK_URL: http://SERVER_IP:5678/

      # Security settings
      # NOTE: Set to false to allow HTTP access (no HTTPS required)
      N8N_SECURE_COOKIE: "false"

      # Authentication
      N8N_BASIC_AUTH_ACTIVE: "false"

      # Execution settings
      EXECUTIONS_DATA_SAVE_ON_ERROR: all
      EXECUTIONS_DATA_SAVE_ON_SUCCESS: none
      EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS: "true"
      EXECUTIONS_DATA_PRUNE: "true"
      EXECUTIONS_DATA_MAX_AGE: 168

      # Timezone
      GENERIC_TIMEZONE: UTC
      TZ: UTC

      # Log level
      N8N_LOG_LEVEL: info

      # Disable telemetry
      N8N_DIAGNOSTICS_ENABLED: "false"
      N8N_VERSION_NOTIFICATIONS_ENABLED: "false"
    volumes:
      - ./n8n/data:/home/node/.n8n
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - openclaw-network

  # ── MinIO Object Storage ────────────────────
  minio:
    image: minio/minio:latest
    container_name: openclaw-minio
    restart: unless-stopped
    ports:
      - "9000:9000"   # API
      - "9001:9001"   # Web Console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin123
    volumes:
      - ./minio/data:/data
    command: server /data --console-address ":9001"
    networks:
      - openclaw-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

# ── Networks ────────────────────────────────
networks:
  openclaw-network:
    driver: bridge
    name: openclaw-network
EOF
```

> ⚠️ **Important**: Replace `SERVER_IP` in `WEBHOOK_URL` with your actual server IP before starting services.

```bash
# Replace SERVER_IP placeholder with actual IP
sed -i "s/SERVER_IP/$SERVER_IP/g" /opt/openclaw/docker-compose.yml

# Verify the replacement
grep "WEBHOOK_URL" /opt/openclaw/docker-compose.yml
```

### 2.3 Start Services

```bash
# Navigate to OpenClaw directory
cd /opt/openclaw

# Pull all images first (optional but recommended)
docker compose pull

# Start all services in background
docker compose up -d

# Monitor startup progress
docker compose logs -f --tail=50
```

Press `Ctrl+C` to exit the log view once all services are ready.

### 2.4 Verify Services Running

```bash
cd /opt/openclaw

# Check container status
docker compose ps

# Expected output:
# NAME                  IMAGE                     STATUS              PORTS
# openclaw-n8n          n8nio/n8n:2.14.2          Up (healthy)        0.0.0.0:5678->5678/tcp
# openclaw-postgres     postgres:15-alpine        Up (healthy)        5432/tcp
# openclaw-minio        minio/minio:latest        Up (healthy)        0.0.0.0:9000->9000/tcp, 0.0.0.0:9001->9001/tcp

# Test n8n is responding
curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/healthz
# Expected: 200

# Test MinIO is responding
curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/minio/health/live
# Expected: 200
```

---

## Part 3: n8n Initial Setup

### 3.1 First Login & Create Owner Account

1. Open browser and navigate to: `http://SERVER_IP:5678`
2. You will see the n8n setup screen
3. Fill in the owner account details:
   - **First Name**: Admin
   - **Last Name**: OpenClaw
   - **Email**: `admin@openclaw.io`
   - **Password**: `OpenClaw2024!`
4. Click **"Get started"**

#### Skip Onboarding Survey via API

```bash
# Get auth cookie by logging in via API
curl -s -c /tmp/n8n_cookies.txt -X POST http://localhost:5678/rest/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@openclaw.io","password":"OpenClaw2024!"}' | python3 -m json.tool

# Skip the survey
curl -s -b /tmp/n8n_cookies.txt -X POST http://localhost:5678/rest/owner/setup \
    -H "Content-Type: application/json" \
    -d '{"skipSurvey": true}' 2>/dev/null || true

echo "Setup complete"
```

### 3.2 Create Telegram Credential

1. In n8n, go to **Settings → Credentials**
2. Click **"Add Credential"**
3. Search for **"Telegram"** and select `Telegram API`
4. Fill in:
   - **Credential Name**: `OpenClaw Telegram Bot`
   - **Access Token**: `YOUR_BOT_TOKEN` (from @BotFather)
5. Click **"Save"**

#### Create Credential via API (automated)

```bash
# Login and save session cookie
curl -s -c /tmp/n8n_cookies.txt -X POST http://localhost:5678/rest/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@openclaw.io","password":"OpenClaw2024!"}'

# Create Telegram credential
curl -s -b /tmp/n8n_cookies.txt -X POST http://localhost:5678/rest/credentials \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"OpenClaw Telegram Bot\",
        \"type\": \"telegramApi\",
        \"data\": {
            \"accessToken\": \"$BOT_TOKEN\"
        }
    }" | python3 -m json.tool
```

### 3.3 Import Workflows

#### Import OCR Workflow

```bash
# Login first
curl -s -c /tmp/n8n_cookies.txt -X POST http://localhost:5678/rest/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@openclaw.io","password":"OpenClaw2024!"}'

# Import OCR workflow from file (if you have the JSON)
curl -s -b /tmp/n8n_cookies.txt -X POST http://localhost:5678/rest/workflows \
    -H "Content-Type: application/json" \
    -d @/opt/openclaw/workflows/ocr-workflow.json | python3 -m json.tool
```

#### Import Telegram Handler Workflow

```bash
curl -s -b /tmp/n8n_cookies.txt -X POST http://localhost:5678/rest/workflows \
    -H "Content-Type: application/json" \
    -d @/opt/openclaw/workflows/telegram-workflow.json | python3 -m json.tool
```

#### Activate Workflows

```bash
# List all workflows to get their IDs
curl -s -b /tmp/n8n_cookies.txt http://localhost:5678/rest/workflows | \
    python3 -c "import sys,json; [print(f'ID: {w[\"id\"]} | Name: {w[\"name\"]}') for w in json.load(sys.stdin)['data']]"

# Activate a workflow by ID (replace WORKFLOW_ID)
curl -s -b /tmp/n8n_cookies.txt -X PATCH http://localhost:5678/rest/workflows/WORKFLOW_ID \
    -H "Content-Type: application/json" \
    -d '{"active": true}'
```

**Known Workflow IDs (current deployment):**
- Telegram Handler: `lfIu4XjmucM26mkv`
- OCR Demo: `AT1uQiJBsh7S2cyb`

---

## Part 4: Telegram Bot Setup

### 4.1 Create Telegram Bot (if not already created)

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts:
   - Bot name: e.g., `OpenClaw Bot`
   - Bot username: e.g., `openclaw_bot` (must end in `bot`)
4. Copy the **API Token** (format: `1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ`)
5. Save this token – you'll need it throughout this guide

### 4.2 Install Python Dependencies

```bash
# Install required Python packages
pip3 install requests

# Verify installation
python3 -c "import requests; print('requests version:', requests.__version__)"
```

### 4.3 Create Polling Script

```bash
cat > /opt/openclaw/telegram_polling.py << 'PYEOF'
#!/usr/bin/env python3
"""
OpenClaw Telegram Polling Service v3
Polls Telegram Bot API and forwards updates to n8n webhook.
"""
import requests, time, logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('/opt/openclaw/polling.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
BOT_TOKEN = 'YOUR_BOT_TOKEN'                              # Replace with actual token
N8N_WEBHOOK = 'http://localhost:5678/webhook/openclaw-telegram'
TELEGRAM_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
CHAT_ID_FILE = '/opt/openclaw/last_chat_id.txt'
last_update_id = 0


def get_updates(offset=0):
    """Fetch new updates from Telegram API using long polling."""
    try:
        resp = requests.get(
            f'{TELEGRAM_API}/getUpdates',
            params={'offset': offset, 'timeout': 30, 'limit': 10},
            timeout=35
        )
        data = resp.json()
        if data.get('ok'):
            return data.get('result', [])
    except Exception as e:
        logger.error(f'getUpdates error: {e}')
    return []


def send_telegram_message(chat_id, text):
    """Send a text message to a Telegram chat."""
    try:
        resp = requests.post(
            f'{TELEGRAM_API}/sendMessage',
            json={'chat_id': chat_id, 'text': text},
            timeout=10
        )
        result = resp.json()
        if result.get('ok'):
            logger.info(f'SENT reply to {chat_id}: {text[:80]}')
            return True
        else:
            logger.error(f'Telegram sendMessage error: {result}')
    except Exception as e:
        logger.error(f'send_telegram_message error: {e}')
    return False


def process_command(chat_id, text, first_name):
    """Handle known bot commands locally without forwarding to n8n."""
    text = text.strip()
    first_name = first_name or 'there'

    if text == '/start':
        return (
            f"Hello {first_name}!\n\n"
            "I am OpenClaw Bot.\n\n"
            "Commands:\n"
            "/status - system status\n"
            "/help - help"
        )
    elif text == '/status':
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        return (
            f"OpenClaw system OK\n\n"
            f"Bot: Online\n"
            f"n8n: Running\n"
            f"Time: {now}"
        )
    elif text == '/help':
        return (
            "Help:\n"
            "/start - start\n"
            "/status - status\n"
            "/help - help\n\n"
            "Send an invoice image for OCR."
        )
    elif text.startswith('/'):
        return f"Command '{text}' is not supported. Use /help to see available commands."
    elif len(text) > 0:
        return f"You sent: \"{text}\"\nUse /help to see commands."
    return None


def forward_to_n8n(update):
    """Forward a Telegram update to n8n webhook."""
    try:
        resp = requests.post(
            N8N_WEBHOOK,
            json={'body': update, 'headers': {}, 'query': {}},
            timeout=10
        )
        logger.info(f'n8n response: {resp.status_code}')
        return resp.status_code == 200
    except Exception as e:
        logger.error(f'n8n forward error: {e}')
    return False


def main():
    """Main polling loop."""
    global last_update_id
    logger.info('OpenClaw Telegram Polling v3 started...')

    while True:
        updates = get_updates(offset=last_update_id + 1)

        for update in updates:
            update_id = update.get('update_id', 0)
            message = update.get('message', {})
            chat = message.get('chat', {})
            chat_id = chat.get('id')
            first_name = message.get('from', {}).get('first_name', 'there')
            text = message.get('text', '')

            logger.info(f'UPDATE: chat_id={chat_id} text={text!r}')

            # Save last known chat_id for monitoring purposes
            try:
                with open(CHAT_ID_FILE, 'w') as f:
                    f.write(str(chat_id))
            except Exception:
                pass

            if text and chat_id:
                # Try to handle as a bot command first
                reply = process_command(chat_id, text, first_name)
                if reply:
                    send_telegram_message(chat_id, reply)
                else:
                    # Forward non-command text to n8n
                    forward_to_n8n(update)
            elif message.get('photo') or message.get('document'):
                # Forward media messages (invoices, images) to n8n
                forward_to_n8n(update)

            last_update_id = max(last_update_id, update_id)

        time.sleep(1)


if __name__ == '__main__':
    main()
PYEOF
```

#### Replace Bot Token in Script

```bash
# Replace placeholder with actual bot token
sed -i "s/YOUR_BOT_TOKEN/$BOT_TOKEN/g" /opt/openclaw/telegram_polling.py

# Make executable
chmod +x /opt/openclaw/telegram_polling.py

# Verify token was set correctly
grep "BOT_TOKEN" /opt/openclaw/telegram_polling.py
```

#### Test Script Manually

```bash
# Run manually to test (press Ctrl+C to stop)
python3 /opt/openclaw/telegram_polling.py
```

### 4.4 Create systemd Service

```bash
cat > /etc/systemd/system/openclaw-polling.service << 'EOF'
[Unit]
Description=OpenClaw Telegram Polling Service
After=network.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/openclaw
ExecStart=/usr/bin/python3 /opt/openclaw/telegram_polling.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

### 4.5 Enable & Start Service

```bash
# Reload systemd daemon to pick up new service file
systemctl daemon-reload

# Enable service to start on boot
systemctl enable openclaw-polling

# Start the service
systemctl start openclaw-polling

# Check service status
systemctl status openclaw-polling
```

**Expected output:**
```
● openclaw-polling.service - OpenClaw Telegram Polling Service
     Loaded: loaded (/etc/systemd/system/openclaw-polling.service; enabled)
     Active: active (running) since ...
   Main PID: XXXXX (python3)
```

### 4.6 Verify Bot Working

```bash
# View live logs from the polling service
journalctl -u openclaw-polling -f

# Also check the log file
tail -f /opt/openclaw/polling.log
```

Send `/start` to your bot in Telegram. You should see the update logged and receive a response.

---

## Part 5: MinIO Setup

### 5.1 Access MinIO Console

Open browser: `http://SERVER_IP:9001`
- **Username**: `minioadmin`
- **Password**: `minioadmin123`

### 5.2 Create Buckets via Web Console

1. Click **"Create Bucket"**
2. Create bucket: `invoices` (for incoming invoice images)
3. Create bucket: `processed` (for OCR results)

### 5.3 Create Buckets via CLI

```bash
# Install MinIO client (mc)
curl -sO https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
mv mc /usr/local/bin/mc

# Configure mc alias
mc alias set openclaw http://localhost:9000 minioadmin minioadmin123

# Create buckets
mc mb openclaw/invoices
mc mb openclaw/processed

# Set public read policy for processed bucket (optional)
mc anonymous set download openclaw/processed

# Verify buckets
mc ls openclaw
```

### 5.4 Configure n8n MinIO Credential

1. In n8n, go to **Settings → Credentials**
2. Click **"Add Credential"**
3. Search for **"S3"** and select `AWS S3`
4. Fill in:
   - **Credential Name**: `OpenClaw MinIO`
   - **Access Key ID**: `minioadmin`
   - **Secret Access Key**: `minioadmin123`
   - **Region**: `us-east-1`
   - **Custom Endpoint**: `http://openclaw-minio:9000`
   - **Force Path Style**: ✓ Enabled

---

## Part 6: Clone to New Server

> 💡 **Cloning fee**: €50 per migration. Contact the OpenClaw team to arrange.

This section describes how to migrate the entire OpenClaw system from the current server to a new server.

### 6.1 Prerequisites for Clone

- New server provisioned (same or higher specs)
- SSH access to both old and new servers
- New server's IP address (referred to as `NEW_SERVER_IP`)

### 6.2 Backup Volumes from Old Server

Run these commands on the **old server**:

```bash
cd /opt/openclaw

# Stop services to ensure data consistency
docker compose stop

# Create backup archive of all persistent data
tar -czf /tmp/openclaw-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
    /opt/openclaw/n8n/data \
    /opt/openclaw/postgres/data \
    /opt/openclaw/minio/data \
    /opt/openclaw/docker-compose.yml \
    /opt/openclaw/telegram_polling.py \
    /etc/systemd/system/openclaw-polling.service

# Verify backup file
ls -lh /tmp/openclaw-backup-*.tar.gz

# Restart services on old server
docker compose start
```

### 6.3 Transfer to New Server

```bash
# Transfer backup from old server to new server
# Run this on the OLD server (replace NEW_SERVER_IP)
scp /tmp/openclaw-backup-*.tar.gz root@NEW_SERVER_IP:/tmp/

# Verify transfer completed
ssh root@NEW_SERVER_IP "ls -lh /tmp/openclaw-backup-*.tar.gz"
```

### 6.4 Restore on New Server

Run these commands on the **new server**:

```bash
NEW_SERVER_IP="YOUR_NEW_SERVER_IP"  # Set this

# 1. Follow Part 1 (Server Setup) and Part 2.1 (Create Directory Structure) first
# Then restore the backup:

# Extract backup
tar -xzf /tmp/openclaw-backup-*.tar.gz -C /

# Update SERVER_IP in docker-compose.yml
sed -i "s/OLD_SERVER_IP/$NEW_SERVER_IP/g" /opt/openclaw/docker-compose.yml

# Verify the change
grep "WEBHOOK_URL" /opt/openclaw/docker-compose.yml
```

### 6.5 Start Services on New Server

```bash
cd /opt/openclaw

# Start all services
docker compose up -d

# Wait for services to be healthy
sleep 30

# Verify all containers are running
docker compose ps

# Test n8n is accessible
curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/healthz
```

### 6.6 Restore systemd Service

```bash
# Reload systemd with the restored service file
systemctl daemon-reload

# Enable and start polling service
systemctl enable openclaw-polling
systemctl start openclaw-polling

# Verify service is running
systemctl status openclaw-polling
```

### 6.7 Verify Clone Successful

```bash
# Check all services
docker compose -f /opt/openclaw/docker-compose.yml ps

# Test n8n login
curl -s -c /tmp/n8n_cookies.txt -X POST http://localhost:5678/rest/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@openclaw.io","password":"OpenClaw2024!"}' | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print('Login:', 'OK' if d.get('data') else 'FAILED')"

# Check workflows are active
curl -s -b /tmp/n8n_cookies.txt http://localhost:5678/rest/workflows | \
    python3 -c "import sys,json; [print(f'{w[\"name\"]}: {\"Active\" if w[\"active\"] else \"Inactive\"}') for w in json.load(sys.stdin)['data']]"

# Check polling service logs
journalctl -u openclaw-polling --since "5 minutes ago"
```

### 6.8 Post-Clone: Update Telegram Webhook (if applicable)

If you were using Telegram webhooks (not polling), update the webhook URL:

```bash
# Delete old webhook
curl "https://api.telegram.org/bot$BOT_TOKEN/deleteWebhook"

# The polling service handles updates via long polling, no webhook needed
# Just verify the polling service is running
systemctl status openclaw-polling
```

---

## Part 7: Maintenance

### 7.1 Service Status Check

```bash
# Check all Docker containers
docker compose -f /opt/openclaw/docker-compose.yml ps

# Check polling service
systemctl status openclaw-polling

# Check system resources
htop
df -h
free -h
```

### 7.2 View Logs

```bash
# n8n logs
docker logs openclaw-n8n --tail=100 -f

# PostgreSQL logs
docker logs openclaw-postgres --tail=50 -f

# MinIO logs
docker logs openclaw-minio --tail=50 -f

# Polling service logs (systemd journal)
journalctl -u openclaw-polling -f

# Polling service log file
tail -f /opt/openclaw/polling.log

# All OpenClaw Docker logs combined
docker compose -f /opt/openclaw/docker-compose.yml logs -f --tail=50
```

### 7.3 Restart Services

```bash
cd /opt/openclaw

# Restart all Docker services
docker compose restart

# Restart specific service
docker compose restart n8n
docker compose restart postgres
docker compose restart minio

# Restart polling service
systemctl restart openclaw-polling

# Full stop and start
docker compose down && docker compose up -d
```

### 7.4 Update n8n

```bash
cd /opt/openclaw

# Edit docker-compose.yml to change n8n version
# Change: n8nio/n8n:2.14.2  →  n8nio/n8n:NEW_VERSION
nano docker-compose.yml

# Pull new image and recreate container
docker compose pull n8n
docker compose up -d n8n

# Verify new version
docker exec openclaw-n8n n8n --version
```

> ⚠️ **Warning**: Always backup data before updating n8n. Check [n8n changelog](https://docs.n8n.io/release-notes/) for breaking changes.

### 7.5 Backup

#### Automated Daily Backup Script

```bash
cat > /opt/openclaw/scripts/backup.sh << 'BACKUPEOF'
#!/bin/bash
# OpenClaw Daily Backup Script
BACKUP_DIR="/opt/openclaw/backups"
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/openclaw-$DATE.tar.gz"

mkdir -p "$BACKUP_DIR"

# Stop n8n briefly for consistent backup (optional)
# docker compose -f /opt/openclaw/docker-compose.yml stop n8n

# Create backup
tar -czf "$BACKUP_FILE" \
    /opt/openclaw/n8n/data \
    /opt/openclaw/postgres/data \
    /opt/openclaw/minio/data \
    /opt/openclaw/docker-compose.yml \
    /opt/openclaw/telegram_polling.py \
    /etc/systemd/system/openclaw-polling.service

# Restart n8n if stopped
# docker compose -f /opt/openclaw/docker-compose.yml start n8n

# Keep only last 7 backups
ls -t "$BACKUP_DIR"/openclaw-*.tar.gz | tail -n +8 | xargs rm -f 2>/dev/null

echo "Backup completed: $BACKUP_FILE ($(du -h $BACKUP_FILE | cut -f1))"
BACKUPEOF

chmod +x /opt/openclaw/scripts/backup.sh
```

#### Schedule Daily Backup with Cron

```bash
# Add to crontab (runs at 2:00 AM UTC daily)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/openclaw/scripts/backup.sh >> /opt/openclaw/backup.log 2>&1") | crontab -

# Verify cron entry
crontab -l

# Test backup manually
/opt/openclaw/scripts/backup.sh
ls -lh /opt/openclaw/backups/
```

### 7.6 Database Maintenance

```bash
# Connect to PostgreSQL
docker exec -it openclaw-postgres psql -U n8n -d n8n

# Check database size
\l+

# Exit
\q

# PostgreSQL backup only
docker exec openclaw-postgres pg_dump -U n8n n8n > /opt/openclaw/backups/n8n-db-$(date +%Y%m%d).sql
```

---

## Appendix: Quick Reference

### Service URLs

| Service | URL | Notes |
|---------|-----|-------|
| n8n Web UI | `http://SERVER_IP:5678` | Workflow automation interface |
| MinIO Console | `http://SERVER_IP:9001` | Object storage management |
| MinIO API | `http://SERVER_IP:9000` | S3-compatible API endpoint |

### Default Credentials

| Service | Username | Password |
|---------|----------|---------|
| n8n | `admin@openclaw.io` | `OpenClaw2024!` |
| MinIO | `minioadmin` | `minioadmin123` |
| PostgreSQL | `n8n` | `n8n_password_2024` |

> ⚠️ **Security Note**: Change all default passwords in production environments!

### Workflow IDs

| Workflow | ID |
|----------|----|
| Telegram Handler | `lfIu4XjmucM26mkv` |
| OCR Demo | `AT1uQiJBsh7S2cyb` |

### Important File Paths

| File | Path |
|------|------|
| Docker Compose | `/opt/openclaw/docker-compose.yml` |
| Polling Script | `/opt/openclaw/telegram_polling.py` |
| Polling Log | `/opt/openclaw/polling.log` |
| Last Chat ID | `/opt/openclaw/last_chat_id.txt` |
| systemd Service | `/etc/systemd/system/openclaw-polling.service` |
| Backup Script | `/opt/openclaw/scripts/backup.sh` |
| Backups Directory | `/opt/openclaw/backups/` |

### Commonly Used Commands

```bash
# ── Service Management ────────────────────────────────────────────
# Start all services
docker compose -f /opt/openclaw/docker-compose.yml up -d

# Stop all services
docker compose -f /opt/openclaw/docker-compose.yml down

# Restart all services
docker compose -f /opt/openclaw/docker-compose.yml restart

# View all service status
docker compose -f /opt/openclaw/docker-compose.yml ps

# ── Polling Service ───────────────────────────────────────────────
systemctl start openclaw-polling
systemctl stop openclaw-polling
systemctl restart openclaw-polling
systemctl status openclaw-polling

# ── Logs ──────────────────────────────────────────────────────────
docker logs openclaw-n8n -f --tail=100
docker logs openclaw-postgres -f --tail=50
journalctl -u openclaw-polling -f
tail -f /opt/openclaw/polling.log

# ── Quick Health Check ────────────────────────────────────────────
curl -s http://localhost:5678/healthz          # n8n health
curl -s http://localhost:9000/minio/health/live # MinIO health
systemctl is-active openclaw-polling           # Polling status

# ── Backup ────────────────────────────────────────────────────────
/opt/openclaw/scripts/backup.sh
```

### Troubleshooting Quick Reference

| Issue | Command to Diagnose |
|-------|---------------------|
| n8n not starting | `docker logs openclaw-n8n --tail=50` |
| DB connection error | `docker logs openclaw-postgres --tail=50` |
| Bot not responding | `journalctl -u openclaw-polling -f` |
| Webhook not received | `docker logs openclaw-n8n --tail=50 \| grep webhook` |
| Disk full | `df -h && du -sh /opt/openclaw/*` |
| High memory | `free -h && docker stats` |

---

*End of OpenClaw Deployment Guide*

> For support or questions, contact the OpenClaw team.
