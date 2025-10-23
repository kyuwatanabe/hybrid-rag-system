"""
FAQ検索モジュール

既存FAQシステムのデータを検索するモジュール。
セマンティック検索により、質問に最も近いFAQを見つける。
"""

import csv
import os
from typing import List, Dict, Optional, Tuple
from sentence_transformers import SentenceTransformer
import numpy as np


class FAQSearcher:
    """FAQ検索クラス"""

    def __init__(self, faq_csv_path: str):
        """
        FAQSearcherの初期化

        Args:
            faq_csv_path: FAQデータのCSVファイルパス
        """
        self.faq_csv_path = faq_csv_path
        self.faq_data = []
        self.faq_embeddings = None

        # セマンティック検索用モデル（既存FAQシステムと同じモデル）
        print("[INFO] FAQ検索用モデルをロード中...")
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        print("[INFO] FAQ検索用モデルのロード完了")

        # FAQデータの読み込み
        self.load_faq_data()

        # FAQ質問のベクトル化（初回のみ）
        if len(self.faq_data) > 0:
            self.compute_faq_embeddings()

    def load_faq_data(self) -> None:
        """CSVファイルからFAQデータを読み込む"""
        self.faq_data = []

        if not os.path.exists(self.faq_csv_path):
            print(f"[WARNING] FAQファイルが見つかりません: {self.faq_csv_path}")
            return

        try:
            with open(self.faq_csv_path, 'r', encoding='utf-8-sig') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    # timestampがある場合とない場合の両方に対応
                    question = row.get('question', '').strip()
                    answer = row.get('answer', '').strip()

                    if question and answer:
                        self.faq_data.append({
                            'question': question,
                            'answer': answer,
                            'timestamp': row.get('timestamp', '')
                        })

            # 重複を除去（同じ質問がある場合は最新のみ保持）
            unique_faqs = {}
            for faq in self.faq_data:
                question = faq['question']
                # 同じ質問がない場合、または新しいタイムスタンプの場合に上書き
                if question not in unique_faqs or faq['timestamp'] >= unique_faqs[question]['timestamp']:
                    unique_faqs[question] = faq

            self.faq_data = list(unique_faqs.values())
            print(f"[INFO] FAQデータを{len(self.faq_data)}件読み込みました（重複除去済み）")

        except Exception as e:
            print(f"[ERROR] FAQデータ読み込みエラー: {e}")

    def compute_faq_embeddings(self) -> None:
        """FAQ質問のベクトルを事前計算"""
        print("[INFO] FAQ質問のベクトル化を開始...")
        questions = [faq['question'] for faq in self.faq_data]
        self.faq_embeddings = self.model.encode(questions, convert_to_numpy=True)
        print(f"[INFO] {len(questions)}件の質問をベクトル化しました")

    def search(self, query: str, top_k: int = 3, threshold: float = 0.85) -> List[Dict]:
        """
        質問に類似するFAQを検索

        Args:
            query: ユーザーの質問
            top_k: 返す結果の最大数
            threshold: 類似度の閾値（これ以上の場合のみ返す）

        Returns:
            類似するFAQのリスト（類似度の高い順）
        """
        if len(self.faq_data) == 0:
            return []

        # 質問をベクトル化
        query_embedding = self.model.encode([query], convert_to_numpy=True)[0]

        # コサイン類似度を計算
        similarities = np.dot(self.faq_embeddings, query_embedding) / (
            np.linalg.norm(self.faq_embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # 類似度の高い順にソート
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            similarity = float(similarities[idx])
            if similarity >= threshold:
                results.append({
                    'question': self.faq_data[idx]['question'],
                    'answer': self.faq_data[idx]['answer'],
                    'similarity': similarity,
                    'source': 'FAQ'
                })

        return results

    def get_best_match(self, query: str, threshold: float = 0.85) -> Optional[Dict]:
        """
        最も類似度の高いFAQを1件取得

        Args:
            query: ユーザーの質問
            threshold: 類似度の閾値

        Returns:
            最も類似するFAQ、または閾値未満の場合はNone
        """
        results = self.search(query, top_k=1, threshold=threshold)
        return results[0] if results else None

    def reload(self) -> None:
        """FAQデータを再読み込み"""
        print("[INFO] FAQデータを再読み込み中...")
        self.load_faq_data()
        if len(self.faq_data) > 0:
            self.compute_faq_embeddings()
        print("[INFO] FAQデータの再読み込み完了")


# テスト用
if __name__ == "__main__":
    # FAQファイルのパス（既存FAQシステム）
    faq_path = r"C:\Users\GF001\Desktop\システム開発\手引き用チャットボット\faq_system\faq_generation_history.csv"

    # FAQSearcherの初期化
    searcher = FAQSearcher(faq_path)

    # テスト質問
    test_queries = [
        "H-1Bビザの学歴要件は？",
        "ESTAが拒否されたらどうすればいい？",
        "ビザの種類を教えてください",  # FAQにない質問
    ]

    print("\n" + "="*60)
    print("FAQ検索テスト")
    print("="*60)

    for query in test_queries:
        print(f"\n質問: {query}")
        print("-" * 60)

        results = searcher.search(query, top_k=3, threshold=0.7)

        if results:
            for i, result in enumerate(results, 1):
                print(f"\n[結果 {i}] 類似度: {result['similarity']:.3f}")
                print(f"FAQ質問: {result['question']}")
                print(f"FAQ回答: {result['answer'][:100]}...")
        else:
            print("→ 該当するFAQが見つかりませんでした（RAG生成が必要）")
