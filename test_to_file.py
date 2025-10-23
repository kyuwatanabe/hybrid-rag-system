"""
Test and save output to file with UTF-8 encoding
"""

import requests
import json

query = "E-2ビザの申請条件を教えて。"

response = requests.post(
    "http://localhost:5001/api/chat",
    json={"query": query},
    headers={"Content-Type": "application/json; charset=utf-8"}
)

output = []

if response.status_code == 200:
    data = response.json()
    if data['success']:
        answer = data['answer']
        output.append("=" * 60)
        output.append(f"質問: {query}")
        output.append("-" * 60)
        output.append(f"\n回答:\n{answer}\n")
        output.append("=" * 60)
        output.append("\n検証ポイント:")

        if "以下のとおり" in answer:
            output.append("❌ 「以下のとおり」が含まれています")
        else:
            output.append("✓ 「以下のとおり」なし")

        if "参照情報によると" in answer or "資料によると" in answer:
            output.append("❌ 「参照情報によると」または「資料によると」が含まれています")
        else:
            output.append("✓ 出典への言及なし")

        sentences = answer.split("。")
        sentence_count = len([s for s in sentences if s.strip()])
        if sentence_count <= 2:
            output.append(f"✓ {sentence_count}文で完結")
        else:
            output.append(f"❌ {sentence_count}文 (目標は1-2文)")

        output.append("=" * 60)
    else:
        output.append(f"Error: {data.get('error', 'Unknown error')}")
else:
    output.append(f"HTTP Error {response.status_code}")
    output.append(response.text)

# Write to file with UTF-8 encoding
with open("test_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Test completed. Results saved to test_result.txt")
