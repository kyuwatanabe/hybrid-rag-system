"""
Quick test with proper UTF-8 encoding
"""

import requests
import json

query = "E-2ビザの申請条件を教えて。"

response = requests.post(
    "http://localhost:5001/api/chat",
    json={"query": query},
    headers={"Content-Type": "application/json; charset=utf-8"}
)

if response.status_code == 200:
    data = response.json()
    if data['success']:
        answer = data['answer']
        print("=" * 60)
        print(f"質問: {query}")
        print("-" * 60)
        print(f"\n回答:\n{answer}\n")
        print("=" * 60)
        print("\n検証ポイント:")
        if "以下のとおり" in answer:
            print("❌ 「以下のとおり」が含まれています")
        else:
            print("✓ 「以下のとおり」なし")

        if "参照情報によると" in answer or "資料によると" in answer:
            print("❌ 「参照情報によると」または「資料によると」が含まれています")
        else:
            print("✓ 出典への言及なし")

        sentences = answer.split("。")
        sentence_count = len([s for s in sentences if s.strip()])
        if sentence_count <= 2:
            print(f"✓ {sentence_count}文で完結")
        else:
            print(f"❌ {sentence_count}文 (目標は1-2文)")

        print("=" * 60)
    else:
        print(f"Error: {data.get('error', 'Unknown error')}")
else:
    print(f"HTTP Error {response.status_code}")
    print(response.text)
