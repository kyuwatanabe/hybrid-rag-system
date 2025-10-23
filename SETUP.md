# Hybrid RAG System - セットアップガイド

このドキュメントでは、Hybrid RAG Systemの詳細なセットアップ手順を説明します。

## 目次

1. [システム要件](#システム要件)
2. [事前準備](#事前準備)
3. [インストール手順](#インストール手順)
4. [初回セットアップ](#初回セットアップ)
5. [動作確認](#動作確認)
6. [トラブルシューティング](#トラブルシューティング)
7. [高度な設定](#高度な設定)

---

## システム要件

### ハードウェア要件

| 項目 | 最小要件 | 推奨要件 |
|------|---------|---------|
| CPU | 2コア以上 | 4コア以上 |
| メモリ | 4GB | 8GB以上 |
| ストレージ | 5GB（モデル含む） | 10GB以上 |

### ソフトウェア要件

- **OS**: Windows 10/11, macOS 10.15+, Ubuntu 20.04+
- **Python**: 3.9, 3.10, 3.11（3.12は未対応）
- **インターネット接続**: 必須（初回セットアップ時とAPI呼び出し時）

---

## 事前準備

### 1. Python のインストール確認

```bash
python --version
# または
python3 --version
```

Pythonがインストールされていない場合:
- **Windows**: [Python公式サイト](https://www.python.org/downloads/)からダウンロード
- **Mac**: `brew install python@3.11`
- **Linux**: `sudo apt install python3.11`

### 2. Claude API Key の取得

1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. アカウント作成 / ログイン
3. **API Keys** セクションで新しいキーを作成
4. キーをコピーして保存（後で使用）

**注意**: APIキーは絶対に公開リポジトリにコミットしないでください。

### 3. Git のインストール（オプション）

リポジトリをクローンする場合は Git が必要です:

```bash
git --version
```

インストールされていない場合:
- **Windows**: [Git for Windows](https://git-scm.com/download/win)
- **Mac**: `brew install git`
- **Linux**: `sudo apt install git`

---

## インストール手順

### Step 1: プロジェクトの取得

#### Option A: Git Clone（推奨）

```bash
git clone https://github.com/yourusername/hybrid-rag-system.git
cd hybrid-rag-system
```

#### Option B: ZIP ダウンロード

1. GitHubリポジトリから「Code」→「Download ZIP」
2. ZIPファイルを解凍
3. ディレクトリに移動

```bash
cd hybrid-rag-system
```

### Step 2: 仮想環境の作成

仮想環境を使用することで、システム全体のPython環境を汚染せずに済みます。

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### Mac / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

**確認**: プロンプトの先頭に `(venv)` が表示されることを確認してください。

### Step 3: 依存ライブラリのインストール

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**初回インストール時の注意**:
- Sentence Transformersモデル（約500MB）が自動ダウンロードされます
- インストールには5-10分程度かかる場合があります
- ネットワーク接続が必要です

#### インストール進捗の確認

```bash
pip list
```

以下のパッケージが表示されることを確認:
- Flask
- anthropic
- sentence-transformers
- faiss-cpu
- pymupdf
- pandas

---

## 初回セットアップ

### Step 1: 環境変数の設定

`.env.example` ファイルをコピーして `.env` を作成:

#### Windows

```bash
copy .env.example .env
```

#### Mac / Linux

```bash
cp .env.example .env
```

### Step 2: .env ファイルの編集

`.env` ファイルをテキストエディタで開き、Claude API Keyを設定:

```bash
CLAUDE_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxx
```

**最小限の設定例**:

```bash
CLAUDE_API_KEY=your_actual_api_key_here
FLASK_ENV=development
FLASK_DEBUG=True
```

### Step 3: PDFファイルの配置

1. `reference_docs/` ディレクトリを作成（存在しない場合）:

```bash
mkdir reference_docs
```

2. PDFファイルをコピー:

```bash
# 例: カレントディレクトリのPDFを reference_docs/ にコピー
cp /path/to/your/documents/*.pdf reference_docs/
```

**推奨**:
- PDFファイル名は日本語でもOK
- 複数のPDFファイルを配置可能
- サブディレクトリは現在未対応

### Step 4: ベクトルデータベースの構築

PDFファイルを処理してベクトルDBを作成します:

```bash
python rebuild_vector_db.py
```

**処理内容**:
1. `reference_docs/` 内のすべてのPDFを読み込み
2. テキスト抽出
3. チャンク化（デフォルト: 800文字、オーバーラップ100文字）
4. ベクトル埋め込み生成
5. FAISSインデックス作成

**処理時間の目安**:
- 100ページのPDF: 約5-10分
- 500ページのPDF: 約30-60分

**出力**:
```
vector_db/
├── faiss_index.bin      # FAISSインデックス
├── chunks.pkl           # チャンクデータ
└── metadata.pkl         # メタデータ
```

### Step 5: 初期FAQデータの作成（オプション）

初期状態ではFAQデータは空です。以下のいずれかの方法でFAQを作成できます:

#### Option A: Web UIで自動生成

```bash
python web_app_hybrid.py
```

ブラウザで http://localhost:5003/generate にアクセスし、FAQ自動生成を実行。

#### Option B: 手動でCSVファイルを作成

`faq_database.csv` を作成:

```csv
id,question,answer,keywords,category,created_at
1,質問1,回答1,キーワード1;キーワード2,カテゴリ1,2025-10-23 12:00:00
```

---

## 動作確認

### Step 1: アプリケーションの起動

```bash
python web_app_hybrid.py
```

**起動成功時の出力例**:

```
============================================================
ハイブリッドRAGシステム 初期化中...
============================================================

[1/3] FAQ管理システムを初期化中...
[2/3] FAQ検索システムを初期化中...
[3/3] RAGシステムを初期化中...
[4/4] FAQデータをRAGに統合中...

============================================================
ハイブリッドRAGシステム 準備完了！
============================================================

 * Running on http://127.0.0.1:5003
```

### Step 2: 動作確認テスト

ブラウザで以下にアクセス:

#### 1. メイン画面
- URL: http://localhost:5003
- 確認: チャット画面が表示される
- テスト: 質問を入力して回答を確認

#### 2. 管理画面
- URL: http://localhost:5003/admin
- 確認: 承認待ちQ&Aリストが表示される
- テスト: FAQの承認・拒否機能を確認

#### 3. FAQ生成画面
- URL: http://localhost:5003/generate
- 確認: FAQ生成フォームが表示される
- テスト: 10件程度のFAQを生成してみる

### Step 3: 簡単な質問テスト

メイン画面で以下のような質問を試してみましょう:

```
Q: PDFに含まれる内容に関する質問
```

**正常動作の確認**:
- ✅ 回答が返ってくる
- ✅ 出典（ページ番号）が表示される
- ✅ FAQ/RAGのどちらで回答したか表示される

---

## トラブルシューティング

### エラー: `ModuleNotFoundError: No module named 'xxx'`

**原因**: 依存ライブラリがインストールされていない

**解決策**:

```bash
pip install -r requirements.txt
```

### エラー: `CLAUDE_API_KEY not found`

**原因**: 環境変数が設定されていない

**解決策**:

1. `.env` ファイルが存在するか確認
2. `.env` 内に `CLAUDE_API_KEY=...` が記載されているか確認
3. APIキーが正しいか確認

### エラー: `vector_db/faiss_index.bin not found`

**原因**: ベクトルDBが作成されていない

**解決策**:

```bash
python rebuild_vector_db.py
```

### エラー: `Port 5003 is already in use`

**原因**: ポート5003が既に使用されている

**解決策1**: 既存のプロセスを終了

```bash
# Windows
netstat -ano | findstr :5003
taskkill /PID <PID番号> /F

# Mac/Linux
lsof -i :5003
kill -9 <PID番号>
```

**解決策2**: 別のポートを使用

`.env` ファイルに追加:

```bash
FLASK_PORT=5004
```

### FAQ検索が動作しない

**原因**: `faq_database.csv` が存在しないか空

**解決策**:

1. FAQ生成画面でFAQを自動生成
2. 管理画面で承認待ちQ&Aを承認

### 回答生成が遅い

**原因**: Claude API のレスポンス時間（正常）

**対策**:
- FAQ生成を行い、FAQ検索でカバー範囲を増やす
- RAG生成は5-15秒かかるのが正常

### メモリ不足エラー

**原因**: ベクトルDBが大きすぎる

**解決策**:

1. PDFファイル数を減らす
2. `.env` で `CHUNK_SIZE` を大きくする（例: 1000）
3. サーバーのメモリを増やす

---

## 高度な設定

### FAQ検索の調整

`.env` ファイルで閾値を調整:

```bash
FAQ_THRESHOLD=0.85
```

- **0.90以上**: 厳密なマッチング（RAG頻度増加）
- **0.80以下**: 柔軟なマッチング（FAQ頻度増加）

### RAGチャンク数の調整

```bash
TOP_K_CHUNKS=15        # より多くのチャンクを検索
FINAL_CHUNKS=7         # より多くの文脈をLLMに送る
```

**注意**: チャンク数を増やすと処理時間が増加します。

### PDFチャンクサイズの調整

```bash
CHUNK_SIZE=1000        # より大きなチャンク（文脈が広い）
CHUNK_OVERLAP=150      # より大きなオーバーラップ（連続性向上）
```

**再構築が必要**:

```bash
python rebuild_vector_db.py
```

### FAQ自動生成の調整

```bash
FAQ_GEN_WINDOW_SIZE=100                      # より大きなウィンドウ
FAQ_GEN_DUPLICATE_THRESHOLD_EXACT=0.90       # より緩い重複チェック
FAQ_GEN_WAIT_TIME=0.5                        # より長い待機時間
```

---

## セキュリティ

### API キーの管理

❌ **やってはいけないこと**:
- `.env` ファイルをGitにコミット
- APIキーをコードに直接記述
- APIキーをログに出力

✅ **推奨事項**:
- `.env` ファイルは `.gitignore` に含める（デフォルトで設定済み）
- APIキーは環境変数のみで管理
- 本番環境では別の秘密管理サービスを使用

### PDFファイルの取り扱い

プロプライエタリなPDFファイルを含む場合:

```bash
# .gitignore に追加
reference_docs/*.pdf
```

---

## アップグレード

### 依存ライブラリの更新

```bash
pip install --upgrade -r requirements.txt
```

### ベクトルDBの再構築

PDFファイルを追加・削除した場合:

```bash
python rebuild_vector_db.py
```

---

## バックアップ

重要なデータのバックアップ:

```bash
# Windows
xcopy /E /I vector_db vector_db_backup
copy faq_database.csv faq_database_backup.csv

# Mac/Linux
cp -r vector_db vector_db_backup
cp faq_database.csv faq_database_backup.csv
```

---

## 次のステップ

セットアップが完了したら:

1. **FAQを生成**: FAQ生成画面で10-20件のFAQを生成
2. **テスト**: 様々な質問を試して精度を確認
3. **チューニング**: 閾値やチャンクサイズを調整
4. **FAQ承認**: 良い回答を承認してシステムを学習させる

詳細な使い方は [README.md](README.md) を参照してください。
