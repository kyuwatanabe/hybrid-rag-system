from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
import json
import datetime
import time
import os
import sys
import threading
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# FAQ system のパスを追加
# FAQ system is now in the same directory
from faq_system import FAQSystem, find_similar_faqs

# ハイブリッドRAGシステムをインポート（同じディレクトリにある）
from hybrid_rag_system import HybridRAGSystem

app = Flask(__name__)

# 既存のFAQシステム（管理画面用に保持）
faq_system_dir = os.path.dirname(__file__)
faq_data_path = os.path.join(faq_system_dir, 'faq_database.csv')  # 承認済みFAQ
faq_system = FAQSystem(faq_data_path)
faq_system.claude_api_key = os.getenv('CLAUDE_API_KEY')
# FAQSystemの作業ディレクトリを明示的に設定
faq_system.pending_file = os.path.join(faq_system_dir, 'pending_qa.csv')
faq_system.unsatisfied_qa_file = os.path.join(faq_system_dir, 'unsatisfied_qa.csv')

# ハイブリッドRAGシステムを初期化（検索用）
print("[INFO] ハイブリッドRAGシステムを初期化中...")
hybrid_rag = HybridRAGSystem(
    faq_csv_path='faq_database.csv',  # 承認済みFAQ
    faq_threshold=0.85,
    claude_api_key=os.getenv('CLAUDE_API_KEY')
)
print("[INFO] ハイブリッドRAGシステム初期化完了")

# FAQ生成の進捗状況を保存するグローバル変数
generation_progress = {
    'current': 0,
    'total': 0,
    'status': 'idle',  # idle, generating, completed, error
    'retry_count': 0,  # 現在のウィンドウリトライ回数
    'max_retries': 10,  # 最大リトライ回数（ウィンドウごと）
    'excluded_windows': 0,  # 除外されたウィンドウ数
    'total_windows': 0,  # 総ウィンドウ数
    'positions_list': [],  # 成功した位置のリスト（累積）
    'current_trying_position': '',  # 現在試行中の位置
    'logs': [],  # 最新10件のログメッセージ
    'start_time': None,  # 生成開始時刻
    'last_update_time': None,  # 最終更新時刻
    'elapsed_time': 0,  # 経過時間（秒）
    'generation_speed': 0,  # 生成速度（FAQ/秒）
    'average_speed': 0,  # 平均速度（FAQ/秒）
    'time_per_faq': 0,  # FAQ1件あたりの平均時間（秒）
    'generated_faqs_list': []  # 生成されたFAQのリスト（質問と位置）
}

# 自動バックアップ関数
def create_auto_backup(reason="manual"):
    """
    自動バックアップを作成
    Args:
        reason: バックアップの理由（例: "approval", "delete", "edit", "manual"）
    """
    import zipfile
    import io
    import shutil
    from datetime import datetime

    try:
        # backupsディレクトリを確認・作成
        backup_dir = 'backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # タイムスタンプとバックアップファイル名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'auto_backup_{timestamp}_{reason}.zip'
        backup_path = os.path.join(backup_dir, backup_filename)

        # ZIPファイルを作成
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # FAQ データを追加
            if os.path.exists(faq_system.csv_file):
                zip_file.write(faq_system.csv_file, os.path.basename(faq_system.csv_file))

            # 承認待ちデータを追加
            if os.path.exists('pending_qa.csv'):
                zip_file.write('pending_qa.csv', 'pending_qa.csv')

            # 不満足データを追加（あれば）
            if os.path.exists('unsatisfied_qa.csv'):
                zip_file.write('unsatisfied_qa.csv', 'unsatisfied_qa.csv')

        print(f"[BACKUP] 自動バックアップ作成: {backup_filename}")

        # 古いバックアップを削除（最新100個だけ保持）
        cleanup_old_backups(backup_dir, keep_count=100)

        return backup_path

    except Exception as e:
        print(f"[BACKUP ERROR] バックアップ作成エラー: {e}")
        import traceback
        traceback.print_exc()
        return None

def cleanup_old_backups(backup_dir, keep_count=20):
    """
    古いバックアップファイルを削除
    Args:
        backup_dir: バックアップディレクトリ
        keep_count: 保持するバックアップファイル数
    """
    try:
        # バックアップファイル一覧を取得
        backup_files = [
            f for f in os.listdir(backup_dir)
            if f.startswith('auto_backup_') and f.endswith('.zip')
        ]

        # ファイル作成日時でソート（新しい順）
        backup_files.sort(key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)), reverse=True)

        # 古いファイルを削除
        for old_file in backup_files[keep_count:]:
            old_path = os.path.join(backup_dir, old_file)
            os.remove(old_path)
            print(f"[BACKUP] 古いバックアップ削除: {old_file}")

    except Exception as e:
        print(f"[BACKUP ERROR] バックアップクリーンアップエラー: {e}")

@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """FAQ検索API（ハイブリッドRAGシステム使用）"""
    data = request.get_json()
    question = data.get('question', '').strip()

    if not question:
        return jsonify({'error': '質問を入力してください'}), 400

    try:
        # ハイブリッドRAGシステムで回答を取得（FAQ優先、なければRAG生成）
        result = hybrid_rag.answer_question(question)

        # 回答ソースに応じてレスポンスを構築
        if result['source'] == 'FAQ':
            # FAQから回答が見つかった場合
            return jsonify({
                'needs_confirmation': False,
                'answer': result['answer'],
                'matched_question': result.get('faq_question', ''),
                'source': 'FAQ',
                'similarity': result.get('similarity', 0)
            })
        else:
            # RAGで回答を生成した場合
            return jsonify({
                'needs_confirmation': False,
                'answer': result['answer'],
                'matched_question': None,
                'source': 'RAG',
                'num_sources': result.get('num_sources', 0)
            })

    except Exception as e:
        print(f"[ERROR] ハイブリッドRAG検索エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'検索エラーが発生しました: {str(e)}'}), 500

@app.route('/admin/backup')
def backup_page():
    """バックアップ管理ページ"""
    # バックアップ一覧を取得
    backup_dir = 'backups'
    backup_files = []

    try:
        if os.path.exists(backup_dir):
            files = [f for f in os.listdir(backup_dir) if f.endswith('.zip')]
            for filename in files:
                filepath = os.path.join(backup_dir, filename)
                file_stat = os.stat(filepath)

                # ファイル名から情報を抽出（例: auto_backup_20250128_133045_approval.zip）
                parts = filename.replace('.zip', '').split('_')
                reason = parts[-1] if len(parts) >= 4 else 'unknown'

                # 理由の日本語化
                reason_map = {
                    'approval': 'FAQ承認',
                    'edit': 'FAQ編集',
                    'delete': 'FAQ削除',
                    'reject': 'FAQ却下',
                    'edit_pending': '承認待ち編集',
                    'manual': '手動バックアップ'
                }
                reason_ja = reason_map.get(reason, reason)

                backup_files.append({
                    'filename': filename,
                    'size': file_stat.st_size,
                    'created_at': datetime.datetime.fromtimestamp(file_stat.st_mtime),
                    'reason': reason_ja
                })

            # 作成日時で降順ソート（新しい順）
            backup_files.sort(key=lambda x: x['created_at'], reverse=True)
    except Exception as e:
        print(f"[ERROR] バックアップ一覧取得エラー: {e}")

    return render_template('backup.html', backup_files=backup_files)

@app.route('/admin')
def admin():
    """管理画面"""
    try:
        # 最新データを再読み込み
        faq_system.load_faq_data(faq_system.csv_file)
        faqs = faq_system.faq_data
        print(f"[DEBUG] 管理画面: FAQデータ件数 = {len(faqs)}")
        print(f"[DEBUG] 最初の3件: {[faq.get('question', '')[:30] for faq in faqs[:3]]}")
        response = make_response(render_template('admin.html', faqs=faqs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] 管理画面エラー: {e}")
        print(error_details)
        return f"<h1>エラー</h1><pre>{error_details}</pre>", 500

@app.route('/admin/add_faq')
def add_faq_page():
    """FAQ追加画面"""
    return render_template('add_faq.html')

@app.route('/admin/auto_generate_faq')
def auto_generate_faq_page():
    """FAQ自動生成画面"""
    return render_template('auto_generate_faq.html')

@app.route('/admin/add', methods=['POST'])
def add_faq():
    """FAQ追加"""
    question = request.form.get('question', '').strip()
    answer = request.form.get('answer', '').strip()
    category = request.form.get('category', '一般').strip()

    if question and answer:
        faq_system.add_faq(question, answer, category=category)
        faq_system.save_faq_data()

    return redirect(url_for('add_faq_page') + '?success=true')

@app.route('/admin/edit/<int:index>', methods=['POST'])
def edit_faq(index):
    """FAQ編集"""
    question = request.form.get('question', '').strip()
    answer = request.form.get('answer', '').strip()
    category = request.form.get('category', '').strip()

    if faq_system.edit_faq(index, question if question else None, answer if answer else None, category if category else None):
        faq_system.save_faq_data()
        # 自動バックアップを作成
        create_auto_backup(reason="edit")

    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:index>', methods=['POST'])
def delete_faq(index):
    """FAQ削除"""
    faq_system.delete_faq(index)
    faq_system.save_faq_data()
    # 自動バックアップを作成
    create_auto_backup(reason="delete")
    return redirect(url_for('admin'))

@app.route('/admin/export_all', methods=['GET'])
def export_all():
    """全データ（FAQ + 承認待ち）をZIPでエクスポート"""
    import io
    import zipfile
    from datetime import datetime
    import shutil
    import os

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 一時的なメモリ上のZIPファイルを作成
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # FAQ データを追加
        if os.path.exists(faq_system.csv_file):
            zip_file.write(faq_system.csv_file, os.path.basename(faq_system.csv_file))

        # 承認待ちデータを追加
        if os.path.exists('pending_qa.csv'):
            zip_file.write('pending_qa.csv', 'pending_qa.csv')

        # 不満足データを追加（あれば）
        if os.path.exists('unsatisfied_qa.csv'):
            zip_file.write('unsatisfied_qa.csv', 'unsatisfied_qa.csv')

    zip_buffer.seek(0)

    response = make_response(zip_buffer.read())
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = f'attachment; filename=faq_system_backup_{timestamp}.zip'

    return response

@app.route('/admin/export_pending', methods=['GET'])
def export_pending_faq():
    """承認待ちFAQデータをCSVとしてエクスポート"""
    import io
    from datetime import datetime

    # 最新データを再読み込み
    faq_system.load_pending_qa()

    # CSVデータを作成
    output = io.StringIO()
    import csv
    writer = csv.DictWriter(output, fieldnames=['id', 'question', 'answer', 'keywords', 'category', 'created_at', 'user_question', 'confirmation_request'])
    writer.writeheader()
    for pending in faq_system.pending_qa:
        writer.writerow({
            'id': pending.get('id', ''),
            'question': pending.get('question', ''),
            'answer': pending.get('answer', ''),
            'keywords': pending.get('keywords', ''),
            'category': pending.get('category', '一般'),
            'created_at': pending.get('created_at', ''),
            'user_question': pending.get('user_question', ''),
            'confirmation_request': pending.get('confirmation_request', '0')
        })

    # レスポンスを作成（BOM付きUTF-8）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_content = '\ufeff' + output.getvalue()  # BOMを先頭に追加
    response = make_response(csv_content.encode('utf-8'))
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=pending_faq_backup_{timestamp}.csv'

    return response

@app.route('/admin/import_all', methods=['POST'])
def import_all():
    """ZIPファイルから全データをインポート"""
    import zipfile
    import os
    import shutil

    # ファイルアップロードの確認
    if 'backup_file' not in request.files:
        return redirect(url_for('backup_page') + '?error=no_file')

    file = request.files['backup_file']
    if file.filename == '':
        return redirect(url_for('backup_page') + '?error=no_file')

    if not file.filename.lower().endswith('.zip'):
        return redirect(url_for('backup_page') + '?error=invalid_file')

    try:
        # 一時ファイルに保存
        import tempfile
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'backup.zip')
        file.save(zip_path)

        # ZIPファイルを解凍
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # 各CSVファイルを復元
        restored_files = []

        # FAQデータ（古いファイル名も考慮）
        faq_file_new = os.path.join(temp_dir, os.path.basename(faq_system.csv_file))
        faq_file_old = os.path.join(temp_dir, 'faq_data-1.csv')
        if os.path.exists(faq_file_new):
            shutil.copy(faq_file_new, faq_system.csv_file)
            restored_files.append('FAQ')
        elif os.path.exists(faq_file_old):
            shutil.copy(faq_file_old, faq_system.csv_file)
            restored_files.append('FAQ')

        # 承認待ちデータ
        pending_file = os.path.join(temp_dir, 'pending_qa.csv')
        if os.path.exists(pending_file):
            shutil.copy(pending_file, 'pending_qa.csv')
            restored_files.append('承認待ち')

        # 不満足データ
        unsatisfied_file = os.path.join(temp_dir, 'unsatisfied_qa.csv')
        if os.path.exists(unsatisfied_file):
            shutil.copy(unsatisfied_file, 'unsatisfied_qa.csv')
            restored_files.append('不満足')

        # 一時ファイルを削除
        shutil.rmtree(temp_dir)

        # データを再読み込み
        faq_system.load_faq_data(faq_system.csv_file)
        faq_system.load_pending_qa()

        restored_str = '、'.join(restored_files)
        print(f"[DEBUG] バックアップ復元完了: {restored_str}")

        return redirect(url_for('backup_page') + f'?success=restore&files={len(restored_files)}')

    except Exception as e:
        print(f"[ERROR] バックアップ復元エラー: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('backup_page') + '?error=restore_failed')

@app.route('/admin/restore_from_backup/<filename>', methods=['POST'])
def restore_from_backup(filename):
    """バックアップディレクトリから直接復元"""
    import zipfile
    import shutil
    import tempfile

    try:
        backup_path = os.path.join('backups', filename)

        # バックアップファイルの存在確認
        if not os.path.exists(backup_path):
            return redirect(url_for('backup_page') + '?error=file_not_found')

        # 一時ディレクトリを作成
        temp_dir = tempfile.mkdtemp()

        # ZIPファイルを解凍
        with zipfile.ZipFile(backup_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # 各CSVファイルを復元
        restored_files = []

        # FAQデータ（古いファイル名も考慮）
        faq_file_new = os.path.join(temp_dir, os.path.basename(faq_system.csv_file))
        faq_file_old = os.path.join(temp_dir, 'faq_data-1.csv')
        if os.path.exists(faq_file_new):
            shutil.copy(faq_file_new, faq_system.csv_file)
            restored_files.append('FAQ')
        elif os.path.exists(faq_file_old):
            shutil.copy(faq_file_old, faq_system.csv_file)
            restored_files.append('FAQ')

        # 承認待ちデータ
        pending_file = os.path.join(temp_dir, 'pending_qa.csv')
        if os.path.exists(pending_file):
            shutil.copy(pending_file, 'pending_qa.csv')
            restored_files.append('承認待ち')

        # 不満足データ
        unsatisfied_file = os.path.join(temp_dir, 'unsatisfied_qa.csv')
        if os.path.exists(unsatisfied_file):
            shutil.copy(unsatisfied_file, 'unsatisfied_qa.csv')
            restored_files.append('不満足')

        # 一時ファイルを削除
        shutil.rmtree(temp_dir)

        # データを再読み込み
        faq_system.load_faq_data(faq_system.csv_file)
        faq_system.load_pending_qa()

        # ハイブリッドRAGシステムをリロード
        hybrid_rag.reload_faqs_to_rag()

        restored_str = '、'.join(restored_files)
        print(f"[BACKUP] バックアップから復元完了: {filename} ({restored_str})")

        return redirect(url_for('backup_page') + f'?success=restore&files={len(restored_files)}')

    except Exception as e:
        print(f"[BACKUP ERROR] バックアップ復元エラー: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('backup_page') + '?error=restore_failed')

@app.route('/admin/batch_delete', methods=['POST'])
def batch_delete_faq():
    """複数のFAQをまとめて削除"""
    print(f"[DEBUG] 受信したフォームデータ全体: {dict(request.form)}")
    print(f"[DEBUG] request.form.getlist('faq_indices'): {request.form.getlist('faq_indices')}")
    print(f"[DEBUG] request.form.keys(): {list(request.form.keys())}")

    faq_indices = request.form.getlist('faq_indices')

    if not faq_indices:
        print("[DEBUG] まとめて削除: 選択されたFAQがありません")
        return redirect(url_for('admin'))

    # 最新データを再読み込み
    faq_system.load_faq_data(faq_system.csv_file)

    # インデックスを降順にソートして削除（大きい方から削除しないとインデックスがずれる）
    indices = sorted([int(idx) for idx in faq_indices], reverse=True)

    print(f"[DEBUG] まとめて削除開始 - 対象インデックス: {indices}")
    print(f"[DEBUG] 削除前のFAQ件数: {len(faq_system.faq_data)}")

    success_count = 0
    for idx in indices:
        try:
            if 0 <= idx < len(faq_system.faq_data):
                deleted_question = faq_system.faq_data[idx].get('question', '')[:30]
                faq_system.delete_faq(idx)
                success_count += 1
                print(f"[DEBUG] FAQ削除成功: インデックス {idx} - {deleted_question}")
            else:
                print(f"[DEBUG] FAQ削除スキップ: インデックス {idx} は範囲外")
        except Exception as e:
            print(f"[DEBUG] FAQ削除失敗: インデックス {idx}, エラー: {e}")

    faq_system.save_faq_data()
    # 削除後に最新データを再読み込み
    faq_system.load_faq_data(faq_system.csv_file)
    print(f"[DEBUG] 削除後のFAQ件数: {len(faq_system.faq_data)}")
    print(f"[DEBUG] まとめて削除完了 - 成功: {success_count}件")
    return redirect(url_for('admin'))

@app.route('/interactive_improvement')
def interactive_improvement():
    """対話的改善画面"""
    return render_template('interactive_improvement.html')

@app.route('/admin/review')
def review_pending():
    """承認待ちQ&A一覧"""
    # 最新データを再読み込み
    faq_system.load_pending_qa()
    pending_items = faq_system.pending_qa
    print(f"[DEBUG] 承認待ち画面: 承認待ちアイテム数 = {len(pending_items)}")
    return render_template('review_pending.html', pending_items=pending_items)

@app.route('/admin/approve/<qa_id>', methods=['POST'])
def approve_qa(qa_id):
    """Q&Aを承認してFAQに追加"""
    if faq_system.approve_pending_qa(qa_id):
        faq_system.save_faq_data()
        print(f"[DEBUG] Q&A承認成功: {qa_id}")

        # 自動バックアップを作成
        create_auto_backup(reason="approval")

        # faq_database.csvを更新（検索用）
        import csv
        faq_data_list = []
        # faq_data.csvから読み込み
        faq_file = os.path.join(faq_system_dir, 'faq_data.csv')
        if os.path.exists(faq_file):
            with open(faq_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('question', '').strip():
                        faq_data_list.append(row)
        # pending_qa.csvから読み込み
        pending_file = os.path.join(os.path.dirname(__file__), 'pending_qa.csv')
        if os.path.exists(pending_file):
            with open(pending_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('question', '').strip():
                        faq_data_list.append(row)
        # faq_database.csvに保存
        faq_db_file = os.path.join(os.path.dirname(__file__), 'faq_database.csv')
        with open(faq_db_file, 'w', encoding='utf-8', newline='') as f:
            if faq_data_list:
                fieldnames = ['id', 'question', 'answer', 'keywords', 'category', 'created_at']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for faq in faq_data_list:
                    writer.writerow({
                        'id': faq.get('id', ''),
                        'question': faq.get('question', ''),
                        'answer': faq.get('answer', ''),
                        'keywords': faq.get('keywords', ''),
                        'category': faq.get('category', ''),
                        'created_at': faq.get('created_at', '')
                    })
        print(f"[DEBUG] faq_database.csv更新完了: {len(faq_data_list)}件")

        # ハイブリッドRAGシステムをリロード
        hybrid_rag.reload_faqs_to_rag()
        print(f"[DEBUG] ハイブリッドRAGシステムのFAQデータをリロードしました")
    else:
        print(f"[DEBUG] Q&A承認失敗: {qa_id}")
    return redirect(url_for('review_pending'))

@app.route('/admin/reject/<qa_id>', methods=['POST'])
def reject_qa(qa_id):
    """Q&Aを却下"""
    if faq_system.reject_pending_qa(qa_id):
        print(f"[DEBUG] Q&A却下成功: {qa_id}")
        # 自動バックアップを作成
        create_auto_backup(reason="reject")
    else:
        print(f"[DEBUG] Q&A却下失敗: {qa_id}")
    return redirect(url_for('review_pending'))

@app.route('/admin/mark_question_ng/<qa_id>', methods=['POST'])
def mark_question_ng(qa_id):
    """質問をNG登録（不適切な質問として学習、FAQは残す）"""
    import re
    from datetime import datetime

    try:
        # 承認待ちQ&Aを取得
        faq_system.load_pending_qa()
        pending_item = None
        for item in faq_system.pending_qa:
            if item['id'] == qa_id:
                pending_item = item
                break

        if not pending_item:
            print(f"[DEBUG] 質問NG登録失敗: アイテムが見つかりません - {qa_id}")
            return redirect(url_for('review_pending'))

        # window_info から位置を抽出
        window_info = pending_item.get('window_info', '')
        window_position = None
        if window_info:
            match = re.search(r'位置:\s*(\d+)', window_info)
            if match:
                window_position = int(match.group(1))

        print(f"[DEBUG] 質問NG登録 - ID: {qa_id}")
        print(f"[DEBUG] NG質問: {pending_item['question']}")

        # rejected_patterns.csv に記録（type=question）
        rejected_file = 'rejected_patterns.csv'
        import csv
        with open(rejected_file, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                pending_item.get('question', ''),
                pending_item.get('answer', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                window_position if window_position else '',
                '',  # chunk_textは空
                'question'  # type
            ])
        print(f"[DEBUG] rejected_patterns.csv に記録しました（type=question）")

        # バックアップ作成（FAQは削除しない）
        create_auto_backup(reason="mark_question_ng")

        return redirect(url_for('review_pending'))

    except Exception as e:
        print(f"[ERROR] 質問NG登録処理でエラー: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('review_pending'))

@app.route('/admin/mark_answer_ng/<qa_id>', methods=['POST'])
def mark_answer_ng(qa_id):
    """回答をNG登録（不適切な回答として学習、FAQは残す）"""
    import re
    from datetime import datetime

    try:
        # 承認待ちQ&Aを取得
        faq_system.load_pending_qa()
        pending_item = None
        for item in faq_system.pending_qa:
            if item['id'] == qa_id:
                pending_item = item
                break

        if not pending_item:
            print(f"[DEBUG] 回答NG登録失敗: アイテムが見つかりません - {qa_id}")
            return redirect(url_for('review_pending'))

        # window_info から位置を抽出
        window_info = pending_item.get('window_info', '')
        window_position = None
        if window_info:
            match = re.search(r'位置:\s*(\d+)', window_info)
            if match:
                window_position = int(match.group(1))

        print(f"[DEBUG] 回答NG登録 - ID: {qa_id}")
        print(f"[DEBUG] 質問: {pending_item['question']}")
        print(f"[DEBUG] NG回答: {pending_item['answer'][:50]}...")

        # rejected_patterns.csv に記録（type=answer）
        rejected_file = 'rejected_patterns.csv'
        import csv
        with open(rejected_file, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                pending_item.get('question', ''),
                pending_item.get('answer', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                window_position if window_position else '',
                '',  # chunk_textは空
                'answer'  # type
            ])
        print(f"[DEBUG] rejected_patterns.csv に記録しました（type=answer）")

        # バックアップ作成（FAQは削除しない）
        create_auto_backup(reason="mark_answer_ng")

        return redirect(url_for('review_pending'))

    except Exception as e:
        print(f"[ERROR] 回答NG登録処理でエラー: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('review_pending'))

@app.route('/admin/rejected_patterns')
def rejected_patterns_page():
    """NGデータ管理画面"""
    import csv
    import os

    rejected_patterns = []
    rejected_file = 'rejected_patterns.csv'

    try:
        if os.path.exists(rejected_file):
            with open(rejected_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rejected_patterns.append(row)
    except Exception as e:
        print(f"[ERROR] rejected_patterns.csv 読み込みエラー: {e}")

    # 新しい順にソート
    rejected_patterns.reverse()

    return render_template('rejected_patterns.html', rejected_patterns=rejected_patterns)

@app.route('/admin/delete_rejected_pattern/<int:index>', methods=['POST'])
def delete_rejected_pattern(index):
    """NGパターンを削除"""
    import csv
    import os

    rejected_file = 'rejected_patterns.csv'

    try:
        # 全データを読み込み
        all_patterns = []
        if os.path.exists(rejected_file):
            with open(rejected_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                all_patterns = list(reader)

        # 指定されたインデックスを削除（逆順で表示しているので調整）
        actual_index = len(all_patterns) - 1 - index
        if 0 <= actual_index < len(all_patterns):
            deleted_item = all_patterns.pop(actual_index)
            print(f"[DEBUG] NGパターン削除: {deleted_item.get('question', '')[:30]}...")

            # ファイルに書き戻し
            with open(rejected_file, 'w', encoding='utf-8', newline='') as f:
                if all_patterns:
                    fieldnames = ['question', 'answer', 'rejected_at', 'window_position', 'chunk_text', 'type']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_patterns)
                else:
                    # 空の場合はヘッダーのみ
                    f.write('question,answer,rejected_at,window_position,chunk_text,type\n')

            create_auto_backup(reason="delete_rejected_pattern")
    except Exception as e:
        print(f"[ERROR] NGパターン削除エラー: {e}")
        import traceback
        traceback.print_exc()

    return redirect(url_for('rejected_patterns_page'))

@app.route('/admin/batch_delete_rejected_patterns', methods=['POST'])
def batch_delete_rejected_patterns():
    """複数のNGパターンをまとめて削除"""
    import csv
    import os

    ng_indices = request.form.getlist('ng_indices')
    rejected_file = 'rejected_patterns.csv'

    try:
        if not ng_indices:
            print("[DEBUG] まとめて削除: 選択されたNGパターンがありません")
            return redirect(url_for('rejected_patterns_page'))

        # 全データを読み込み
        all_patterns = []
        if os.path.exists(rejected_file):
            with open(rejected_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                all_patterns = list(reader)

        # インデックスを降順にソートして削除（大きい方から削除しないとインデックスがずれる）
        indices = sorted([int(idx) for idx in ng_indices], reverse=True)

        # 逆順で表示しているので実際のインデックスを計算
        actual_indices = [len(all_patterns) - 1 - idx for idx in indices]
        actual_indices.sort(reverse=True)

        print(f"[DEBUG] まとめて削除開始 - 対象インデックス: {actual_indices}")
        print(f"[DEBUG] 削除前のNGパターン数: {len(all_patterns)}")

        success_count = 0
        for idx in actual_indices:
            if 0 <= idx < len(all_patterns):
                deleted_item = all_patterns.pop(idx)
                success_count += 1
                print(f"[DEBUG] NGパターン削除: {deleted_item.get('question', '')[:30]}...")

        # ファイルに書き戻し
        with open(rejected_file, 'w', encoding='utf-8', newline='') as f:
            if all_patterns:
                fieldnames = ['question', 'answer', 'rejected_at', 'window_position', 'chunk_text', 'type']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_patterns)
            else:
                # 空の場合はヘッダーのみ
                f.write('question,answer,rejected_at,window_position,chunk_text,type\n')

        print(f"[DEBUG] 削除後のNGパターン数: {len(all_patterns)}")
        print(f"[DEBUG] まとめて削除完了 - 成功: {success_count}件")

        create_auto_backup(reason="batch_delete_rejected_patterns")

    except Exception as e:
        print(f"[ERROR] NGパターン一括削除エラー: {e}")
        import traceback
        traceback.print_exc()

    return redirect(url_for('rejected_patterns_page'))

@app.route('/admin/batch_reject', methods=['POST'])
def batch_reject_qa():
    """複数のQ&Aをまとめて却下"""
    qa_ids = request.form.getlist('qa_ids')

    if not qa_ids:
        print("[DEBUG] まとめて却下: 選択されたQ&Aがありません")
        return redirect(url_for('review_pending'))

    success_count = 0
    fail_count = 0

    for qa_id in qa_ids:
        if faq_system.reject_pending_qa(qa_id):
            success_count += 1
            print(f"[DEBUG] Q&A却下成功: {qa_id}")
        else:
            fail_count += 1
            print(f"[DEBUG] Q&A却下失敗: {qa_id}")

    print(f"[DEBUG] まとめて却下完了 - 成功: {success_count}, 失敗: {fail_count}")
    return redirect(url_for('review_pending'))

@app.route('/admin/edit_pending/<qa_id>', methods=['POST'])
def edit_pending_qa(qa_id):
    """承認待ちQ&Aを編集"""
    question = request.form.get('question', '').strip()
    answer = request.form.get('answer', '').strip()
    keywords = request.form.get('keywords', '').strip()
    category = request.form.get('category', '').strip()

    if faq_system.edit_pending_qa(qa_id, question, answer, keywords, category):
        print(f"[DEBUG] 承認待ちQ&A編集成功: {qa_id}")
        # 自動バックアップを作成
        create_auto_backup(reason="edit_pending")
    else:
        print(f"[DEBUG] 承認待ちQ&A編集失敗: {qa_id}")

    return redirect(url_for('check_duplicates', qa_id=qa_id))

@app.route('/admin/toggle_confirmation_request/<qa_id>', methods=['POST'])
def toggle_confirmation_request(qa_id):
    """承認待ちFAQの確認依頼フラグを切り替え"""
    if faq_system.toggle_confirmation_request(qa_id):
        print(f"[DEBUG] 確認依頼切り替え成功: {qa_id}")
    else:
        print(f"[DEBUG] 確認依頼切り替え失敗: {qa_id}")

    return redirect(url_for('check_duplicates', qa_id=qa_id))

@app.route('/admin/check_duplicates/<qa_id>')
def check_duplicates(qa_id):
    """承認待ちQ&Aの重複チェック"""
    try:
        # 承認待ちQ&Aを取得
        faq_system.load_pending_qa()
        pending_item = None
        for item in faq_system.pending_qa:
            if item['id'] == qa_id:
                pending_item = item
                break

        if not pending_item:
            print(f"[DEBUG] 承認待ちアイテムが見つかりません: {qa_id}")
            return redirect(url_for('review_pending'))

        # 類似FAQ検索
        faq_system.load_faq_data(faq_system.csv_file)
        similar_faqs = find_similar_faqs(faq_system, pending_item['question'])

        print(f"[DEBUG] 重複チェック - 質問: {pending_item['question']}")
        print(f"[DEBUG] 類似FAQ数: {len(similar_faqs)}")

        return render_template('check_duplicates.html',
                             pending_item=pending_item,
                             similar_faqs=similar_faqs)
    except Exception as e:
        print(f"[ERROR] 重複チェックでエラー: {e}")
        import traceback
        traceback.print_exc()
        return f"エラーが発生しました: {e}", 500

@app.route('/admin/generation_progress', methods=['GET'])
def get_generation_progress():
    """FAQ生成の進捗状況を取得"""
    return jsonify(generation_progress)

@app.route('/admin/get_duplicates', methods=['GET'])
def get_duplicate_faqs():
    """重複判定されたFAQのリストを取得（デバッグ用）"""
    return jsonify({
        'duplicates': faq_system.duplicate_faqs,
        'total': len(faq_system.duplicate_faqs)
    })

@app.route('/admin/clear_duplicates', methods=['POST'])
def clear_duplicate_faqs():
    """重複FAQリストをクリア（デバッグ用）"""
    faq_system.duplicate_faqs = []
    print("[DEBUG] 重複FAQリストをクリアしました")
    return jsonify({'success': True, 'message': '重複FAQリストをクリアしました'})

@app.route('/admin/interrupt_generation', methods=['POST'])
def interrupt_generation():
    """FAQ生成を中断"""
    faq_system.generation_interrupted = True
    generation_progress['status'] = 'interrupted'
    print("[INFO] FAQ生成の中断リクエストを受信")
    return jsonify({'success': True, 'message': 'FAQ生成を中断しました'})

@app.route('/admin/auto_generate', methods=['POST'])
def auto_generate_faqs():
    """FAQ自動生成API"""
    import sys
    import os
    from datetime import datetime

    # ファイルベースのデバッグログ（stdoutが見えない場合の対策）
    debug_log_path = os.path.join(os.path.dirname(__file__), 'debug_faq_generation.log')
    def log_debug(message):
        try:
            with open(debug_log_path, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {message}\n")
                f.flush()
        except Exception as e:
            print(f"[ERROR] Failed to write debug log: {e}")

    log_debug("=" * 60)
    log_debug("auto_generate_faqs関数が呼び出されました")
    print("[DEBUG] auto_generate_faqs関数が呼び出されました", flush=True)
    sys.stdout.flush()

    try:
        # デバッグモード: 米国ビザ申請の手引きVer.21..pdfを固定で使用
        DEBUG_MODE = True
        log_debug(f"DEBUG_MODE = {DEBUG_MODE}")
        print(f"[DEBUG] DEBUG_MODE = {DEBUG_MODE}")

        if DEBUG_MODE:
            log_debug("デバッグモード: 米国ビザ申請の手引きVer.21..pdfを使用")
            print("[DEBUG] デバッグモード: 米国ビザ申請の手引きVer.21..pdfを使用")
            pdf_path = os.path.join(os.path.dirname(__file__), '米国ビザ申請の手引きVer.21..pdf')
            num_questions = int(request.form.get('num_questions', 10))
            category = 'AI生成'

            log_debug(f"PDF path: {pdf_path}")
            log_debug(f"PDF exists: {os.path.exists(pdf_path)}")
            log_debug(f"Num questions: {num_questions}")
            log_debug(f"Category: {category}")

            if not os.path.exists(pdf_path):
                error_msg = f'デバッグ用PDFが見つかりません: {pdf_path}'
                log_debug(f"ERROR: {error_msg}")
                return jsonify({'success': False, 'message': error_msg})

            log_debug(f"FAQ自動生成開始 - ファイル: 米国ビザ申請の手引きVer.21..pdf, 数: {num_questions}")
            print(f"[DEBUG] FAQ自動生成開始 - ファイル: 米国ビザ申請の手引きVer.21..pdf, 数: {num_questions}")

            # 進捗状況を初期化
            generation_progress['current'] = 0
            generation_progress['total'] = num_questions
            generation_progress['status'] = 'generating'
            generation_progress['retry_count'] = 0
            generation_progress['max_retries'] = 10  # ウィンドウごとの最大リトライ回数
            generation_progress['excluded_windows'] = 0
            generation_progress['total_windows'] = 0
            generation_progress['positions_list'] = []  # 成功した位置のリスト
            generation_progress['rejected_positions'] = []  # 拒否された位置のリスト（赤字表示用）
            generation_progress['current_trying_position'] = ''  # 現在試行中の位置
            generation_progress['start_time'] = time.time()  # 生成開始時刻を記録
            generation_progress['last_update_time'] = time.time()
            generation_progress['elapsed_time'] = 0
            generation_progress['generation_speed'] = 0
            generation_progress['average_speed'] = 0
            generation_progress['time_per_faq'] = 0
            generation_progress['generated_faqs_list'] = []  # 生成されたFAQリストを初期化

            # 中断フラグをリセット
            faq_system.generation_interrupted = False

            # 進捗更新用コールバックを設定
            def update_progress(current, total, retry_count=0, excluded_windows=0, total_windows=0, question_range='', answer_range='', current_position='', rejected_position=''):
                current_time = time.time()
                generation_progress['current'] = current
                generation_progress['total'] = total
                generation_progress['status'] = 'generating'
                generation_progress['retry_count'] = retry_count
                generation_progress['excluded_windows'] = excluded_windows
                generation_progress['total_windows'] = total_windows

                # 現在試行中の位置を常に記録（リアルタイム表示用）
                generation_progress['current_trying_position'] = current_position

                # FAQ生成成功時（retry_count == 0）のみ位置をリストに追加
                if retry_count == 0 and current_position and current_position not in generation_progress['positions_list']:
                    generation_progress['positions_list'].append(current_position)

                # 拒否された位置を記録（赤字表示用）
                if rejected_position and rejected_position not in generation_progress['rejected_positions']:
                    generation_progress['rejected_positions'].append(rejected_position)

                generation_progress['last_update_time'] = current_time

                # 経過時間を計算
                if generation_progress['start_time']:
                    generation_progress['elapsed_time'] = current_time - generation_progress['start_time']

                    # 生成速度を計算（現在の件数 / 経過時間）
                    if current > 0 and generation_progress['elapsed_time'] > 0:
                        generation_progress['average_speed'] = current / generation_progress['elapsed_time']
                        generation_progress['time_per_faq'] = generation_progress['elapsed_time'] / current

                print(f"[DEBUG] 進捗更新: {current}/{total}, 経過時間: {generation_progress['elapsed_time']:.1f}秒, 平均速度: {generation_progress['average_speed']:.2f} FAQ/秒, ウィンドウリトライ: {retry_count}, 除外ウィンドウ: {excluded_windows}/{total_windows}, 位置リスト: {', '.join(generation_progress['positions_list'])}, 試行中: {current_position}")

            faq_system.progress_callback = update_progress

            # バックグラウンドスレッドでFAQ生成を実行
            def generate_in_background():
                log_debug("--- バックグラウンドスレッド開始 ---")
                try:
                    log_debug("バックグラウンドスレッドでFAQ生成開始")
                    print("[DEBUG] バックグラウンドスレッドでFAQ生成開始")
                    log_debug(f"PDF path: {pdf_path}")
                    log_debug(f"PDF exists: {os.path.exists(pdf_path)}")
                    log_debug(f"Num questions: {num_questions}")
                    log_debug(f"Category: {category}")
                    print(f"[DEBUG] PDF path: {pdf_path}")
                    print(f"[DEBUG] PDF exists: {os.path.exists(pdf_path)}")
                    print(f"[DEBUG] Num questions: {num_questions}")
                    print(f"[DEBUG] Category: {category}")

                    log_debug("generate_faqs_from_document呼び出し前")
                    log_debug(f"faq_system.claude_api_key is set: {faq_system.claude_api_key is not None}")
                    if faq_system.claude_api_key:
                        log_debug(f"API key starts: {faq_system.claude_api_key[:15]}...")

                    # FAQSystemにログ関数を渡す（内部でログを記録できるように）
                    original_print = print
                    def intercepted_print(*args, **kwargs):
                        message = ' '.join(str(arg) for arg in args)
                        log_debug(f"[faq_system] {message}")
                        original_print(*args, **kwargs)

                    # 一時的にprintを置き換え
                    import builtins
                    builtins.print = intercepted_print

                    try:
                        generated_faqs = faq_system.generate_faqs_from_document(pdf_path, num_questions, category)
                        log_debug(f"generate_faqs_from_document呼び出し後: {len(generated_faqs)} FAQs生成")
                        print(f"[DEBUG] FAQ generation completed, generated: {len(generated_faqs)} FAQs")
                    finally:
                        # printを元に戻す
                        builtins.print = original_print

                    # 生成完了（中断された場合もFAQがあれば保存）
                    if faq_system.generation_interrupted:
                        generation_progress['status'] = 'interrupted'
                        print(f"[DEBUG] FAQ生成が中断されました（生成済み: {len(generated_faqs)}件）")
                    else:
                        generation_progress['status'] = 'completed'

                    if not generated_faqs:
                        generation_progress['status'] = 'error' if not faq_system.generation_interrupted else 'interrupted'
                        print("[DEBUG] FAQ生成失敗: 生成されたFAQがありません")
                        return

                    # 生成されたFAQを承認待ちキューに追加（中断されても実行）
                    added_count = 0
                    total_generated = len(generated_faqs)
                    faqs_list = []  # 生成されたFAQリスト（質問と位置）

                    for faq in generated_faqs:
                        try:
                            qa_id = faq_system.add_pending_qa(
                                question=faq.get('question', ''),
                                answer=faq.get('answer', ''),
                                keywords=faq.get('keywords', ''),
                                category=faq.get('category', category),
                                user_question=f"[自動生成] 米国ビザ申請の手引きVer.21..pdfから生成",
                                window_info=faq.get("window_info", "")
                            )
                            added_count += 1
                            print(f"[DEBUG] 承認待ちQ&Aに追加: {qa_id}")

                            # 質問と位置情報を抽出してリストに追加
                            window_info = faq.get("window_info", "")
                            position = ""
                            if window_info:
                                # window_info形式: "Q範囲: 1250~1750 / A範囲: 1000~2500 / 位置: 1000"
                                import re
                                match = re.search(r'位置:\s*(\d+)', window_info)
                                if match:
                                    position = match.group(1)

                            faqs_list.append({
                                'question': faq.get('question', ''),
                                'position': position
                            })
                        except Exception as e:
                            print(f"[DEBUG] 承認待ちQ&A追加エラー: {e}")

                    # 生成されたFAQリストをgeneration_progressに保存
                    generation_progress['generated_faqs_list'] = faqs_list
                    print(f"[DEBUG] {added_count}件のFAQを承認待ちキューに追加しました")

                except Exception as e:
                    error_msg = f"バックグラウンドFAQ生成エラー: {e}"
                    log_debug(f"EXCEPTION: {error_msg}")
                    print(f"[DEBUG] {error_msg}")
                    import traceback
                    error_trace = traceback.format_exc()
                    log_debug(f"Traceback:\n{error_trace}")
                    traceback.print_exc()
                    generation_progress['status'] = 'error'

            # スレッドを起動
            thread = threading.Thread(target=generate_in_background)
            thread.daemon = True
            thread.start()

            # 即座にレスポンスを返す（Railway タイムアウト回避）
            return jsonify({
                'success': True,
                'message': 'FAQ生成を開始しました。進捗は画面で確認できます。'
            })
        else:
            # 通常モード: ファイルアップロードの処理
            uploaded_file = request.files.get('source_file')
            num_questions = int(request.form.get('num_questions', 3))
            category = request.form.get('category', 'AI生成').strip()

            if not uploaded_file or uploaded_file.filename == '':
                return jsonify({'success': False, 'message': 'PDFファイルを選択してください'})

            if not uploaded_file.filename.lower().endswith('.pdf'):
                return jsonify({'success': False, 'message': 'PDFファイルのみアップロード可能です'})

            if num_questions < 1 or num_questions > 50:
                return jsonify({'success': False, 'message': '生成数は1-50の範囲で指定してください'})

            # ファイルサイズチェック（10MB制限）
            uploaded_file.seek(0, 2)  # ファイルの末尾に移動
            file_size = uploaded_file.tell()
            uploaded_file.seek(0)  # ファイルの先頭に戻す

            if file_size > 10 * 1024 * 1024:  # 10MB
                return jsonify({'success': False, 'message': 'ファイルサイズが10MBを超えています'})

            # 一時ファイルとして保存
            import tempfile
            import uuid

            temp_dir = tempfile.gettempdir()
            temp_filename = f"uploaded_pdf_{uuid.uuid4().hex[:8]}_{uploaded_file.filename}"
            pdf_path = os.path.join(temp_dir, temp_filename)

            # アップロードされたファイルを保存
            uploaded_file.save(pdf_path)
            print(f"[DEBUG] FAQ自動生成開始 - ファイル: {uploaded_file.filename}, 数: {num_questions}")

            # 進捗状況を初期化
            generation_progress['current'] = 0
            generation_progress['total'] = num_questions
            generation_progress['status'] = 'generating'
            generation_progress['retry_count'] = 0
            generation_progress['max_retries'] = 10
            generation_progress['excluded_windows'] = 0
            generation_progress['total_windows'] = 0
            generation_progress['question_range'] = ''
            generation_progress['answer_range'] = ''

            # 中断フラグをリセット
            faq_system.generation_interrupted = False

            # 進捗更新用コールバックを設定
            def update_progress(current, total, retry_count=0, excluded_windows=0, total_windows=0, question_range='', answer_range='', current_position='', rejected_position=''):
                current_time = time.time()
                generation_progress['current'] = current
                generation_progress['total'] = total
                generation_progress['status'] = 'generating'
                generation_progress['retry_count'] = retry_count
                generation_progress['excluded_windows'] = excluded_windows
                generation_progress['total_windows'] = total_windows

                # 現在試行中の位置を常に記録（リアルタイム表示用）
                generation_progress['current_trying_position'] = current_position

                # FAQ生成成功時（retry_count == 0）のみ位置をリストに追加
                if retry_count == 0 and current_position and current_position not in generation_progress['positions_list']:
                    generation_progress['positions_list'].append(current_position)

                # 拒否された位置を記録（赤字表示用）
                if rejected_position and rejected_position not in generation_progress['rejected_positions']:
                    generation_progress['rejected_positions'].append(rejected_position)

                generation_progress['last_update_time'] = current_time

                # 経過時間を計算
                if generation_progress['start_time']:
                    generation_progress['elapsed_time'] = current_time - generation_progress['start_time']

                    # 生成速度を計算（現在の件数 / 経過時間）
                    if current > 0 and generation_progress['elapsed_time'] > 0:
                        generation_progress['average_speed'] = current / generation_progress['elapsed_time']
                        generation_progress['time_per_faq'] = generation_progress['elapsed_time'] / current

                print(f"[DEBUG] 進捗更新: {current}/{total}, 経過時間: {generation_progress['elapsed_time']:.1f}秒, 平均速度: {generation_progress['average_speed']:.2f} FAQ/秒, ウィンドウリトライ: {retry_count}, 除外ウィンドウ: {excluded_windows}/{total_windows}, 位置リスト: {', '.join(generation_progress['positions_list'])}, 試行中: {current_position}")

            faq_system.progress_callback = update_progress

            # バックグラウンドスレッドでFAQ生成を実行
            def generate_in_background():
                try:
                    print("[DEBUG] バックグラウンドスレッドでFAQ生成開始（通常モード）")
                    generated_faqs = faq_system.generate_faqs_from_document(pdf_path, num_questions, category)

                    # 一時ファイルをクリーンアップ
                    try:
                        if os.path.exists(pdf_path):
                            os.remove(pdf_path)
                            print(f"[DEBUG] 一時ファイル削除: {pdf_path}")
                    except Exception as cleanup_error:
                        print(f"[DEBUG] 一時ファイル削除エラー: {cleanup_error}")

                    # 生成完了（中断された場合もFAQがあれば保存）
                    if faq_system.generation_interrupted:
                        generation_progress['status'] = 'interrupted'
                        print(f"[DEBUG] FAQ生成が中断されました（生成済み: {len(generated_faqs)}件）")
                    else:
                        generation_progress['status'] = 'completed'

                    if not generated_faqs:
                        generation_progress['status'] = 'error' if not faq_system.generation_interrupted else 'interrupted'
                        print("[DEBUG] FAQ生成失敗: 生成されたFAQがありません")
                        return

                    # 生成されたFAQを承認待ちキューに追加（中断されても実行）
                    added_count = 0
                    total_generated = len(generated_faqs)
                    for faq in generated_faqs:
                        try:
                            qa_id = faq_system.add_pending_qa(
                                question=faq.get('question', ''),
                                answer=faq.get('answer', ''),
                                keywords=faq.get('keywords', ''),
                                category=faq.get('category', category),
                                user_question=f"[自動生成] {uploaded_file.filename}から生成",
                                window_info=faq.get("window_info", "")
                            )
                            added_count += 1
                            print(f"[DEBUG] 承認待ちQ&Aに追加: {qa_id}")
                        except Exception as e:
                            print(f"[DEBUG] 承認待ちQ&A追加エラー: {e}")

                    print(f"[DEBUG] {added_count}件のFAQを承認待ちキューに追加しました")

                except Exception as e:
                    error_msg = f"バックグラウンドFAQ生成エラー: {e}"
                    log_debug(f"EXCEPTION: {error_msg}")
                    print(f"[DEBUG] {error_msg}")
                    import traceback
                    error_trace = traceback.format_exc()
                    log_debug(f"Traceback:\n{error_trace}")
                    traceback.print_exc()
                    generation_progress['status'] = 'error'

            # スレッドを起動
            thread = threading.Thread(target=generate_in_background)
            thread.daemon = True
            thread.start()

            # 即座にレスポンスを返す（Railway タイムアウト回避）
            return jsonify({
                'success': True,
                'message': 'FAQ生成を開始しました。進捗は画面で確認できます。'
            })

    except Exception as e:
        print(f"[DEBUG] FAQ自動生成エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'エラーが発生しました: {str(e)}'})

@app.route('/feedback', methods=['POST'])
def feedback():
    """ユーザーフィードバックを処理"""
    data = request.get_json()
    satisfied = data.get('satisfied')
    user_question = data.get('user_question')
    matched_question = data.get('matched_question')
    matched_answer = data.get('matched_answer')

    if not satisfied and user_question:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 不満足なQ&Aを記録
        faq_system.save_unsatisfied_qa(user_question, matched_question, matched_answer, timestamp)

        # Claude API が設定されているかチェック
        import os
        api_key = os.getenv('CLAUDE_API_KEY')
        print(f"[DEBUG] CLAUDE_API_KEY exists: {bool(api_key)}")
        if api_key:
            print(f"[DEBUG] API key starts with: {api_key[:10] if len(api_key) > 10 else 'too short'}")

        if api_key:
            # Claude で自動改善を試行
            try:
                print(f"[DEBUG] Claude API で自動改善開始: {user_question}")
                improvement_success = faq_system.auto_improve_qa(user_question, matched_question, matched_answer)
                if improvement_success:
                    print(f"[DEBUG] 自動改善成功")
                    return jsonify({
                        'status': 'success',
                        'message': 'フィードバックありがとうございます。【Claude API】が改善されたQ&Aを自動生成しました。管理者による承認後にFAQに追加されます。'
                    })
                else:
                    print(f"[DEBUG] 自動改善失敗")
                    return jsonify({
                        'status': 'success',
                        'message': 'フィードバックありがとうございます。改善案の生成に失敗しましたが、記録いたしました。'
                    })
            except Exception as e:
                print(f"自動改善エラー: {e}")
                return jsonify({
                    'status': 'success',
                    'message': 'フィードバックありがとうございます。記録いたしました。（Claude API エラー）'
                })
        else:
            # Claude API キー未設定の場合、モック機能を使用
            print(f"[DEBUG] Claude API キー未設定。モック改善機能を使用します")
            try:
                improvement_success = faq_system.auto_improve_qa(user_question, matched_question, matched_answer)
                if improvement_success:
                    print(f"[DEBUG] モック改善成功")
                    return jsonify({
                        'status': 'success',
                        'message': 'フィードバックありがとうございます。【モック機能】が改善されたQ&Aを自動生成しました。管理者による承認後にFAQに追加されます。'
                    })
                else:
                    print(f"[DEBUG] モック改善失敗")
                    return jsonify({
                        'status': 'success',
                        'message': 'フィードバックありがとうございます。改善案の生成に失敗しましたが、記録いたしました。'
                    })
            except Exception as e:
                print(f"モック改善エラー: {e}")
                return jsonify({
                    'status': 'success',
                    'message': 'フィードバックありがとうございます。記録いたしました。（モック機能エラー）'
                })

    return jsonify({'status': 'success'})

if __name__ == '__main__':
    import os
    # 起動時に環境変数をチェック
    api_key = os.getenv('CLAUDE_API_KEY')
    print(f"[STARTUP] CLAUDE_API_KEY is {'set' if api_key else 'NOT set'}")
    if api_key:
        print(f"[STARTUP] API key starts with: {api_key[:10]}...")

    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)