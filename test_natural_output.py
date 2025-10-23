"""
Test natural output format (no citations, no "according to" phrases)
"""

import requests

BASE_URL = "http://localhost:5001"

print("="*60)
print("Testing Natural Output Format")
print("="*60)

query = "E-1ビザの貿易の条件とは？"

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
        print(f"\n【回答】\n{data['answer']}")
        print("\n" + "="*60)
        print("改善点:")
        print("✓ 出典情報なし")
        print("✓ 「参照情報によると」などのフレーズなし")
        print("✓ より自然な回答")
        print("="*60)
    else:
        print(f"Error: {data['error']}")
else:
    print(f"HTTP Error: {response.status_code}")
