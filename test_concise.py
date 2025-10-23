"""
Test concise output (no extra info, just answer the question)
"""

import requests

BASE_URL = "http://localhost:5001"

print("="*60)
print("Testing Concise Output")
print("="*60)

query = "E-2ビザの申請条件を教えて。"

print(f"\nQuery: {query}")
print("-" * 60)

response = requests.post(
    f"{BASE_URL}/api/chat",
    json={"query": query},
    headers={"Content-Type": "application/json"}
)

if response.status_code == 200:
    data = response.json()
    if data['success']:
        print(f"\n{data['answer']}")
        print("\n" + "="*60)
        print("Goal: 2-3 sentences, just the core answer")
        print("No:審査期間, 関連情報など")
        print("="*60)
    else:
        print(f"Error: {data['error']}")
else:
    print(f"HTTP Error: {response.status_code}")
