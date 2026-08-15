# garbled-text-checker 乱码检测与修复

识别并修复文本乱码（编码错误）：**古文码 / 口字码 / 符号码 / 拼音码 / 问句码 / 锟拷码** 六种类型，支持检测、BFS 反向还原、预防规则。配套 PostToolUse hook 在工具输出出现编码报错/乱码时自动提醒调用本 skill。

## 目录结构

```
garbled-text-checker/
├── SKILL.md              # skill 源文件（部署到 ~/.claude/skills/garbled-text-checker/）
├── hooks/
│   └── check-garbled.py  # hook 脚本（部署到 ~/.claude/hooks/）
├── tests/                # 回归测试（修改后必跑）
│   ├── test_garbled.py   # skill 内嵌脚本测试
│   └── test_hook.py      # hook 命中/防误报测试
└── install.sh            # 一键部署/更新
```

## 快速开始

```bash
./install.sh    # 部署到 ~/.claude（复制文件 + settings.json 幂等合并 hooks）
```

## 修改优化流程

1. **改**：编辑 `SKILL.md`（检测/修复逻辑）或 `hooks/check-garbled.py`（自动提醒）
2. **测**：`python tests/test_garbled.py && python tests/test_hook.py`
3. **部署**：`./install.sh`（同步到 `~/.claude`）
4. **提交**：`git add -A && git commit -m "..."`

## 设计要点（修改时注意）

### 六种乱码速查

| 类型 | 特征 | 成因 |
|---|---|---|
| 古文码 | 生僻古文夹杂日韩字符 | GBK 误读 UTF-8 |
| 口字码 | 替换符 � / 方块 ◆◇ | UTF-8 误读 GBK |
| 符号码 | 带重音拉丁字符 çæèå | ISO8859-1 误读 UTF-8 |
| 拼音码 | 带声调字母 ÓÉÔÂ | ISO8859-1 误读 GBK |
| 问句码 | 末尾变 `?` | GBK 读 UTF-8 字节残缺 |
| 锟拷码 | "锟斤拷"重复 | U+FFFD（EF BF BD）被 GBK 重读 |

### 修复算法（SKILL.md 内嵌脚本）
- `detect()` 特征正则 + 启发式判定类型（古文码需假名/CJK 兼容符佐证，避免 emoji 误报）
- `fix()` **BFS 多轮**反向解码（enc: latin-1/utf-8/gbk × dec: utf-8/gbk/gb18030/utf-16-le/utf-16，深度 4）
- `clean_score()` 一级汉字区（0xB0A1-0xD7F9）占比评分，返回评分最高的还原结果
- **不可还原是常态**：口字码/锟拷码含 U+FFFD，原字节已丢失，`fix()` 返回 None 属正确行为
- 脚本入口**无条件跑 fix**（detect 漏判时 BFS 兜底）

### hook 防误报设计（check-garbled.py）
- **强信号**：编码错误描述短语（`'gbk' codec can't`、`invalid start byte` 等）直接命中
- **弱信号**：异常类名（`UnicodeEncodeError`）需 **Traceback 佐证**——代码里的 `except` 不是报错
- **乱码按行级占比**：乱码文本整行被污染（>40% 特征字符 / >50% latin-1 扩展字符）；讨论乱码的文档只是零星提及，不会误报
- **配置文件跳过**：`.claude/skills/` 与 `.claude/hooks/` 下的文件含特征词属正常，直接跳过（防止 hook 检测自身）
- 口字码替换符计数 ≥2 即命中（不要求连续 3 个）

## 依赖

- Python 3（检测/修复脚本与 hook）
- Git Bash（install.sh；hook 在 settings.json 中显式 `"shell": "bash"`）

## 版本记录

见 `git log`。初始版本：识别六种乱码 + BFS 修复 + 自动提醒 hook。
