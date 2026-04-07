#!/usr/bin/env python3
"""
Telegram Bot Polling Service for OpenClaw
Polls Telegram API và forward messages tới n8n webhook
"""
import os
import requests
import time
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
N8N_WEBHOOK = "http://localhost:5678/webhook/openclaw-telegram"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

last_update_id = 0

def get_updates(offset=0):
    try:
        resp = requests.get(
            f"{TELEGRAM_API}/getUpdates",
            params={"offset": offset, "timeout": 30, "limit": 10},
            timeout=35
        )
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
    except Exception as e:
        logger.error(f"getUpdates error: {e}")
    return []

def forward_to_n8n(update):
    try:
        resp = requests.post(
            N8N_WEBHOOK,
            json={"body": update, "headers": {}, "query": {}},
            timeout=10
        )
        logger.info(f"n8n response: {resp.status_code} - {resp.text[:100]}")
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"n8n forward error: {e}")
    return False

def main():
    global last_update_id
    logger.info("OpenClaw Telegram Polling started...")

    while True:
        updates = get_updates(offset=last_update_id + 1)
        for update in updates:
            update_id = update.get("update_id", 0)
            message = update.get("message", {})
            chat_id = message.get("chat", {}).get("id", "?")
            text = message.get("text", "")
            logger.info(f"Message from chat_id={chat_id}: {text}")

            forward_to_n8n(update)
            last_update_id = max(last_update_id, update_id)

        time.sleep(1)

if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN environment variable is required")
    main()
