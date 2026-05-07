#!/usr/bin/env bash
# setup_design_hook.sh — 安裝 post-commit hook，自動觸發 design review
# 在 WSL2 執行：bash scripts/setup_design_hook.sh

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_FILE="$REPO_ROOT/.git/hooks/post-commit"

echo "🔧 安裝 post-commit hook..."

cat > "$HOOK_FILE" << 'HOOK_CONTENT'
#!/usr/bin/env bash
# post-commit hook — 吉寶軒 Claude Design Loop
# 自動偵測 Publish/index.html 的改動並生成下一輪設計 brief

REPO_ROOT="$(git rev-parse --show-toplevel)"
TARGET="Publish/index.html"

# 只在 index.html 有改動時觸發
if git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -q "^$TARGET$"; then
    echo ""
    echo "🎨 偵測到 Claude Design 輸出 ── 正在生成下一輪 brief..."
    echo ""

    # 嘗試 WSL2 python3，fallback 到系統 python3
    if command -v python3 &>/dev/null; then
        python3 "$REPO_ROOT/scripts/ap_design_review.py"
    else
        echo "⚠️  找不到 python3，請手動執行："
        echo "   python3 scripts/ap_design_review.py"
    fi
fi
HOOK_CONTENT

chmod +x "$HOOK_FILE"

echo "✅ Hook 已安裝：$HOOK_FILE"
echo ""
echo "測試方式：修改任一檔案後 git commit，若 Publish/index.html 有改動就會自動觸發。"
