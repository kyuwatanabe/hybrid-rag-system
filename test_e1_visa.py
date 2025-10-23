"""
Test E-1 visa question that previously had focus issues
"""

import requests

query = "E-1ビザの貿易の条件とは？"

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

        # Check for preambles
        preambles = ["以下のとおり", "次のようになります", "参照情報によると", "資料によると"]
        has_preamble = any(p in answer for p in preambles)
        if has_preamble:
            output.append("❌ 前置き表現が含まれています")
        else:
            output.append("✓ 前置き表現なし")

        # Check for off-topic info (E-2 visa, application documents, review period)
        off_topic = ["E-2", "申請書類", "審査期間"]
        has_off_topic = any(t in answer for t in off_topic)
        if has_off_topic:
            output.append("❌ 質問に直接関係ない情報が含まれています")
        else:
            output.append("✓ 質問に直接答える内容のみ")

        # Check sentence count
        sentences = answer.split("。")
        sentence_count = len([s for s in sentences if s.strip()])
        if sentence_count <= 2:
            output.append(f"✓ {sentence_count}文で完結")
        else:
            output.append(f"⚠ {sentence_count}文 (目標は1-2文)")

        # Check if it focuses on trade conditions specifically
        if "貿易" in answer or "取引" in answer or "商取引" in answer:
            output.append("✓ 貿易の条件に焦点を当てている")
        else:
            output.append("⚠ 貿易の条件への言及が弱い可能性")

        output.append("=" * 60)
    else:
        output.append(f"Error: {data.get('error', 'Unknown error')}")
else:
    output.append(f"HTTP Error {response.status_code}")

# Write to file
with open("test_e1_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Test completed. Results saved to test_e1_result.txt")
