# Railway デプロイガイド

このドキュメントでは、Hybrid RAG SystemをRailwayにデプロイする手順を説明します。

## 目次

1. [Railwayとは](#railwayとは)
2. [事前準備](#事前準備)
3. [デプロイ手順](#デプロイ手順)
4. [環境変数の設定](#環境変数の設定)
5. [デプロイ後の確認](#デプロイ後の確認)
6. [トラブルシューティング](#トラブルシューティング)
7. [料金について](#料金について)

---

## Railwayとは

[Railway](https://railway.app/)は、GitHubと連携して簡単にアプリケーションをデプロイできるPaaSプラットフォームです。

**特徴:**
- GitHubリポジトリから自動デプロイ
- 環境変数の管理が簡単
- 無料プラン（$5/月の無料クレジット）あり
- カスタムドメイン対応

---

## 事前準備

### 1. アカウント作成

1. [Railway](https://railway.app/)にアクセス
2. 「Login」→「Login with GitHub」
3. GitHubアカウントでサインイン
4. 必要な権限を承認

### 2. GitHubリポジトリの準備

プロジェクトをGitHubにプッシュしておく必要があります。

```bash
# 既にプッシュ済みの場合は不要
cd C:\Users\GF001\Desktop\システム開発\手引き用チャットボット\rag_system

# Gitリポジトリ初期化（未実施の場合）
git init
git add .
git commit -m "Initial commit: Hybrid RAG System"

# GitHubリポジトリをリモートに追加
git remote add origin https://github.com/your-username/hybrid-rag-system.git
git branch -M main
git push -u origin main
```

### 3. 必要なファイルの確認

以下のファイルがリポジトリに含まれていることを確認してください：

- ✅ `Procfile` - Railway起動コマンド
- ✅ `runtime.txt` - Pythonバージョン指定
- ✅ `railway.json` - Railway設定
- ✅ `requirements.txt` - 依存ライブラリ
- ✅ `.env.example` - 環境変数テンプレート
- ❌ `.env` - 除外（APIキー含む、.gitignore済み）

---

## デプロイ手順

### Step 1: 新規プロジェクト作成

1. Railwayダッシュボード（https://railway.app/dashboard）にアクセス
2. **「New Project」** をクリック
3. **「Deploy from GitHub repo」** を選択
4. リポジトリ一覧から `hybrid-rag-system` を選択
   - リポジトリが表示されない場合は「Configure GitHub App」をクリックしてアクセス権限を付与

### Step 2: 自動デプロイ開始

Railwayが自動的に以下を実行します：

1. リポジトリのクローン
2. `requirements.txt` から依存ライブラリをインストール
3. `Procfile` の内容に従ってアプリを起動

**初回デプロイには5-10分かかります**（Sentence Transformersモデルダウンロード含む）

---

## 環境変数の設定

### 必須の環境変数

デプロイ後、以下の環境変数を設定する必要があります：

1. Railwayダッシュボードでプロジェクトをクリック
2. **「Variables」** タブをクリック
3. **「New Variable」** をクリック
4. 以下を追加：

#### CLAUDE_API_KEY（必須）

```
CLAUDE_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxx
```

Claude APIキーを設定します（[Anthropic Console](https://console.anthropic.com/)で取得）。

#### その他の推奨設定

```
# 本番環境設定
FLASK_ENV=production
FLASK_DEBUG=False

# FAQ検索の類似度閾値（デフォルト: 0.85）
FAQ_THRESHOLD=0.85

# RAG設定
TOP_K_CHUNKS=10
FINAL_CHUNKS=5
SIMILARITY_THRESHOLD=0.93

# チャンク設定
CHUNK_SIZE=800
CHUNK_OVERLAP=100
```

### 環境変数の反映

環境変数を追加・変更すると、**自動的に再デプロイ**されます。

---

## デプロイ後の確認

### Step 1: デプロイログの確認

1. Railwayダッシュボードでプロジェクトをクリック
2. **「Deployments」** タブを確認
3. 最新のデプロイメントをクリック
4. ログを確認：

**正常なログ例:**

```
============================================================
ハイブリッドRAGシステム 初期化中...
============================================================

[1/3] FAQ管理システムを初期化中...
[2/3] FAQ検索システムを初期化中...
[3/3] RAGシステムを初期化中...

============================================================
ハイブリッドRAGシステム 準備完了！
============================================================

 * Running on http://0.0.0.0:XXXX
```

### Step 2: 公開URLの取得

1. **「Settings」** タブをクリック
2. **「Domains」** セクションを確認
3. Railwayが自動生成したURL（例: `https://your-app-name.up.railway.app`）をクリック

### Step 3: 動作確認

ブラウザで以下にアクセスして動作確認：

- **メイン画面**: `https://your-app-name.up.railway.app/`
- **管理画面**: `https://your-app-name.up.railway.app/admin`
- **FAQ生成**: `https://your-app-name.up.railway.app/generate`

質問を入力して、回答が返ることを確認してください。

---

## トラブルシューティング

### デプロイが失敗する

**原因1: 環境変数が設定されていない**

```
Error: CLAUDE_API_KEY not found
```

**解決策**: `CLAUDE_API_KEY` を環境変数に追加

**原因2: メモリ不足**

```
Killed
```

**解決策**:
- Railwayの無料プランではメモリ制限があります
- Pro プラン（$20/月）にアップグレードを検討
- または、チャンクサイズを増やしてメモリ使用量を削減：
  ```
  CHUNK_SIZE=1000
  ```

### アプリが起動しない

**ログ確認**:

1. Deployments タブを開く
2. 最新のデプロイメントをクリック
3. ログを確認

**よくあるエラー**:

```
ModuleNotFoundError: No module named 'xxx'
```

→ `requirements.txt` に該当モジュールが含まれているか確認

```
CLAUDE_API_KEY is NOT set
```

→ 環境変数を設定

### FAQ検索/RAG生成が動作しない

**原因**: ベクトルDBが作成されていない、またはPDFファイルがない

**解決策**:

1. `reference_docs/` ディレクトリにサンプルPDFを追加
2. 初回起動時に自動生成されるように `rebuild_vector_db.py` を修正
   - または手動で起動スクリプトを作成

**注意**: Railwayはファイルシステムが揮発性のため、再デプロイ時にベクトルDBが消えます。永続化が必要な場合は、Railway Volumesを使用してください。

### 応答が遅い

**原因**:
- 初回起動時のモデルダウンロード（500MB）
- Claude APIの応答時間（8-10秒）

**正常**: RAG生成は5-15秒かかるのが正常です。FAQ検索は高速（50-100ms）です。

---

## 料金について

### 無料プラン

- **$5/月の無料クレジット**
- 小規模プロジェクトに適しています
- メモリ: 512MB-1GB
- CPU: 共有

**注意**: Hybrid RAG Systemは初回起動時にモデルをダウンロード（500MB）するため、メモリ使用量が高くなります。無料プランで動作しない場合は、Proプランを検討してください。

### Proプラン

- **$20/月**
- メモリ: 8GB
- CPU: 専有
- カスタムドメイン
- 複数のサービス

詳細: [Railway Pricing](https://railway.app/pricing)

---

## カスタムドメインの設定（オプション）

独自ドメインを使用する場合：

1. Railwayダッシュボードで **「Settings」** → **「Domains」**
2. **「Custom Domain」** をクリック
3. ドメイン名を入力（例: `rag.yourdomain.com`）
4. DNS設定でCNAMEレコードを追加：
   ```
   rag.yourdomain.com CNAME your-app-name.up.railway.app
   ```
5. SSL証明書は自動発行されます

---

## 自動デプロイの設定

GitHubにプッシュすると自動的にRailwayにデプロイされます。

### ブランチ設定

デフォルトでは `main` ブランチが自動デプロイされます。別のブランチを使用する場合：

1. **「Settings」** → **「Service」**
2. **「Source」** セクション
3. **「Branch」** を変更

### デプロイの無効化

自動デプロイを一時的に無効にする場合：

1. **「Settings」** → **「Service」**
2. **「Watch Paths」** でデプロイをトリガーするファイルを指定

---

## データの永続化（オプション）

Railwayのファイルシステムは揮発性のため、再デプロイ時にベクトルDBが消えます。

### Railway Volumesを使用

1. Railwayダッシュボードで **「Settings」** → **「Volumes」**
2. **「New Volume」** をクリック
3. マウントパス: `/app/vector_db`
4. サイズ: 1GB（推奨）

これにより、ベクトルDBが永続化されます。

---

## まとめ

Railwayへのデプロイ手順:

1. ✅ GitHubリポジトリを準備
2. ✅ Railwayで新規プロジェクト作成
3. ✅ GitHubリポジトリを選択
4. ✅ 環境変数（`CLAUDE_API_KEY`）を設定
5. ✅ デプロイ完了を待つ
6. ✅ 公開URLで動作確認

これで、Hybrid RAG Systemがインターネット上で公開されました！

---

## サポート

問題が発生した場合:

1. [Railway Discord](https://discord.gg/railway) でサポートを受ける
2. [Railway Documentation](https://docs.railway.app/) を確認
3. GitHubのIssueで報告

---

## 参考リンク

- [Railway公式サイト](https://railway.app/)
- [Railway Documentation](https://docs.railway.app/)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [FAQ System Example](https://faqsystem-production.up.railway.app/)
