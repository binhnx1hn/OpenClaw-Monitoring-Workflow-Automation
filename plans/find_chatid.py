import subprocess
import re
import json

# Get execution data from postgres
result = subprocess.run(
    ["docker", "exec", 
     subprocess.check_output("docker ps | grep postgres | awk '{print $1}'", shell=True).decode().strip(),
     "psql", "-U", "n8n", "-d", "n8n", "-t", "-c",
     "SELECT data FROM execution_data WHERE \"executionId\" IN (26, 28);"],
    capture_output=True, text=True
)

raw = result.stdout + result.stderr
print("Raw length:", len(raw))

# Search for chat_id patterns
chat_ids = re.findall(r'chat.{0,5}id.{0,5}(\d{5,12})', raw, re.IGNORECASE)
print("chat_id patterns:", chat_ids[:5])

# Search for numbers 7-10 digits (typical telegram user IDs)
all_ids = re.findall(r'\b(\d{7,12})\b', raw)
unique_ids = list(set(all_ids))
print("All 7-12 digit numbers:", unique_ids[:20])

# Try to find "from" id
from_ids = re.findall(r'"from".*?"id".*?(\d{5,12})', raw, re.IGNORECASE | re.DOTALL)
print("from.id patterns:", from_ids[:5])

# Print first 2000 chars of raw for manual inspection
print("\n--- RAW PREVIEW ---")
print(raw[:2000])
