#!/usr/bin/env python3
"""
OpenClaw Telegram Polling v4
- Handles ACCEPT_{id} / REJECT_{id} invoice review commands
- Direct PostgreSQL update (no n8n dependency for invoice review)
- Forwards all other messages to n8n webhook
"""
import os
import re
import requests
import time
import logging
import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/opt/openclaw/polling.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8787727906:AAEZWhJqmV53IR563jSoxJZTlc_4cM3Nx1M")
N8N_WEBHOOK = 'http://localhost:5678/webhook/openclaw-telegram'
TELEGRAM_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
CHAT_ID_FILE = '/opt/openclaw/last_chat_id.txt'

# PostgreSQL connection (via socat forward: host->docker)
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'dbname': 'n8n',
    'user': 'n8n',
    'password': 'n8npassword123!'
}

last_update_id = 0


def get_db_connection():
    """Get PostgreSQL connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f'DB connection error: {e}')
        return None


def send_telegram_message(chat_id, text, parse_mode=None):
    """Send message via Telegram API"""
    try:
        payload = {'chat_id': chat_id, 'text': text}
        if parse_mode:
            payload['parse_mode'] = parse_mode
        resp = requests.post(
            f'{TELEGRAM_API}/sendMessage',
            json=payload,
            timeout=10
        )
        result = resp.json()
        if result.get('ok'):
            logger.info(f'Sent reply to {chat_id}: {text[:80]}')
            return True
        else:
            logger.error(f'Telegram sendMessage error: {result}')
    except Exception as e:
        logger.error(f'send_telegram_message error: {e}')
    return False


def handle_accept_invoice(invoice_id, chat_id):
    """Accept invoice: UPDATE status=approved in DB"""
    conn = get_db_connection()
    if not conn:
        return send_telegram_message(chat_id, '❌ Database connection error. Please try again.')

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """UPDATE invoices 
                   SET status='approved', fraud_status='approved', updated_at=NOW() 
                   WHERE id=%s 
                   RETURNING id, vendor_name, invoice_number, total_amount, currency""",
                (invoice_id,)
            )
            row = cur.fetchone()
            conn.commit()

            if row:
                msg = (
                    f"✅ Invoice #{row['id']} accepted and queued for processing\n\n"
                    f"Vendor: {row['vendor_name'] or 'N/A'}\n"
                    f"Invoice#: {row['invoice_number'] or 'N/A'}\n"
                    f"Amount: {row['total_amount'] or 0} {row['currency'] or 'EUR'}\n\n"
                    f"Status updated to: approved ✓"
                )
                logger.info(f'Invoice {invoice_id} ACCEPTED by user')
                send_telegram_message(chat_id, msg)
            else:
                send_telegram_message(chat_id, f'⚠️ Invoice #{invoice_id} not found in database.')
    except Exception as e:
        conn.rollback()
        logger.error(f'handle_accept_invoice error: {e}')
        send_telegram_message(chat_id, f'❌ Error accepting invoice #{invoice_id}: {str(e)[:100]}')
    finally:
        conn.close()


def handle_reject_invoice(invoice_id, chat_id):
    """Reject invoice: UPDATE status=spam in DB"""
    conn = get_db_connection()
    if not conn:
        return send_telegram_message(chat_id, '❌ Database connection error. Please try again.')

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """UPDATE invoices 
                   SET status='spam', fraud_status='rejected', updated_at=NOW() 
                   WHERE id=%s 
                   RETURNING id, vendor_name, invoice_number""",
                (invoice_id,)
            )
            row = cur.fetchone()
            conn.commit()

            if row:
                msg = (
                    f"❌ Invoice #{row['id']} rejected and marked as spam\n\n"
                    f"Vendor: {row['vendor_name'] or 'N/A'}\n"
                    f"Invoice#: {row['invoice_number'] or 'N/A'}\n\n"
                    f"Status updated to: spam ✗"
                )
                logger.info(f'Invoice {invoice_id} REJECTED by user')
                send_telegram_message(chat_id, msg)
            else:
                send_telegram_message(chat_id, f'⚠️ Invoice #{invoice_id} not found in database.')
    except Exception as e:
        conn.rollback()
        logger.error(f'handle_reject_invoice error: {e}')
        send_telegram_message(chat_id, f'❌ Error rejecting invoice #{invoice_id}: {str(e)[:100]}')
    finally:
        conn.close()


def process_command(chat_id, text, first_name):
    """Process standard bot commands, return reply text or None"""
    text = text.strip()
    first_name = first_name or 'there'

    # Check ACCEPT_/REJECT_ first (priority)
    accept_match = re.match(r'^ACCEPT_(\d+)$', text, re.IGNORECASE)
    reject_match = re.match(r'^REJECT_(\d+)$', text, re.IGNORECASE)

    if accept_match:
        invoice_id = int(accept_match.group(1))
        logger.info(f'ACCEPT command for invoice #{invoice_id} from chat {chat_id}')
        handle_accept_invoice(invoice_id, chat_id)
        return None  # Already sent via handle_accept_invoice

    if reject_match:
        invoice_id = int(reject_match.group(1))
        logger.info(f'REJECT command for invoice #{invoice_id} from chat {chat_id}')
        handle_reject_invoice(invoice_id, chat_id)
        return None  # Already sent via handle_reject_invoice

    # Standard commands
    if text == '/start':
        return (
            f"👋 Hello {first_name}!\n\n"
            f"I am OpenClaw Invoice Bot.\n\n"
            f"📋 Commands:\n"
            f"/status - System status\n"
            f"/help - Help & commands\n\n"
            f"📨 Invoice Review:\n"
            f"ACCEPT_{{id}} - Accept flagged invoice\n"
            f"REJECT_{{id}} - Reject as spam"
        )

    elif text == '/status':
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        # Quick DB stats
        try:
            conn = get_db_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT status, COUNT(*) FROM invoices GROUP BY status")
                    rows = cur.fetchall()
                    conn.close()
                    stats = '\n'.join([f"  {r[0]}: {r[1]}" for r in rows]) or '  No invoices yet'
            else:
                stats = '  DB unavailable'
        except Exception:
            stats = '  DB error'

        return (
            f"🟢 OpenClaw System Status\n\n"
            f"Bot: Online ✓\n"
            f"n8n: Running ✓\n"
            f"Time: {now}\n\n"
            f"📊 Invoice Stats:\n{stats}"
        )

    elif text == '/help':
        return (
            f"📖 OpenClaw Bot Help\n\n"
            f"Commands:\n"
            f"/start - Welcome message\n"
            f"/status - System & invoice stats\n"
            f"/help - This help\n\n"
            f"Invoice Review:\n"
            f"ACCEPT_123 - Accept invoice #123\n"
            f"REJECT_123 - Reject invoice #123 as spam\n\n"
            f"The bot automatically processes:\n"
            f"• Email invoices (every 5 min)\n"
            f"• PDF/image attachments via OCR\n"
            f"• IBAN fraud detection"
        )

    elif text.startswith('/'):
        return f"Command '{text}' is not supported.\nUse /help to see available commands."

    elif len(text) > 0:
        # Check if it looks like an ACCEPT/REJECT but malformed
        if re.match(r'^(ACCEPT|REJECT)', text, re.IGNORECASE):
            return (
                f"⚠️ Invalid format: '{text}'\n\n"
                f"Correct format:\n"
                f"ACCEPT_123\n"
                f"REJECT_123"
            )
        # Unknown text
        return f"❓ Unknown command.\nUse /help for available commands."

    return None


def forward_to_n8n(update):
    """Forward update to n8n webhook"""
    try:
        resp = requests.post(
            N8N_WEBHOOK,
            json={'body': update, 'headers': {}, 'query': {}},
            timeout=10
        )
        logger.info(f'n8n forward: {resp.status_code} - {resp.text[:200]}')
        return resp.status_code == 200
    except Exception as e:
        logger.error(f'n8n forward error: {e}')
    return False


def get_updates(offset=0):
    """Get Telegram updates with long polling"""
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


def main():
    global last_update_id
    logger.info('OpenClaw Telegram Polling v4 (ACCEPT/REJECT support) started...')

    while True:
        try:
            updates = get_updates(offset=last_update_id + 1)

            for update in updates:
                update_id = update.get('update_id', 0)
                message = update.get('message', {})
                chat = message.get('chat', {})
                chat_id = chat.get('id')
                username = chat.get('username', 'unknown')
                first_name = message.get('from', {}).get('first_name', 'there')
                text = message.get('text', '')

                logger.info(
                    f'UPDATE: update_id={update_id} chat_id={chat_id} '
                    f'username=@{username} text={text!r}'
                )

                # Save last chat_id
                try:
                    with open(CHAT_ID_FILE, 'w') as f:
                        f.write(str(chat_id))
                except Exception as e:
                    logger.error(f'Save chat_id error: {e}')

                # Process text commands (includes ACCEPT_/REJECT_)
                if text and chat_id:
                    reply = process_command(chat_id, text, first_name)
                    if reply:
                        send_telegram_message(chat_id, reply)
                    # ACCEPT/REJECT are handled inside process_command directly

                # Photos/documents -> forward to n8n for OCR
                elif message.get('photo') or message.get('document'):
                    logger.info('Media message received, forwarding to n8n for OCR...')
                    forward_to_n8n(update)

                last_update_id = max(last_update_id, update_id)

        except KeyboardInterrupt:
            logger.info('Polling stopped by user')
            break
        except Exception as e:
            logger.error(f'Main loop error: {e}')
            time.sleep(5)

        time.sleep(1)


if __name__ == '__main__':
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN environment variable is required")
    main()
