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
faq_data_path = os.path.join(faq_system_dir, 'faq_data.csv')
faq_system = FAQSystem(faq_data_path)
faq_system.claude_api_key = os.getenv('CLAUDE_API_KEY')
# FAQSystemの作業ディレクトリを明示的に設定
faq_system.pending_file = os.path.join(faq_system_dir, 'pending_qa.csv')
faq_system.unsatisfied_qa_file = os.path.join(faq_system_dir, 'unsatisfied_qa.csv')
faq_system.faq_generation_history_file = os.path.join(faq_system_dir, 'faq_generation_history.csv')

# ハイブリッドRAGシステムを初期化（検索用）
print("[INFO] ハイブリッドRAGシステムを初期化中...")
hybrid_rag = HybridRAGSystem(
    faq_csv_path='faq_database.csv',
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
    'question_range': '',  # 質問ウィンドウ範囲
    'answer_range': '',  # 回答ウィンドウ範囲
    'logs': [],  # 最新10件のログメッセージ
    'start_time': None,  # 生成開始時刻
    'last_update_time': None,  # 最終更新時刻
    'elapsed_time': 0,  # 経過時間（秒）
    'generation_speed': 0,  # 生成速度（FAQ/秒）
    'average_speed': 0,  # 平均速度（FAQ/秒）
    'time_per_faq': 0  # FAQ1件あたりの平均時間（秒）
}

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
    return render_template('backup.html')

@app.route('/admin')
def admin():
    """管理画面"""
    try:
        # 最新データを再読み込み
        faq_system.load_faq_data('faq_data.csv')
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

@app.route('/admin/clear_history', methods=['POST'])
def clear_generation_history():
    """FAQ生成履歴をクリア（デバッグ用）"""
    import os
    history_file = 'faq_generation_history.csv'
    try:
        if os.path.exists(history_file):
            os.remove(history_file)
            print(f"[DEBUG] FAQ生成履歴を削除: {history_file}")
            return jsonify({'success': True, 'message': 'FAQ生成履歴を削除しました'})
        else:
            return jsonify({'success': True, 'message': '履歴ファイルは存在しません'})
    except Exception as e:
        print(f"[ERROR] 履歴削除エラー: {e}")
        return jsonify({'success': False, 'message': f'エラー: {e}'})

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

    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:index>', methods=['POST'])
def delete_faq(index):
    """FAQ削除"""
    faq_system.delete_faq(index)
    faq_system.save_faq_data()
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
        if os.path.exists('faq_data-1.csv'):
            zip_file.write('faq_data-1.csv', 'faq_data-1.csv')

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

        # FAQデータ
        faq_file = os.path.join(temp_dir, 'faq_data-1.csv')
        if os.path.exists(faq_file):
            shutil.copy(faq_file, 'faq_data-1.csv')
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
        faq_system.load_faq_data('faq_data-1.csv')
        faq_system.load_pending_qa()

        restored_str = '、'.join(restored_files)
        print(f"[DEBUG] バックアップ復元完了: {restored_str}")

        return redirect(url_for('backup_page') + f'?success=restore&files={len(restored_files)}')

    except Exception as e:
        print(f"[ERROR] バックアップ復元エラー: {e}")
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
    faq_system.load_faq_data('faq_data-1.csv')

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
    faq_system.load_faq_data('faq_data-1.csv')
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
    else:
        print(f"[DEBUG] Q&A却下失敗: {qa_id}")
    return redirect(url_for('review_pending'))

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
        faq_system.load_faq_data('faq_data-1.csv')
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
            generation_progress['question_range'] = ''
            generation_progress['answer_range'] = ''
            generation_progress['start_time'] = time.time()  # 生成開始時刻を記録
            generation_progress['last_update_time'] = time.time()
            generation_progress['elapsed_time'] = 0
            generation_progress['generation_speed'] = 0
            generation_progress['average_speed'] = 0
            generation_progress['time_per_faq'] = 0

            # 中断フラグをリセット
            faq_system.generation_interrupted = False

            # 進捗更新用コールバックを設定
            def update_progress(current, total, retry_count=0, excluded_windows=0, total_windows=0, question_range='', answer_range=''):
                current_time = time.time()
                generation_progress['current'] = current
                generation_progress['total'] = total
                generation_progress['status'] = 'generating'
                generation_progress['retry_count'] = retry_count
                generation_progress['excluded_windows'] = excluded_windows
                generation_progress['total_windows'] = total_windows
                generation_progress['question_range'] = question_range
                generation_progress['answer_range'] = answer_range
                generation_progress['last_update_time'] = current_time

                # 経過時間を計算
                if generation_progress['start_time']:
                    generation_progress['elapsed_time'] = current_time - generation_progress['start_time']

                    # 生成速度を計算（現在の件数 / 経過時間）
                    if current > 0 and generation_progress['elapsed_time'] > 0:
                        generation_progress['average_speed'] = current / generation_progress['elapsed_time']
                        generation_progress['time_per_faq'] = generation_progress['elapsed_time'] / current

                print(f"[DEBUG] 進捗更新: {current}/{total}, 経過時間: {generation_progress['elapsed_time']:.1f}秒, 平均速度: {generation_progress['average_speed']:.2f} FAQ/秒, ウィンドウリトライ: {retry_count}, 除外ウィンドウ: {excluded_windows}/{total_windows}, 質問範囲: {question_range}")

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
                    for faq in generated_faqs:
                        try:
                            qa_id = faq_system.add_pending_qa(
                                question=faq.get('question', ''),
                                answer=faq.get('answer', ''),
                                keywords=faq.get('keywords', ''),
                                category=faq.get('category', category),
                                user_question=f"[自動生成] 米国ビザ申請の手引きVer.21..pdfから生成"
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
            def update_progress(current, total, retry_count=0, excluded_windows=0, total_windows=0, question_range='', answer_range=''):
                current_time = time.time()
                generation_progress['current'] = current
                generation_progress['total'] = total
                generation_progress['status'] = 'generating'
                generation_progress['retry_count'] = retry_count
                generation_progress['excluded_windows'] = excluded_windows
                generation_progress['total_windows'] = total_windows
                generation_progress['question_range'] = question_range
                generation_progress['answer_range'] = answer_range
                generation_progress['last_update_time'] = current_time

                # 経過時間を計算
                if generation_progress['start_time']:
                    generation_progress['elapsed_time'] = current_time - generation_progress['start_time']

                    # 生成速度を計算（現在の件数 / 経過時間）
                    if current > 0 and generation_progress['elapsed_time'] > 0:
                        generation_progress['average_speed'] = current / generation_progress['elapsed_time']
                        generation_progress['time_per_faq'] = generation_progress['elapsed_time'] / current

                print(f"[DEBUG] 進捗更新: {current}/{total}, 経過時間: {generation_progress['elapsed_time']:.1f}秒, 平均速度: {generation_progress['average_speed']:.2f} FAQ/秒, ウィンドウリトライ: {retry_count}, 除外ウィンドウ: {excluded_windows}/{total_windows}, 質問範囲: {question_range}")

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
                                user_question=f"[自動生成] {uploaded_file.filename}から生成"
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