# Garbled Text Checker 乱码检测与修复

> Detect and fix garbled text (mojibake) — 12 garbled-text types, BFS reverse-decoding repair, and a Claude Code skill + auto-detection hook.

[![CI](https://github.com/AureliaRen/garbled-text-checker/actions/workflows/ci.yml/badge.svg)](https://github.com/AureliaRen/garbled-text-checker/actions/workflows/ci.yml)

Identify and repair garbled text caused by encoding errors: the 6 classic Chinese mojibake types (**古文码 / 口字码 / 符号码 / 拼音码 / 问句码 / 锟拷码**) plus 6 extended types (HTML double-escape / lone surrogates / cp1252 misread / UTF-16 misread / C1 control characters / invisible Unicode). Ships as a standalone CLI, a portable script, and a Claude Code skill with an automatic PostToolUse hook.

## Features 功能

- **12 种乱码类型检测**（含隐形码：不可见 Unicode）(12 type detection incl. invisible unicode)

  | Classic 经典 | Cause 成因 |
  |---|---|
  | 古文码 Guwen | GBK misread as UTF-8 |
  | 口字码 Kou | UTF-8 misread as GBK (U+FFFD) |
  | 符号码 Fuhao | ISO-8859-1 misread as UTF-8 |
  | 拼音码 Pinyin | ISO-8859-1 misread as GBK |
  | 问句码 Wenju | Truncated GBK→UTF-8 chain |
  | 锟拷码 Kunkao | U+FFFD stream re-read as GBK |

  | Extended 扩展 | 说明 |
  |---|---|
  | HTML double-escape | `&amp;amp;` repeated entity escaping |
  | Lone surrogates | Invalid U+D800-DFFF units |
  | cp1252 misread | Windows-1252 decoding of UTF-8 bytes |
  | UTF-16 misread | UTF-16LE/BE bytes read as latin-1 |
  | C1 control chars | U+0080-U+009F byte-stuffing residue |

- **BFS 多轮反向还原** (BFS reverse-decoding repair): tries `4 encodings × 7 decodings` up to 4 rounds, scores candidates by GBK level-1 Han character ratio, returns the best clean result. Honest about unrecoverable input (U+FFFD means bytes are gone — it says so instead of fabricating).
- **完整 CLI**: multiple files, recursive directory scan, `--json` machine-readable output, `--check` exit-code mode (CI-friendly), `--demo` sample generator.
- **Claude Code skill + hook**: say "检查乱码" and it runs; a PostToolUse hook auto-detects encoding errors / garbled output in tool results and reminds Claude to fix them.
- **Anti-false-positive design**: heuristic detection requires corroborating characters (kana/CJK compatibility glyphs for Guwen), line-level ratio checks, config-file skip — reading code or docs that merely *mention* mojibake won't trigger.

## Quick Start 快速开始

CLI 需要 Python 3.10+（`str | None` 类型语法）:

```bash
python scripts/garbled_fix.py "鑿辨浚瑕佸ソ濼濂藉彛涔犱範"    # 直接传文本
python scripts/garbled_fix.py -f 乱码.txt -f 另一份.csv      # 多文件
python scripts/garbled_fix.py -d data/ -r --check            # 递归扫描 + 仅检测（有乱码 exit 1）
python scripts/garbled_fix.py -f 乱码.txt --json             # JSON 输出
python scripts/garbled_fix.py --demo                         # 生成 12 种类型演示样本
```

Portable single-file script (`scripts/garbled_portable.py`, six classic types; the argument is a file path, text can be piped in):

```bash
python -X utf8 scripts/garbled_portable.py 乱码样本.txt
printf '%s' "鑿辨浚瑕佸ソ濼濂藉彛涔犱範" | python -X utf8 scripts/garbled_portable.py
```

## Claude Code Skill Installation 安装为 Claude Code skill

```bash
./install.sh
```

This copies `SKILL.md` + the `scripts/` files (full CLI + portable) into `~/.claude/skills/garbled-text-checker/`, the hook into `~/.claude/hooks/`, and idempotently registers the `PostToolUse` hook in `~/.claude/settings.json`. Afterwards:

- 遇到乱码/编码报错时自动调用该 skill（CLAUDE.md 规则 + hook 双保险）
- hook 检测到工具输出含编码报错（`UnicodeEncodeError`、`'gbk' codec can't` 等）或乱码特征时，自动注入提醒

## How It Works 设计原理

- `detect(s)` — ordered heuristic rules: specific signatures first (锟斤拷, U+FFFD, cp1252 sequences), then broad ratios (latin-1 extension character density for 符号码/拼音码, kana corroboration for 古文码).
- `clean_score(t)` — two-path readability scoring: Han text requires ≥60% GBK level-1 characters *and* full-text GBK-encodability (rejects pseudo-restores mixing Hangul/private-use chars); non-Han text requires ≥90% printable non-CJK chars.
- `fix(s)` — BFS over `enc × dec` combinations, depth 4. Early-exits on provably unrecoverable input: U+FFFD (bytes lost), 锟拷码 (came from an EF BF BD replacement stream), C1 control chars (byte-pairing problem). Han-dense input demands Han candidates — encoding chains never turn Chinese into pure latin text.
- 诚实报告：不可还原时明确说"回源头重新读取"，绝不伪造还原结果。

## Design Notes 设计取舍

- **SKILL.md 不内嵌脚本** — 脚本内容不进模型上下文，模型只读运行输出。便携版独立为 `scripts/garbled_portable.py` 后，skill 触发时的加载体积约 -60%。
- **隐形码防误报三规则** — 文件头 BOM、emoji ZWJ 序列（👨‍👩‍👦）、emoji 后的 VS16（❤️）都是正常文本，不判；游离变体选择符 <3 个视为排版噪音，成批出现才判隐写。
- **hook 有意不感知隐形码** — PostToolUse hook 挂在每一次工具输出上，emoji 密集的文本不可避免，误报会骚扰每个会话；不可见字符交给 CLI/skill 按需检测。

## Development 开发

```bash
python tests/test_garbled.py   # 便携版脚本（scripts/garbled_portable.py）
python tests/test_hook.py      # hook 命中/防误报
python tests/test_cli.py       # 完整版 CLI（12 类型 demo / 文件 / --check / --json）
./install.sh                   # 部署到 ~/.claude（修改后同步）
```

CI (GitHub Actions) runs all tests on Ubuntu / Windows / macOS.

## Roadmap 路线图

- [x] 12 种类型检测与修复（含隐形码）
- [x] 完整 CLI（批量/JSON/退出码）
- [x] Claude Code skill + hook
- [ ] ftfy 风格的高级修复（lone marks、ligatures、crashed "s"）
- [ ] 大文件流式扫描（当前一次性读入内存）

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements 致谢

- [python-ftfy](https://github.com/rspeer/python-ftfy) — 乱码修复的业界标准，本项目的 BFS 候选评分思路与其 plan-text 校验同源
