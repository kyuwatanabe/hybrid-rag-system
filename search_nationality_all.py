"""
Search all chunks for nationality-related keywords
"""
import sys
sys.path.append('.')

from vector_store import VectorStore

# Initialize vector store
vs = VectorStore()
vs.load_index()

# Keywords related to nationality requirement
keywords = ["国籍", "条約国", "treaty", "申請者", "派遣", "E-2", "条件"]

print(f"全チャンク数: {len(vs.chunks_metadata)}")
print("=" * 80)

for keyword in keywords:
    print(f"\nキーワード: '{keyword}' を含むチャンク:")
    print("-" * 80)

    matches = []
    for idx, chunk in enumerate(vs.chunks_metadata):
        if keyword.lower() in chunk['text'].lower():
            matches.append((idx, chunk))

    print(f"見つかったチャンク数: {len(matches)}")

    # Show first 3 matches
    for i, (idx, chunk) in enumerate(matches[:3]):
        print(f"\n【マッチ {i+1}】 (チャンク番号: {idx})")
        print(f"ページ: {chunk['page_num']}")
        # Find the position of the keyword
        text_lower = chunk['text'].lower()
        pos = text_lower.find(keyword.lower())
        if pos >= 0:
            # Show context around the keyword
            start = max(0, pos - 100)
            end = min(len(chunk['text']), pos + 100)
            context = chunk['text'][start:end]
            print(f"文脈: ...{context}...")

    print()
