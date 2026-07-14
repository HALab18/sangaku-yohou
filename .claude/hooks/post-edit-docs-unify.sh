#!/bin/bash
# ドキュメント・新規ページ追加後の統合・コミット・PR・マージの自動化
# 用途: ドキュメントを編集・新規作成した場合、このスクリプトで一括処理

# 想定される状況:
# - docs/ 配下のファイルを新規作成・編集した
# - index.html を編集してドキュメントへのリンクを追加した
# - 準備完了 → このスクリプト実行で DEVLOG記録・コミット・PR作成・マージまで完了

set -e  # エラーで即座に終了

# 初期化
REPO_ROOT="$(git rev-parse --show-toplevel)"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
CURRENT_DATE=$(date +%Y-%m-%d)

# 1. DEVLOG にセッション記録を追加（既に手動で書いてある想定）
echo "✓ DEVLOG 記録済み（手動更新）"

# 2. コミット
echo "📝 コミット実行..."
git add docs/ index.html DEVLOG.md scripts/gen_*.py 2>/dev/null || true
if git diff-index --quiet HEAD --; then
    echo "⚠ 変更がありません"
    exit 0
fi

COMMIT_MSG=$(cat <<'EOF'
ドキュメント・リストページの統一・UI改善

- 新規ページ追加・既存ドキュメント統一・フォーム UI 改善
- 詳細は DEVLOG 最新セッション参照

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)

git commit -m "$COMMIT_MSG" || echo "⚠ コミット失敗（既にコミット済みの可能性）"

# 3. プッシュ
echo "🚀 プッシュ実行..."
git push origin "$BRANCH" || echo "⚠ プッシュ失敗"

# 4. PR 作成・マージ（gh CLI が必要）
if command -v gh &> /dev/null; then
    echo "📋 PR 作成・マージ実行..."

    # PR があるかチェック
    PR_NUM=$(gh pr list --head "$BRANCH" --state open --json number -q '.[0].number' 2>/dev/null || echo "")

    if [ -z "$PR_NUM" ]; then
        echo "🔗 PR 新規作成..."
        gh pr create --base master --head "$BRANCH" \
            --title "ドキュメント・リストページの統一・UI改善" \
            --body "詳細は DEVLOG / GitHub で最新コミットをご確認ください。" \
            || echo "⚠ PR 作成失敗"
        PR_NUM=$(gh pr list --head "$BRANCH" --state open --json number -q '.[0].number' 2>/dev/null || echo "")
    fi

    if [ -n "$PR_NUM" ]; then
        echo "✅ PR #$PR_NUM をマージ..."
        gh pr merge "$PR_NUM" --merge || echo "⚠ マージ失敗"
    fi
else
    echo "⚠ gh CLI がインストールされていません。手動で PR 作成・マージしてください。"
fi

echo "✨ 完了"
