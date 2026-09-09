# Changelog

## [1.2.0] - 2026-09-09

### Changed
- SKILL.md 不再内嵌便携脚本：提取为 `scripts/garbled_portable.py`，skill 触发时的加载体积约 -60%（脚本内容不进模型上下文，只读运行输出）
- description 增补触发信号（UnicodeEncodeError / 'gbk' codec / 锟斤拷 / 重音字母等），脱离用户侧全局配置也能正确触发
- install.sh 同步部署便携版；hook 提示文案与 README 用法同步更新
- 回归测试改为直接加载 `scripts/garbled_portable.py`（不再从 SKILL.md 提取）

### Fixed
- CI 冒烟步骤在 Windows runner 上失败：`/tmp` 为 POSIX 路径，改用 `shell: python` + `tempfile.gettempdir()` 跨平台兼容（自 v1.1.0 起即存在）

## [1.1.0] - 2026-08-15

### Added
- 完整版 CLI `scripts/garbled_fix.py`：多文件、目录递归扫描、`--json` 输出、`--check` 退出码模式、`--demo` 演示样本
- 5 种扩展乱码类型：HTML 双重转义、孤立代理项、cp1252 误读、UTF-16 误读、C1 控制符
- GitHub Actions CI（Ubuntu / Windows / macOS × Python 3.10/3.12）
- MIT License、双语 README

### Changed
- 符号码/拼音码检测重构为 latin-1 扩展字符占比判定
- 古文码检测改为假名/CJK 兼容符佐证（不依赖 GBK 可编码性）
- `clean_score` 双路径评分 + 全文本 GBK 校验，杜绝伪还原
- 口字码/锟拷码/C1 控制码不可还原时如实报告

### Fixed
- BFS 伪还原问题（谚文/私有区混入、纯拉丁伪候选、U+FFFD 痕迹）
- Windows 控制台 GBK 输出乱码（stdout 强制 UTF-8）

## [1.0.0] - 2026-08-14

### Added
- 六种经典乱码类型检测与修复（古文码/口字码/符号码/拼音码/问句码/锟拷码）
- Claude Code skill（SKILL.md 便携版内嵌脚本）
- PostToolUse 自动检测 hook（分层信号防误报）
