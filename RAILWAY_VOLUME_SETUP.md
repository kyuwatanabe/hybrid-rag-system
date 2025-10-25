# Railway Volume設定手順 - ベクトルDB永続化

## 概要

Railway Volumeを使用してベクトルDBを永続化することで、デプロイ時間を大幅に短縮できます。

### 効果
- **初回デプロイ**: 5〜7分（ベクトルDB構築）
- **2回目以降**: 30秒以下（保存済みDBを読み込み）
- **PDF更新時のみ**: 5〜7分（自動再構築）

---

## Railway Volume設定手順

### 1. Railwayダッシュボードでプロジェクトを開く

1. https://railway.app/ にアクセス
2. `hybrid-rag-system` プロジェクトを選択

### 2. Volume を作成

1. プロジェクト画面で **「+ New」** をクリック
2. **「Volume」** を選択
3. 以下の設定を入力：
   - **Name**: `vector-db-storage`
   - **Mount Path**: `/app/vector_db`
   - **Size**: 1GB（デフォルトでOK）
4. **「Create」** をクリック

### 3. サービスにVolumeをアタッチ

1. 左サイドバーで `web` サービスを選択
2. **「Settings」** タブを開く
3. **「Volumes」** セクションまでスクロール
4. **「+ Add Volume」** をクリック
5. 作成した `vector-db-storage` を選択
6. **「Mount Path」** を確認: `/app/vector_db`
7. **「Save」** をクリック

### 4. 自動再デプロイを待つ

- Volume設定後、Railwayが自動的に再デプロイします
- 初回は5〜7分かかります（ベクトルDB構築）
- 2回目以降は30秒以下になります

---

## 動作確認

### 1. 初回デプロイログ確認

Railwayの**Logsタブ**で以下を確認：

```
✗ Vector database not found: /app/vector_db/faiss_index.bin
[INFO] PDF file list has changed
Building vector database (this may take several minutes)...
✓ Vector database built successfully!
[INFO] PDF metadata saved to /app/vector_db/pdf_metadata.json
```

### 2. 2回目以降のデプロイログ確認

再デプロイ後、Logsタブで以下を確認：

```
✓ Found 1 PDF file(s):
  - 米国ビザ申請の手引きVer.21..pdf
[INFO] No PDF updates detected
✓ Vector database is up-to-date: /app/vector_db/faiss_index.bin
✓ No PDF updates detected - skipping rebuild
```

**起動時間**: 約30秒以下

---

## PDF更新時の動作

### PDFを更新した場合

1. `reference_docs/` フォルダのPDFファイルを更新
2. GitHubにpush
3. Railwayが自動デプロイ
4. **自動的に再構築が実行されます**：

```
✓ Vector database exists: /app/vector_db/faiss_index.bin
[INFO] PDF updated: 米国ビザ申請の手引きVer.21..pdf
⚠ PDF updates detected - rebuilding vector database...
Building vector database (this may take several minutes)...
✓ Vector database built successfully!
```

---

## トラブルシューティング

### Volume が見つからない

**症状:**
```
Error: Cannot write to /app/vector_db
```

**解決策:**
1. RailwayダッシュボードでVolumeが正しくアタッチされているか確認
2. Mount Pathが `/app/vector_db` であることを確認
3. サービスを再デプロイ

### ベクトルDBが毎回再構築される

**症状:**
- 2回目以降のデプロイでも5〜7分かかる
- ログに「PDF updates detected」と表示される

**原因:**
- Volume が正しくマウントされていない
- `pdf_metadata.json` が保存されていない

**解決策:**
1. RailwayダッシュボードでVolume設定を確認
2. ログで以下のメッセージを確認：
   ```
   [INFO] PDF metadata saved to /app/vector_db/pdf_metadata.json
   ```
3. メッセージが表示されない場合、Volumeの設定を見直す

### Volumeの容量不足

**症状:**
```
Error: No space left on device
```

**解決策:**
1. RailwayダッシュボードでVolume容量を増やす
2. Settings → Volumes → `vector-db-storage` → Edit
3. Sizeを2GB以上に増やす

---

## ファイル構成

### Volume内のファイル

```
/app/vector_db/
├── faiss_index.bin           # FAISSインデックス（ベクトルDB本体）
├── faiss_index_metadata.pkl  # チャンクメタデータ
└── pdf_metadata.json          # PDF更新検出用メタデータ
```

### pdf_metadata.json の内容例

```json
{
  "米国ビザ申請の手引きVer.21..pdf": 1729856400.0
}
```

**注:** 値はUNIXタイムスタンプ（最終更新日時）

---

## 実装詳細

### PDF更新検出ロジック

`startup_init.py` で実装：

1. **PDFメタデータ取得**: `get_pdf_metadata()`
   - PDFファイル名と最終更新日時（mtime）を取得

2. **更新チェック**: `check_pdf_updates()`
   - 保存済みメタデータと比較
   - ファイル名変更、追加、更新を検出

3. **メタデータ保存**: `save_pdf_metadata()`
   - ベクトルDB構築後に保存
   - 次回起動時の比較に使用

### 起動フロー

```
起動開始
  ↓
ベクトルDB存在チェック
  ↓
┌─ 存在しない → 構築（5〜7分）
│
└─ 存在する
    ↓
  PDF更新チェック
    ↓
  ┌─ 更新あり → 再構築（5〜7分）
  │
  └─ 更新なし → スキップ（30秒以下）
```

---

## 補足情報

### Volume の削除方法

⚠️ **注意**: Volumeを削除すると、保存されたベクトルDBが失われます。

1. RailwayダッシュボードでVolumeを選択
2. Settings → Delete
3. 確認ダイアログで「Delete」をクリック

### ローカル開発環境

ローカルでは `./vector_db/` にベクトルDBが保存されます。

```bash
# .gitignore に含まれているため、Gitで管理されません
vector_db/
```

---

## 参考資料

- [Railway Volumes Documentation](https://docs.railway.app/reference/volumes)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)

---

**最終更新**: 2025-10-25
**バージョン**: 1.0
