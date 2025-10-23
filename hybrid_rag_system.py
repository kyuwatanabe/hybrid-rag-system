"""
ハイブリッドRAGシステム

FAQシステムとRAGシステムを統合。
1. まずFAQを検索（高速・高品質）
2. 見つからなければRAGで生成（網羅的・柔軟）
3. 良い回答は承認待ちリストに追加（学習）
"""

import csv
import os
from datetime import datetime
from typing import Dict, List, Optional
from faq_searcher import FAQSearcher
from rag_system import RAGSystem
from faq_manager import FAQManager


class HybridRAGSystem:
    """FAQ + RAG ハイブリッドシステム"""

    def __init__(
        self,
        faq_csv_path: str = "faq_database.csv",
        pending_csv_path: str = "pending_faq_approvals.csv",
        faq_threshold: float = 0.85,
        claude_api_key: Optional[str] = None
    ):
        """
        HybridRAGSystemの初期化

        Args:
            faq_csv_path: FAQデータのCSVファイルパス（デフォルト: faq_database.csv）
            pending_csv_path: 承認待ちFAQのCSVファイルパス
            faq_threshold: FAQ検索の類似度閾値（これ以上でFAQを返す）
            claude_api_key: Claude APIキー（FAQ生成用）
        """
        self.faq_threshold = faq_threshold
        self.faq_csv_path = faq_csv_path
        self.pending_csv_path = pending_csv_path

        # FAQManagerの初期化
        print("\n" + "="*60)
        print("ハイブリッドRAGシステム 初期化中...")
        print("="*60)

        print("\n[1/3] FAQ管理システムを初期化中...")
        self.faq_manager = FAQManager(
            faq_csv_path=faq_csv_path,
            pending_csv_path=pending_csv_path,
            claude_api_key=claude_api_key
        )

        print("\n[2/3] FAQ検索システムを初期化中...")
        self.faq_searcher = FAQSearcher(faq_csv_path)

        print("\n[3/3] RAGシステムを初期化中...")
        self.rag_system = RAGSystem()
        self.rag_system.load_knowledge_base()

        # FAQデータをベクトルDBに統合（RAGの学習）
        print("\n[4/4] FAQデータをRAGに統合中...")
        self._integrate_faqs_to_rag()

        print("\n" + "="*60)
        print("ハイブリッドRAGシステム 準備完了！")
        print("="*60)

    def answer_question(self, query: str) -> Dict:
        """
        質問に回答する（FAQ優先、なければRAG生成）

        Args:
            query: ユーザーの質問

        Returns:
            回答情報を含む辞書
            {
                'query': 質問,
                'answer': 回答,
                'source': 'FAQ' または 'RAG',
                'similarity': FAQ類似度（FAQの場合のみ）,
                'sources': 出典情報（RAGの場合のみ）,
                'faq_question': 元のFAQ質問（FAQの場合のみ）
            }
        """
        print(f"\n質問: {query}")
        print("-" * 60)

        # 1. まずFAQを検索
        print("[1] FAQ検索中...")
        faq_result = self.faq_searcher.get_best_match(query, threshold=self.faq_threshold)

        if faq_result:
            # FAQがヒット
            print(f"[OK] FAQ見つかりました！（類似度: {faq_result['similarity']:.3f}）")
            return {
                'query': query,
                'answer': faq_result['answer'],
                'source': 'FAQ',
                'similarity': faq_result['similarity'],
                'faq_question': faq_result['question']
            }

        # 2. FAQになければRAGで生成
        print("[NO] FAQに該当なし")
        print("[2] RAGで回答を生成中...")

        rag_result = self.rag_system.answer_question(query)

        print("[OK] RAG回答生成完了")

        return {
            'query': query,
            'answer': rag_result['answer'],
            'source': 'RAG',
            'sources': rag_result.get('sources', []),
            'num_sources': rag_result.get('num_sources', 0)
        }

    def save_to_pending_approval(
        self,
        query: str,
        answer: str,
        source: str = 'RAG',
        user_rating: str = 'positive'
    ) -> bool:
        """
        承認待ちリストに回答を保存

        Args:
            query: ユーザーの質問
            answer: 生成された回答
            source: 回答ソース（'RAG'など）
            user_rating: ユーザー評価（'positive', 'negative'）

        Returns:
            保存成功/失敗
        """
        return self.faq_manager.add_pending_faq(
            question=query,
            answer=answer,
            source=source,
            user_rating=user_rating
        )

    def get_pending_approvals(self, limit: int = 50) -> List[Dict]:
        """
        承認待ちのFAQを取得

        Args:
            limit: 取得する最大件数

        Returns:
            承認待ちFAQのリスト
        """
        pending_faqs = self.faq_manager.get_pending_faqs(status='pending')
        return pending_faqs[:limit]

    def update_pending_faq(self, faq_id: int, question: str, answer: str) -> bool:
        """
        承認待ちFAQを編集

        Args:
            faq_id: 承認待ちFAQのID
            question: 新しい質問
            answer: 新しい回答

        Returns:
            更新成功/失敗
        """
        return self.faq_manager.update_pending_faq(faq_id, question, answer)

    def approve_faq(self, faq_id: int) -> bool:
        """
        承認待ちFAQを承認してFAQデータベースに追加
        同時にRAGのベクトルDBも更新してRAGが学習する

        Args:
            faq_id: 承認待ちFAQのID

        Returns:
            承認成功/失敗
        """
        success = self.faq_manager.approve_pending_faq(faq_id)

        if success:
            # FAQとRAGの両方を更新
            print("\n[INFO] FAQ承認後の更新処理を開始...")
            self.reload_faqs_to_rag()
            print("[OK] 更新処理が完了しました")

        return success

    def reject_faq(self, faq_id: int) -> bool:
        """
        承認待ちFAQを拒否

        Args:
            faq_id: 承認待ちFAQのID

        Returns:
            拒否成功/失敗
        """
        return self.faq_manager.reject_pending_faq(faq_id)

    def get_stats(self) -> Dict:
        """
        システムの統計情報を取得

        Returns:
            統計情報の辞書
        """
        return self.faq_manager.get_stats()

    def _integrate_faqs_to_rag(self):
        """
        承認済みFAQデータをRAGのベクトルDBに統合
        これによりRAGが過去の良い回答から学習できる
        """
        try:
            # FAQデータを取得
            faqs = self.faq_manager.get_all_faqs()

            if len(faqs) == 0:
                print("[INFO] FAQデータがありません。スキップします。")
                return

            print(f"[INFO] {len(faqs)}件のFAQをベクトルDBに統合します...")

            # RAGシステムのベクトルストアにFAQを追加
            self.rag_system.vector_store.rebuild_with_faqs(faqs)

            print(f"[OK] FAQデータの統合が完了しました")
            print(f"[OK] RAGは{len(faqs)}件のFAQから学習しました")

        except Exception as e:
            print(f"[WARNING] FAQ統合エラー: {e}")
            print(f"[WARNING] RAGはPDFのみで動作します")

    def reload_faqs_to_rag(self):
        """
        FAQデータをRAGに再統合（新しいFAQが承認された後に呼び出す）
        """
        print("\n[INFO] FAQデータを再統合中...")
        self._integrate_faqs_to_rag()
        # FAQ検索システムも再読み込み
        self.faq_searcher.reload()
        print("[OK] FAQデータの再統合が完了しました")


# テスト用
if __name__ == "__main__":
    # ファイルパス
    faq_path = r"C:\Users\GF001\Desktop\システム開発\手引き用チャットボット\faq_system\faq_generation_history.csv"

    # ハイブリッドシステムの初期化
    hybrid = HybridRAGSystem(faq_csv_path=faq_path, faq_threshold=0.85)

    # テスト質問
    test_queries = [
        "H-1Bビザの学歴要件は何ですか？",  # FAQにある
        "ESTA申請が拒否された場合は？",    # FAQにある
        "ビザウェーバープログラムとは？",  # RAG生成が必要
    ]

    print("\n\n" + "="*60)
    print("ハイブリッドRAGシステム テスト")
    print("="*60)

    for query in test_queries:
        result = hybrid.answer_question(query)

        print("\n" + "="*60)
        print(f"ソース: {result['source']}")
        print("="*60)

        if result['source'] == 'FAQ':
            print(f"FAQ質問: {result['faq_question']}")
            print(f"類似度: {result['similarity']:.3f}")
            print(f"\n回答:\n{result['answer']}")
        else:
            print(f"回答:\n{result['answer']}")
            print(f"\n出典数: {result['num_sources']}")

        # RAG回答の場合は承認待ちリストに追加（テスト）
        if result['source'] == 'RAG':
            hybrid.save_to_pending_approval(
                query=query,
                answer=result['answer'],
                source='RAG',
                user_rating='positive'
            )

        print("\n")
