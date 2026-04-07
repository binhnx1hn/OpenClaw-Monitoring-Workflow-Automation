import json
import os
import urllib.request
import urllib.error

API_KEY = os.environ.get("N8N_API_KEY", "")
BASE_URL = os.environ.get("N8N_BASE_URL", "http://localhost:5678/api/v1")

js_code = (
    "const update = $input.first().json;\n"
    "const message = update.message || {};\n"
    "const text = message.text || '';\n"
    "const chatId = message.chat && message.chat.id;\n"
    "const firstName = (message.from && message.from.first_name) || 'User';\n"
    "\n"
    "let reply = '';\n"
    "if (text === '/start' || text.startsWith('/start')) {\n"
    "  reply = 'Hello ' + firstName + '! \\u{1F44B}\\n\\nI am OpenClaw Assistant Bot.\\n\\n\\u2705 Chat ID: ' + chatId + '\\n\\n\\u{1F4CB} Commands:\\n/status - system status\\n/help - help';\n"
    "} else if (text === '/status') {\n"
    "  const t = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';\n"
    "  reply = 'OpenClaw system OK\\n\\nBot: Online\\nn8n: Running\\nPostgreSQL: Running\\nMinIO: Running\\nOCR Pipeline: Ready\\nTime: ' + t;\n"
    "} else if (text === '/help') {\n"
    "  reply = '\\u{1F4CB} Help:\\n/start - start\\n/status - status\\n/help - help\\n\\nSend an invoice image for OCR.';\n"
    "} else {\n"
    "  reply = 'You sent: \"' + text + '\"\\nUse /help to see commands.';\n"
    "}\n"
    "\n"
    "return [{ json: { chatId: chatId, reply: reply } }];"
)

workflow = {
    "name": "Telegram Bot v2 - Polling Native",
    "nodes": [
        {
            "parameters": {
                "updates": ["message"],
                "additionalFields": {}
            },
            "id": "tg-trigger-001",
            "name": "Telegram Trigger",
            "type": "n8n-nodes-base.telegramTrigger",
            "typeVersion": 1.1,
            "position": [250, 300],
            "credentials": {
                "telegramApi": {
                    "id": "8rvHrkiGjHElEu4f",
                    "name": "OpenClaw Telegram Bot"
                }
            }
        },
        {
            "parameters": {
                "jsCode": js_code
            },
            "id": "process-msg-002",
            "name": "Process Message",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [470, 300]
        },
        {
            "parameters": {
                "chatId": "={{ $json.chatId }}",
                "text": "={{ $json.reply }}",
                "additionalFields": {}
            },
            "id": "send-reply-002",
            "name": "Send Reply",
            "type": "n8n-nodes-base.telegram",
            "typeVersion": 1.2,
            "position": [690, 300],
            "credentials": {
                "telegramApi": {
                    "id": "8rvHrkiGjHElEu4f",
                    "name": "OpenClaw Telegram Bot"
                }
            }
        }
    ],
    "connections": {
        "Telegram Trigger": {
            "main": [[{"node": "Process Message", "type": "main", "index": 0}]]
        },
        "Process Message": {
            "main": [[{"node": "Send Reply", "type": "main", "index": 0}]]
        }
    },
    "settings": {
        "executionOrder": "v1"
    }
}


def api_request(path, method="GET", payload=None):
    url = BASE_URL + path
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-N8N-API-KEY", API_KEY)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, "HTTP " + str(e.code) + ": " + e.read().decode()
    except Exception as ex:
        return None, str(ex)


# Step 1: Create workflow
if not API_KEY:
    print("ERROR: set N8N_API_KEY environment variable (n8n API key).")
    exit(1)

print("=== STEP 1: Create new workflow ===")
result, err = api_request("/workflows", method="POST", payload=workflow)
if err:
    print("ERROR creating workflow:", err)
    exit(1)

new_wf_id = result.get("id")
print("Created workflow ID:", new_wf_id, "| Name:", result.get("name"))

# Step 2: Activate new workflow
print("\n=== STEP 2: Activate new workflow ===")
result2, err2 = api_request("/workflows/" + new_wf_id + "/activate", method="PATCH")
if err2:
    print("ERROR activating:", err2)
else:
    print("Activated:", result2.get("id"), "| Active:", result2.get("active"))

# Step 3: Deactivate old webhook workflow
print("\n=== STEP 3: Deactivate old workflow Ay4PiqO6lQVp8iy1 ===")
result3, err3 = api_request("/workflows/Ay4PiqO6lQVp8iy1/deactivate", method="PATCH")
if err3:
    print("ERROR deactivating old:", err3)
else:
    print("Deactivated old:", result3.get("id"), "| Active:", result3.get("active"))

print("\n=== DONE ===")
print("New workflow ID:", new_wf_id)
print("Please send /start to bot now to test!")
