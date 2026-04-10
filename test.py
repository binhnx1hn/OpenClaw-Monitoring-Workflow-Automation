import base64, json, subprocess

# Đọc ảnh và encode base64
with open("IMG_6214.jpeg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

# Gửi qua webhook client-ocr-demo (OCR + Telegram)
payload = {
    "image_url": "",
    "image_base64": b64,
    "filename": "IMG_6214.jpeg",
    "chat_id": "6190676114"
}

with open("payload.json", "w") as f:
    json.dump(payload, f)

print("Payload size:", len(b64), "chars")