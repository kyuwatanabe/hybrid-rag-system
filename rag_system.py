"""
RAG System Core
Handles question answering using vector search and Claude API
"""

import os
from typing import List, Dict, Tuple
from anthropic import Anthropic
from dotenv import load_dotenv
from vector_store import VectorStore

# Load environment variables
load_dotenv()

# Configuration
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
TOP_K_CHUNKS = int(os.getenv('TOP_K_CHUNKS', 10))
FINAL_CHUNKS = int(os.getenv('FINAL_CHUNKS', 5))


class RAGSystem:
    def __init__(self):
        """Initialize RAG system with vector store and Claude API"""
        print("Initializing RAG system...")

        # Initialize Claude API client
        if not CLAUDE_API_KEY:
            raise ValueError("CLAUDE_API_KEY not found in environment variables")

        self.claude_client = Anthropic(api_key=CLAUDE_API_KEY)

        # Initialize vector store
        self.vector_store = VectorStore()

        print("RAG system initialized")

    def load_knowledge_base(self, index_path: str = None):
        """
        Load vector database

        Args:
            index_path: Path to FAISS index (default: from .env)
        """
        print("Loading knowledge base...")
        self.vector_store.load_index(index_path)
        print("Knowledge base loaded successfully")

    def expand_query(self, query: str) -> str:
        """
        Expand query with related keywords using LLM

        Args:
            query: Original user query

        Returns:
            Expanded query with keywords
        """
        try:
            prompt = f"""質問から検索に役立つキーワードを抽出してください。

質問: {query}

以下の形式で出力してください:
- 元の質問の主要なキーワード
- 関連する同義語や言い換え
- 関連する専門用語

出力は改行区切りのキーワードリストのみ。説明不要。5-10個程度。"""

            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            keywords = response.content[0].text.strip()
            expanded = f"{query} {keywords}"

            print(f"Expanded query: {expanded[:100]}...")
            return expanded

        except Exception as e:
            print(f"Query expansion failed: {e}")
            return query

    def search_relevant_chunks(self, query: str, k: int = 10) -> List[Dict]:
        """
        Search for relevant text chunks using hybrid search

        Args:
            query: User's question
            k: Number of chunks to retrieve

        Returns:
            List of relevant chunks with metadata
        """
        print(f"\nSearching for relevant information...")

        # Expand query with keywords
        expanded_query = self.expand_query(query)

        # Use hybrid search (vector + keyword)
        # alpha=0.3 gives more weight to keyword matching for better precision
        results = self.vector_store.hybrid_search(expanded_query, k=k, alpha=0.3)

        # Filter and deduplicate
        filtered_results = self.vector_store.filter_and_deduplicate(
            results,
            final_k=FINAL_CHUNKS
        )

        print(f"Found {len(filtered_results)} relevant chunks")

        # Debug: Write chunk details to file
        try:
            with open("search_debug.txt", "w", encoding="utf-8") as f:
                f.write("="*60 + "\n")
                f.write("SEARCH RESULTS DEBUG:\n")
                f.write(f"Original Query: {query}\n")
                f.write(f"Expanded Query: {expanded_query}\n")
                f.write(f"Found {len(filtered_results)} chunks\n\n")
                for i, chunk in enumerate(filtered_results, 1):
                    f.write(f"\n[Chunk {i}]\n")
                    f.write(f"File: {chunk['file_name']}, Page: {chunk['page_num']}\n")
                    f.write(f"Similarity: {chunk.get('similarity', 0.0):.4f}\n")
                    f.write(f"Text: {chunk['text'][:300]}\n")
                f.write("="*60 + "\n")
        except Exception as e:
            pass

        return filtered_results

    def generate_answer(self, query: str, relevant_chunks: List[Dict]) -> Dict:
        """
        Generate answer using Claude API

        Args:
            query: User's question
            relevant_chunks: List of relevant text chunks

        Returns:
            Dict containing answer and metadata
        """
        print("Generating answer with Claude API...")

        # Build context from relevant chunks
        context = self._build_context(relevant_chunks)

        # Build prompt with hallucination prevention
        prompt = self._build_prompt(query, context, relevant_chunks)

        # Call Claude API
        try:
            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            answer_text = response.content[0].text

            print("Answer generated successfully")

            return {
                'answer': answer_text,
                'sources': self._format_sources(relevant_chunks),
                'num_sources': len(relevant_chunks),
                'query': query
            }

        except Exception as e:
            import traceback
            import sys
            error_details = traceback.format_exc()
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"ERROR generating answer:", file=sys.stderr)
            print(error_details, file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.stderr.flush()
            return {
                'answer': "申し訳ございません。回答の生成中にエラーが発生しました。",
                'sources': [],
                'num_sources': 0,
                'query': query,
                'error': str(e)
            }

    def _build_context(self, chunks: List[Dict]) -> str:
        """Build context string from chunks"""
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"【参照情報 {i}】\n"
                f"ファイル: {chunk['file_name']}\n"
                f"ページ: {chunk['page_num']}\n"
                f"内容: {chunk['text']}\n"
            )

        return "\n".join(context_parts)

    def _build_prompt(self, query: str, context: str, chunks: List[Dict]) -> str:
        """
        Build prompt with hallucination prevention measures

        Args:
            query: User's question
            context: Context text from relevant chunks
            chunks: List of chunk metadata

        Returns:
            Complete prompt string
        """
        prompt = f"""あなたは提供された参照資料のみに基づいて質問に回答するアシスタントです。

【重要なルール】
1. 参照情報に書かれている内容のみを使って回答してください
2. 参照情報に書かれていない内容は推測しないでください
3. 答えられない場合は「提供された資料に記載されておりません」と答えてください

【参照情報】
{context}

【質問】
{query}

【回答】
参照情報に基づいて、簡潔に回答してください。"""

        return prompt

    def _format_sources(self, chunks: List[Dict]) -> List[Dict]:
        """Format source information"""
        sources = []

        for i, chunk in enumerate(chunks, 1):
            sources.append({
                'number': i,
                'file_name': chunk['file_name'],
                'page_num': chunk['page_num'],
                'text_preview': chunk['text'][:100] + "..." if len(chunk['text']) > 100 else chunk['text'],
                'similarity': chunk.get('similarity', 0.0)
            })

        return sources

    def answer_question(self, query: str) -> Dict:
        """
        Complete pipeline: search and generate answer

        Args:
            query: User's question

        Returns:
            Dict containing answer and metadata
        """
        print("\n" + "="*60)
        print(f"Question: {query}")
        print("="*60)

        # Step 1: Search for relevant chunks
        relevant_chunks = self.search_relevant_chunks(query, k=TOP_K_CHUNKS)

        if not relevant_chunks:
            return {
                'answer': "関連する情報が見つかりませんでした。別の質問をお試しください。",
                'sources': [],
                'num_sources': 0,
                'query': query
            }

        # Step 2: Generate answer
        result = self.generate_answer(query, relevant_chunks)

        print("="*60)
        print("Answer generated successfully")
        print("="*60 + "\n")

        return result


def main():
    """Test the RAG system"""
    print("\n" + "="*60)
    print("Testing RAG System")
    print("="*60 + "\n")

    # Initialize RAG system
    rag = RAGSystem()

    # Load knowledge base
    rag.load_knowledge_base()

    # Test queries
    test_queries = [
        "ビザの申請方法について教えてください",
        "入国審査ではどのような質問をされますか？",
        "ビザなしで滞在できる期間はどのくらいですか？",
        # Hallucination test (question not in PDF)
        "東京の人口は何人ですか？"
    ]

    for query in test_queries:
        result = rag.answer_question(query)

        print(f"\n質問: {result['query']}")
        print("-" * 60)
        print(f"\n回答:\n{result['answer']}")
        print(f"\n参照した情報源: {result['num_sources']}件")

        if result['sources']:
            print("\n【出典詳細】")
            for source in result['sources']:
                print(f"  {source['number']}. {source['file_name']} (ページ {source['page_num']})")
                print(f"     類似度: {source['similarity']:.4f}")
                print(f"     内容: {source['text_preview']}")

        print("\n" + "="*60 + "\n")

        # Wait for user input to continue
        input("Press Enter to continue to next question...")


if __name__ == "__main__":
    main()
