#!/usr/bin/env python3
import os
import requests, time, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
    handlers=[logging.FileHandler('/opt/openclaw/polling.log'), logging.StreamHandler()])
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
N8N_WEBHOOK = 'http://localhost:5678/webhook/openclaw-telegram'
TELEGRAM_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
CHAT_ID_FILE = '/opt/openclaw/last_chat_id.txt'
last_update_id = 0

def get_updates(offset=0):
    try:
        resp = requests.get(f'{TELEGRAM_API}/getUpdates',
            params={'offset': offset, 'timeout': 30, 'limit': 10}, timeout=35)
        data = resp.json()
        if data.get('ok'):
            return data.get('result', [])
    except Exception as e:
        logger.error(f'getUpdates error: {e}')
    return []

def send_telegram_message(chat_id, text):
    """Gửi reply trực tiếp qua Telegram API - bypass n8n"""
    try:
        resp = requests.post(f'{TELEGRAM_API}/sendMessage',
            json={'chat_id': chat_id, 'text': text}, timeout=10)
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
    """Xử lý lệnh và trả về reply text"""
    text = text.strip()
    first_name = first_name or 'there'

    if text == '/start':
        return (f"Hello {first_name}!\n\n"
                f"I am OpenClaw Bot.\n\n"
                f"Commands:\n"
                f"/status - system status\n"
                f"/help - help")
    elif text == '/status':
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        return (f"OpenClaw system OK\n\n"
                f"Bot: Online\n"
                f"n8n: Running\n"
                f"Time: {now}")
    elif text == '/help':
        return ("Help:\n"
                "/start - start\n"
                "/status - status\n"
                "/help - help\n\n"
                "Send an invoice image for OCR.")
    elif text.startswith('/'):
        return f"Command '{text}' is not supported. Use /help to see available commands."
    elif len(text) > 0:
        return f"You sent: \"{text}\"\nUse /help to see commands."
    return None

def forward_to_n8n(update):
    """Forward update den n8n (cho cac workflow khac nhu OCR)"""
    try:
        resp = requests.post(N8N_WEBHOOK,
            json={'body': update, 'headers': {}, 'query': {}}, timeout=10)
        logger.info(f'n8n response: {resp.status_code} - {resp.text[:200]}')
        return resp.status_code == 200
    except Exception as e:
        logger.error(f'n8n forward error: {e}')
    return False

def main():
    global last_update_id
    logger.info('OpenClaw Telegram Polling v3 (direct reply) started...')
    while True:
        updates = get_updates(offset=last_update_id + 1)
        for update in updates:
            update_id = update.get('update_id', 0)
            message = update.get('message', {})
            chat = message.get('chat', {})
            chat_id = chat.get('id')
            username = chat.get('username', 'unknown')
            first_name = message.get('from', {}).get('first_name', 'there')
            text = message.get('text', '')

            logger.info(f'UPDATE: update_id={update_id} chat_id={chat_id} username=@{username} text={text!r}')

            # Luu chat_id
            try:
                with open(CHAT_ID_FILE, 'w') as f:
                    f.write(str(chat_id))
            except Exception as e:
                logger.error(f'Save chat_id error: {e}')

            # Xu ly lenh truc tiep - khong qua n8n
            if text and chat_id:
                reply = process_command(chat_id, text, first_name)
                if reply:
                    send_telegram_message(chat_id, reply)
                    logger.info(f'DIRECT reply sent for command: {text}')
                else:
                    # Khong phai lenh text -> forward n8n cho OCR etc
                    forward_to_n8n(update)
            elif message.get('photo') or message.get('document'):
                # Anh/file -> forward den n8n de xu ly OCR
                logger.info(f'Media message, forwarding to n8n...')
                forward_to_n8n(update)

            last_update_id = max(last_update_id, update_id)
        time.sleep(1)

if __name__ == '__main__':
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN environment variable is required")
    main()
