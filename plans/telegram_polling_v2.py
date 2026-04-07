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

def forward_to_n8n(update):
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
    logger.info('OpenClaw Telegram Polling v2 started...')
    while True:
        updates = get_updates(offset=last_update_id + 1)
        for update in updates:
            update_id = update.get('update_id', 0)
            message = update.get('message', {})
            chat = message.get('chat', {})
            chat_id = chat.get('id', '?')
            username = chat.get('username', 'unknown')
            text = message.get('text', '')
            logger.info(f'UPDATE: update_id={update_id} chat_id={chat_id} username=@{username} text={text}')
            try:
                with open(CHAT_ID_FILE, 'w') as f:
                    f.write(str(chat_id))
                logger.info(f'SAVED chat_id={chat_id} to {CHAT_ID_FILE}')
            except Exception as e:
                logger.error(f'Save chat_id error: {e}')
            forward_to_n8n(update)
            last_update_id = max(last_update_id, update_id)
        time.sleep(1)

if __name__ == '__main__':
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN environment variable is required")
    main()
