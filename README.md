# Hybrid RAG System - インテリジェント FAQ・文書検索システム

**最終更新:** 2025-10-23

## 概要

ハイブリッドRAGシステムは、FAQ検索とRAG（Retrieval-Augmented Generation）を組み合わせた高度な質問応答システムです。FAQデータベースで高速検索を行い、該当がなければPDFから動的に回答を生成します。さらに、生成された良い回答を承認することでFAQデータベースが自動的に学習・成長します。

### アーキテクチャ

```
ユーザー質問
    ↓
[1] FAQ検索（高速・高品質）
    ├→ 該当あり → FAQ回答を返す
    └→ 該当なし
        ↓
    [2] RAG生成（網羅的・柔軟）
        └→ PDFから検索して回答生成
            ↓
        [3] 良い回答を承認待ちリストに追加
            ↓
        [4] 管理者が承認
            ↓
        [5] FAQデータベースに追加（学習完了）
```

## 主な特徴

### 1. 二段階検索アーキテクチャ
- **FAQ検索優先**: 既知の質問には即座に高品質な回答（類似度閾値: 0.85）
- **RAGフォールバック**: 新規質問にはPDFから動的に生成
- **ベストオブボス**: 速度と柔軟性を両立

### 2. 自動学習機能
- RAGで生成された良い回答を承認することでFAQに追加
- FAQデータベースが自動更新され、次回から高速回答
- ベクトルDBも同時更新（RAGも学習）

### 3. PDF自動FAQgeneration
- PDFから自動的にQ&Aを生成
- バランス型ウィンドウ選択（全体を均等にカバー）
- セマンティック重複チェック（類似度: 0.95/0.80）
- リアルタイム進捗表示

### 4. ハルシネーション対策
- 必ず出典（ページ番号）を表示
- PDF内容のみから回答生成
- 信頼性の高い回答

### 5. 管理機能
- 承認待ちQ&Aの一覧・編集・承認・拒否
- FAQデータの自動統合
- 統計情報の表示

## 技術スタック

### バックエンド
- **Python 3.9+**
- **Flask 2.3.0** - Webフレームワーク
- **Claude API (Anthropic)** - LLM（回答生成・FAQ生成）
- **Sentence Transformers** - 日本語埋め込み（paraphrase-multilingual-mpnet-base-v2）
- **FAISS** - 高速ベクトル検索

### フロントエンド
- **HTML/CSS/JavaScript**
- **Bootstrap 5** - UIフレームワーク
- **リアルタイムUI更新** - プログレスバー・ストリーミング

### データ処理
- **PyMuPDF** - PDF処理
- **Pandas** - CSV/データ管理
- **NumPy** - ベクトル演算

## プロジェクト構造

```
rag_system/
├── web_app_hybrid.py          # メインFlaskアプリケーション
├── hybrid_rag_system.py       # ハイブリッドRAGコアロジック
├── rag_system.py              # RAGシステム（PDF検索・回答生成）
├── faq_searcher.py            # FAQ検索システム
├── faq_manager.py             # FAQ管理システム（承認・拒否）
├── pdf_processor.py           # PDF前処理・チャンク化
├── vector_store.py            # FAISSベクトルDB操作
├── requirements.txt           # 依存ライブラリ
├── .env                       # 環境変数（APIキーなど）※要作成
├── .env.sample                # 環境変数サンプル
├── README.md                  # このファイル
├── SETUP.md                   # セットアップ詳細ガイド
│
├── reference_docs/            # PDFファイル配置ディレクトリ
│   └── *.pdf
│
├── vector_db/                 # ベクトルDBファイル（自動生成）
│   ├── faiss_index.bin
│   ├── chunks.pkl
│   └── metadata.pkl
│
├── faq_database.csv           # FAQ検索用データ（自動更新）
├── pending_qa.csv             # 承認待ちQ&A
├── faq_generation_history.csv # FAQ生成履歴
│
├── templates/                 # Flaskテンプレート
│   ├── index_hybrid.html     # チャット画面
│   ├── admin_hybrid.html     # 管理画面
│   └── generate_faq.html     # FAQ生成画面
│
└── static/                    # 静的ファイル
    ├── css/
    │   └── style.css
    └── js/
        └── chat.js
```

## セットアップ

### 前提条件
- Python 3.9以上
- Claude API Key（[Anthropic Console](https://console.anthropic.com/)で取得）
- 2GB以上のメモリ（ベクトルDB用）

### 1. 仮想環境の作成と有効化

```bash
cd rag_system
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 2. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

初回起動時、Sentence Transformersモデル（約500MB）が自動ダウンロードされます。

### 3. 環境変数の設定

```bash
# Windows
copy .env.sample .env

# Mac/Linux
cp .env.sample .env
```

`.env` ファイルを編集して、Claude API Keyを設定：

```bash
CLAUDE_API_KEY=your_actual_api_key_here
```

### 4. PDFファイルの配置

`reference_docs/` ディレクトリにPDFファイルを配置してください。

```bash
mkdir reference_docs  # ディレクトリがない場合
# PDFファイルをコピー
```

### 5. ベクトルDBの作成（初回のみ）

```bash
python rebuild_vector_db.py
```

PDFファイルが処理され、`vector_db/` ディレクトリにベクトルDBが作成されます。

### 6. アプリケーションの起動

```bash
python web_app_hybrid.py
```

ブラウザで以下にアクセス：
- **メイン画面**: http://localhost:5003
- **管理画面**: http://localhost:5003/admin
- **FAQ生成**: http://localhost:5003/generate

## デプロイ

### Railwayへのデプロイ

このシステムは[Railway](https://railway.app/)に簡単にデプロイできます。

**クイックスタート:**

1. [Railway](https://railway.app/)にGitHubアカウントでログイン
2. 「New Project」→「Deploy from GitHub repo」
3. このリポジトリを選択
4. 環境変数 `CLAUDE_API_KEY` を設定
5. 自動デプロイ完了（5-10分）

**詳細手順**: [DEPLOY.md](DEPLOY.md) を参照してください。

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

## 使い方

### 1. 質問応答

1. メイン画面（http://localhost:5003）にアクセス
2. 質問を入力して「送信」
3. FAQまたはRAGから回答が返される
4. 出典（ページ番号）が表示される

### 2. FAQ自動生成

1. FAQ生成画面（http://localhost:5003/generate）にアクセス
2. 生成数を入力（推奨: 10-20個）
3. 「FAQ生成開始」をクリック
4. リアルタイムで生成進捗が表示される
5. 生成されたQ&Aは承認待ちリストに追加される

**生成ルール:**
- バランス型ウィンドウ選択（使用回数が少ない部分を優先）
- セマンティック重複チェック（類似度0.95で完全重複、0.80+キーワードで類似）
- Claude API経由でQ&A生成
- 生成速度: 約8-10秒/件（API応答時間に依存）

### 3. Q&A管理（承認・拒否）

1. 管理画面（http://localhost:5003/admin）にアクセス
2. 承認待ちQ&Aリストを確認
3. 必要に応じて質問・回答を編集
4. 「承認」または「拒否」をクリック
5. 承認されたQ&AはFAQデータベースに自動追加
6. ベクトルDBも自動更新（システムが学習）

## システムフロー

### 質問応答フロー

```
1. ユーザーが質問を入力
   ↓
2. FAQ検索システムが検索（類似度 >= 0.85）
   ├→ ヒット: FAQ回答を返す（高速）
   └→ なし: RAGシステムに移行
       ↓
3. RAGシステムがPDFを検索
   ├→ ベクトル検索（TOP 10チャンク）
   ├→ セマンティック重複除去（類似度 >= 0.93）
   └→ 最終5チャンクを選択
       ↓
4. Claude APIで回答生成
   ├→ 関連チャンクを文脈として使用
   └→ 出典（ページ番号）を明記
       ↓
5. 回答を返す + 承認待ちリストに追加（オプション）
```

### 学習フロー

```
1. RAGで良い回答が生成される
   ↓
2. 承認待ちリストに追加
   ↓
3. 管理者が内容を確認・編集
   ↓
4. 承認
   ├→ faq_database.csv に追加（検索用）
   ├→ ベクトルDBに追加（RAG用）
   └→ FAQ検索システムをリロード
       ↓
5. 次回から同じ質問に高速FAQ回答
```

## API エンドポイント

### メイン機能
- `GET /` - チャット画面
- `POST /ask` - 質問応答API
- `POST /save_to_faq` - 回答をFAQに保存

### 管理機能
- `GET /admin` - 管理画面
- `GET /admin/pending` - 承認待ちQ&A取得
- `POST /admin/approve/<qa_id>` - Q&A承認
- `POST /admin/reject/<qa_id>` - Q&A拒否
- `POST /admin/update/<qa_id>` - Q&A更新
- `GET /admin/stats` - 統計情報取得

### FAQ生成
- `GET /generate` - FAQ生成画面
- `POST /generate_faqs` - FAQ自動生成開始

## 設定

### FAQ検索の類似度閾値

`hybrid_rag_system.py` の `__init__` メソッド:

```python
faq_threshold: float = 0.85  # デフォルト: 0.85
```

- **高い値（0.90以上）**: より厳密なマッチング、RAG頻度増加
- **低い値（0.80以下）**: より柔軟なマッチング、FAQ頻度増加

### RAGチャンク設定

`.env` ファイル:

```bash
TOP_K_CHUNKS=10          # 初期検索数
FINAL_CHUNKS=5           # 最終使用数
SIMILARITY_THRESHOLD=0.93 # 重複除去閾値
CHUNK_SIZE=800           # チャンクサイズ（文字）
CHUNK_OVERLAP=100        # チャンクオーバーラップ
```

## トラブルシューティング

### ベクトルDBが見つからない

```bash
python rebuild_vector_db.py
```

### FAQ検索が動作しない

`faq_database.csv` が存在し、データが含まれているか確認：

```bash
# Windows
type faq_database.csv

# Mac/Linux
cat faq_database.csv
```

空の場合、FAQ生成画面でFAQを生成してください。

### Claude API エラー

- APIキーが正しく設定されているか `.env` を確認
- APIクォータが残っているか確認
- ネットワーク接続を確認

### メモリ不足

ベクトルDBサイズが大きい場合、メモリ不足が発生する可能性があります：

- PDFファイル数を減らす
- `CHUNK_SIZE` を大きくしてチャンク数を削減
- サーバーのメモリを増やす

## パフォーマンス

### 応答時間
- **FAQ検索**: 50-100ms（セマンティック検索）
- **RAG生成**: 5-15秒（Claude API応答時間に依存）

### FAQ生成速度
- **平均**: 約9-10秒/件
- **内訳**:
  - Claude API: 8-9秒
  - 重複チェック: 0.3-0.4秒
  - 待機時間: 0.3秒

### データ規模
- **PDF**: 数十〜数百ページ
- **FAQ**: 数千件まで対応
- **ベクトルDB**: 数万チャンクまで対応

## ライセンス

このプロジェクトは MIT License の下で公開されています。

## 貢献

Issue報告やPull Requestを歓迎します。

## サポート

質問やバグ報告は、GitHubのIssueでお願いします。

## 更新履歴

### v1.0.0 (2025-10-23)
- ハイブリッドRAGシステム初回リリース
- FAQ検索 + RAG生成の二段階アーキテクチャ
- 自動学習機能（承認待ち→FAQ化）
- PDF自動FAQ生成機能
- Web管理画面

## 参考資料

- [Anthropic Claude API Documentation](https://docs.anthropic.com/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)
- [Sentence Transformers](https://www.sbert.net/)
- [Flask Documentation](https://flask.palletsprojects.com/)
