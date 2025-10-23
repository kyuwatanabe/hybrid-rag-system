"""
FAQ管理モジュール

FAQの作成、承認、削除などを管理する統合モジュール
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Optional
import anthropic


class FAQManager:
    """FAQ管理クラス"""

    def __init__(
        self,
        faq_csv_path: str = "faq_database.csv",
        pending_csv_path: str = "pending_faq_approvals.csv",
        claude_api_key: Optional[str] = None
    ):
        """
        FAQManagerの初期化

        Args:
            faq_csv_path: FAQデータベースのCSVファイルパス
            pending_csv_path: 承認待ちFAQのCSVファイルパス
            claude_api_key: Claude APIキー（FAQ生成用）
        """
        self.faq_csv_path = faq_csv_path
        self.pending_csv_path = pending_csv_path
        self.claude_api_key = claude_api_key

        # FAQデータベースの初期化
        if not os.path.exists(faq_csv_path):
            self._create_faq_database()

        # 承認待ちデータベースの初期化
        if not os.path.exists(pending_csv_path):
            self._create_pending_database()

    def _create_faq_database(self):
        """FAQデータベースを新規作成"""
        with open(self.faq_csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'question', 'answer'])
        print(f"[INFO] FAQデータベースを作成しました: {self.faq_csv_path}")

    def _create_pending_database(self):
        """承認待ちデータベースを新規作成"""
        with open(self.pending_csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            fieldnames = ['id', 'timestamp', 'question', 'answer', 'source', 'user_rating', 'status']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        print(f"[INFO] 承認待ちデータベースを作成しました: {self.pending_csv_path}")

    def get_all_faqs(self) -> List[Dict]:
        """
        全FAQを取得

        Returns:
            FAQのリスト
        """
        faqs = []
        try:
            with open(self.faq_csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    faqs.append({
                        'timestamp': row.get('timestamp', ''),
                        'question': row.get('question', '').strip(),
                        'answer': row.get('answer', '').strip()
                    })
        except Exception as e:
            print(f"[ERROR] FAQ読み込みエラー: {e}")
        return faqs

    def get_pending_faqs(self, status: str = 'pending') -> List[Dict]:
        """
        承認待ちFAQを取得

        Args:
            status: ステータス（'pending', 'approved', 'rejected'）

        Returns:
            承認待ちFAQのリスト
        """
        pending_faqs = []
        try:
            with open(self.pending_csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('status', '') == status:
                        pending_faqs.append(row)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[ERROR] 承認待ちFAQ読み込みエラー: {e}")
        return pending_faqs

    def add_faq(self, question: str, answer: str) -> bool:
        """
        FAQを直接追加（承認済みとして）

        Args:
            question: 質問
            answer: 回答

        Returns:
            追加成功/失敗
        """
        try:
            with open(self.faq_csv_path, 'a', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    question,
                    answer
                ])
            print(f"[OK] FAQを追加しました: {question[:50]}...")
            return True
        except Exception as e:
            print(f"[ERROR] FAQ追加エラー: {e}")
            return False

    def add_pending_faq(
        self,
        question: str,
        answer: str,
        source: str = 'RAG',
        user_rating: str = 'positive'
    ) -> bool:
        """
        承認待ちFAQを追加

        Args:
            question: 質問
            answer: 回答
            source: ソース（'RAG', 'Manual'など）
            user_rating: ユーザー評価

        Returns:
            追加成功/失敗
        """
        try:
            # IDを生成
            existing_ids = []
            try:
                with open(self.pending_csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            existing_ids.append(int(row.get('id', 0)))
                        except:
                            pass
            except FileNotFoundError:
                pass

            new_id = max(existing_ids) + 1 if existing_ids else 1

            # 追加
            with open(self.pending_csv_path, 'a', encoding='utf-8-sig', newline='') as f:
                fieldnames = ['id', 'timestamp', 'question', 'answer', 'source', 'user_rating', 'status']
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                # ファイルが空の場合はヘッダーを書く
                if os.path.getsize(self.pending_csv_path) == 0:
                    writer.writeheader()

                writer.writerow({
                    'id': new_id,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'question': question,
                    'answer': answer,
                    'source': source,
                    'user_rating': user_rating,
                    'status': 'pending'
                })

            print(f"[OK] 承認待ちFAQを追加しました (ID: {new_id})")
            return True

        except Exception as e:
            print(f"[ERROR] 承認待ちFAQ追加エラー: {e}")
            return False

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
        try:
            # 承認待ちFAQを読み込み
            pending_faqs = []
            found = False

            with open(self.pending_csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('id') == str(faq_id) and row.get('status') == 'pending':
                        row['question'] = question
                        row['answer'] = answer
                        found = True
                    pending_faqs.append(row)

            if not found:
                print(f"[ERROR] ID {faq_id} の承認待ちFAQが見つかりません")
                return False

            # 承認待ちリストを更新
            with open(self.pending_csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                fieldnames = ['id', 'timestamp', 'question', 'answer', 'source', 'user_rating', 'status']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(pending_faqs)

            print(f"[OK] FAQ ID {faq_id} を更新しました")
            return True

        except Exception as e:
            print(f"[ERROR] FAQ更新エラー: {e}")
            return False

    def approve_pending_faq(self, faq_id: int) -> bool:
        """
        承認待ちFAQを承認してFAQデータベースに追加

        Args:
            faq_id: 承認待ちFAQのID

        Returns:
            承認成功/失敗
        """
        try:
            # 承認待ちFAQを読み込み
            pending_faqs = []
            target_faq = None

            with open(self.pending_csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('id') == str(faq_id) and row.get('status') == 'pending':
                        target_faq = row
                        row['status'] = 'approved'
                    pending_faqs.append(row)

            if not target_faq:
                print(f"[ERROR] ID {faq_id} の承認待ちFAQが見つかりません")
                return False

            # FAQデータベースに追加
            self.add_faq(target_faq['question'], target_faq['answer'])

            # 承認待ちリストを更新
            with open(self.pending_csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                fieldnames = ['id', 'timestamp', 'question', 'answer', 'source', 'user_rating', 'status']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(pending_faqs)

            print(f"[OK] FAQ ID {faq_id} を承認しました")
            return True

        except Exception as e:
            print(f"[ERROR] FAQ承認エラー: {e}")
            return False

    def reject_pending_faq(self, faq_id: int) -> bool:
        """
        承認待ちFAQを拒否

        Args:
            faq_id: 承認待ちFAQのID

        Returns:
            拒否成功/失敗
        """
        try:
            # 承認待ちFAQを読み込み
            pending_faqs = []
            found = False

            with open(self.pending_csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('id') == str(faq_id) and row.get('status') == 'pending':
                        row['status'] = 'rejected'
                        found = True
                    pending_faqs.append(row)

            if not found:
                print(f"[ERROR] ID {faq_id} の承認待ちFAQが見つかりません")
                return False

            # 承認待ちリストを更新
            with open(self.pending_csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                fieldnames = ['id', 'timestamp', 'question', 'answer', 'source', 'user_rating', 'status']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(pending_faqs)

            print(f"[OK] FAQ ID {faq_id} を拒否しました")
            return True

        except Exception as e:
            print(f"[ERROR] FAQ拒否エラー: {e}")
            return False

    def get_stats(self) -> Dict:
        """
        FAQシステムの統計情報を取得

        Returns:
            統計情報の辞書
        """
        stats = {
            'total_faqs': 0,
            'pending_faqs': 0,
            'approved_today': 0,
            'rejected_today': 0
        }

        # 総FAQ数
        try:
            with open(self.faq_csv_path, 'r', encoding='utf-8-sig') as f:
                stats['total_faqs'] = sum(1 for _ in f) - 1  # ヘッダーを除く
        except:
            pass

        # 承認待ち数
        try:
            with open(self.pending_csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                today = datetime.now().strftime('%Y-%m-%d')
                for row in reader:
                    if row.get('status') == 'pending':
                        stats['pending_faqs'] += 1
                    elif row.get('status') == 'approved' and row.get('timestamp', '').startswith(today):
                        stats['approved_today'] += 1
                    elif row.get('status') == 'rejected' and row.get('timestamp', '').startswith(today):
                        stats['rejected_today'] += 1
        except:
            pass

        return stats
