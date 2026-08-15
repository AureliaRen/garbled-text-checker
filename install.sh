#!/bin/bash
# garbled-text-checker 一键部署/更新
# 1) 复制 SKILL.md → ~/.claude/skills/garbled-text-checker/
# 2) 复制 hooks/check-garbled.py → ~/.claude/hooks/
# 3) settings.json 幂等合并 PostToolUse hook（已存在则跳过）
set -e

PROJ="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills/garbled-text-checker"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"

mkdir -p "$SKILLS_DIR" "$HOOKS_DIR"

echo "==> 复制 SKILL.md"
cp "$PROJ/SKILL.md" "$SKILLS_DIR/SKILL.md"

echo "==> 复制 hook 脚本"
cp "$PROJ/hooks/check-garbled.py" "$HOOKS_DIR/check-garbled.py"

echo "==> 合并 settings.json hooks 配置"
python -X utf8 - "$SETTINGS" <<'PY'
import json, sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    cfg = json.load(f)

entry = {
    "matcher": "Bash|Read",
    "hooks": [{
        "type": "command",
        "shell": "bash",
        "command": "python -X utf8 \"C:\\Users\\任泽鑫\\.claude\\hooks\\check-garbled.py\"",
        "timeout": 15,
        "statusMessage": "检测编码乱码...",
    }],
}

hooks = cfg.setdefault("hooks", {})
post = hooks.setdefault("PostToolUse", [])
if any(m.get("matcher") == "Bash|Read" for m in post):
    print("   settings.json: hook 已存在，跳过")
else:
    post.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("   settings.json: hook 已添加（新会话或 /hooks 后生效）")
PY

echo "==> 部署完成"
