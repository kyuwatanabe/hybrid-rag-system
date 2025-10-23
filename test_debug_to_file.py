"""
Debug: Check what chunks are being retrieved - save to file
"""

import sys
sys.path.append('.')

from rag_system import RAGSystem

# Initialize RAG system
rag = RAGSystem()
rag.load_knowledge_base()

query = "E-2ビザの申請条件を教えて。"

# Search for relevant chunks
relevant_chunks = rag.search_relevant_chunks(query, k=10)

output = []
output.append("=" * 80)
output.append(f"質問: {query}")
output.append("=" * 80)
output.append(f"\n取得されたチャンク数: {len(relevant_chunks)}\n")

for i, chunk in enumerate(relevant_chunks, 1):
    output.append(f"【チャンク {i}】")
    output.append(f"ファイル: {chunk['file_name']}")
    output.append(f"ページ: {chunk['page_num']}")
    output.append(f"類似度: {chunk.get('similarity', 0.0):.4f}")
    output.append(f"内容:\n{chunk['text']}")
    output.append("-" * 80)
    output.append("")

# Write to file
with open("debug_chunks_e2.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print(f"チャンク情報を debug_chunks_e2.txt に保存しました")
print(f"取得されたチャンク数: {len(relevant_chunks)}")
