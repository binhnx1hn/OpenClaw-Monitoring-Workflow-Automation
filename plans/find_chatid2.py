import subprocess
import re

PG = subprocess.check_output("docker ps | grep postgres | awk '{print $1}'", shell=True).decode().strip()

result = subprocess.run(
    ["docker", "exec", PG, "psql", "-U", "n8n", "-d", "n8n", "-t", "-c",
     'SELECT data FROM execution_data WHERE "executionId" IN (26, 28);'],
    capture_output=True, text=True
)

raw = result.stdout

# Find all numbers near chat or id
print("=== All 7-12 digit numbers ===")
nums = list(set(re.findall(r'\b(\d{7,12})\b', raw)))
print(nums)

print("\n=== Sections with 'chat' or 'start' ===")
# Split by comma and find relevant sections
parts = raw.split(',')
for i, part in enumerate(parts):
    lower = part.lower()
    if 'chat' in lower or '/start' in lower or 'message_id' in lower:
        # print surrounding context
        ctx = ','.join(parts[max(0,i-1):i+3])
        print("CTX:", ctx[:300])
        print("---")

print("\n=== Raw (first 3000 chars) ===")
print(raw[:3000])
