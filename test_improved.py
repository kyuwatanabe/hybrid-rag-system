"""
Test improved RAG system with focused prompts and fewer chunks
"""

import requests
import json

BASE_URL = "http://localhost:5001"

print("="*60)
print("Testing Improved RAG System")
print("="*60)

# Test the specific question that had focus issues
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
        print(f"\n【出典】 {data['num_sources']}件")
        for source in data['sources']:
            print(f"  {source['number']}. {source['file_name']} (Page {source['page_num']}) - 類似度: {source['similarity']:.3f}")
    else:
        print(f"Error: {data['error']}")
else:
    print(f"HTTP Error: {response.status_code}")

print("\n" + "="*60)
print("改善ポイント:")
print("1. チャンク数: 5個 → 3個（より焦点を絞る）")
print("2. プロンプト: 結論ファーストを明示")
print("3. プロンプト: 関連性の低い情報は省略するよう指示")
print("="*60)
