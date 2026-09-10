---
name: garbled-text-checker
description: "检测与修复文本乱码。触发信号：报错 UnicodeEncodeError/UnicodeDecodeError/'gbk' codec can't/invalid start byte/illegal multibyte sequence，或文本出现锟斤拷、方块�、çæèå 类重音字母、ÓÉÔÂ 类声调字母、鑿辨浚类古文乱码、末尾异常问号、可疑的隐形字符、终端输出残留 $$..$$/\\frac{}/\\times/^{} 等 LaTeX 公式标记。六种经典中文乱码+七种扩展类型（含隐形码：零宽/bidi/tag/变体选择符等不可见 Unicode，AI 水印与隐形注入常用载体；公式码：LaTeX 残留拉平），BFS 反向还原或剥离，给出成因与预防规则。"
---

# 乱码检测与修复（Garbled Text Checker）

文本出现乱码时使用：生僻汉字、方框、问号、带重音字母、"锟斤拷"、未渲染的 LaTeX 公式标记等。先判定类型，再反向修复，最后给出预防建议。脚本内容无需读入——直接运行，只看输出。

## 六种经典乱码速查表

| 类型 | 视觉特征 | 成因 | 反向修复 |
|---|---|---|---|
| **古文码** | 生僻古文，夹杂日韩汉字（鑿辨浚瑕佸…） | GBK 误读 UTF-8 | `s.encode('gbk').decode('utf-8')` |
| **口字码** | 小方块/替换符 ◆◇� (U+FFFD) | UTF-8 误读 GBK | 含 U+FFFD 即不可还原，回源头 |
| **符号码** | 拉丁字母带重音 çæèåï… | ISO8859-1 误读 UTF-8 | `s.encode('latin-1').decode('utf-8')` |
| **拼音码** | 字母顶带声调符 ÓÉÔÂÇ… | ISO8859-1 误读 GBK | `s.encode('latin-1').decode('gbk')` |
| **问句码** | 偶数字符正常，末尾变 `?` | GBK 读 UTF-8 时字节残缺，替换为 `?` | 交给 `fix()` BFS 自动还原；`?` 处字节已丢失，仅能还原其余部分 |
| **锟拷码** | "锟斤拷"反复出现 | U+FFFD 替换符（EF BF BD）被 GBK 重读 | 字节已丢失不可还原；回源头重新读取 |

## 扩展类型（完整版 CLI 支持）

| 类型 | 视觉特征 | 成因 | 处理 |
|---|---|---|---|
| **转义码** | `&amp;amp;` 重复转义 | HTML 实体双重/多重转义 | `html.unescape` 循环 |
| **代理码** | 乱码中混入孤立代理项（U+D800-DFFF） | 截断/拼接产生的非法 Unicode | 不可还原，回源头 |
| **cp1252码** | `â€™` `â€œ` 等 Windows 字符 | Windows-1252 误读 UTF-8 | `s.encode('cp1252').decode('utf-8')` |
| **UTF16码** | 含 NUL 或全角字符密集 | UTF-16 字节被 latin-1/UTF-8 误读 | `fix()` BFS（utf-16-le/be 已入链） |
| **控制码** | C1 控制符（U+0080-009F）密集 | GBK 字节流的单字节残留 | 需字节重组，单文本不可还原 |
| **隐形码** | 肉眼不可见：零宽符（U+200B/200C/2060）、bidi 控制（U+202A-E/2066-9）、tag 字符（U+E0000-E007F）、成批游离变体选择符 | AI 输出注水、隐形提示注入、网页复制的常见载体 | 完整版 CLI `fix()` 直接剥离出干净文本；文件头 BOM、emoji ZWJ 序列、emoji 后 VS16 属正常不报 |
| **公式码** | 终端输出残留 `$$…$$`、`\frac{a}{b}`、`\times`、`10^{23}`、`\quad` 等 LaTeX 标记 | 输出端按 Markdown-LaTeX 写公式，终端不渲染、原样漏出 | `latex_to_text.py` 拉平为纯文本/Unicode（见下节） |

## 检测与修复（直接运行脚本，勿读脚本源码）

三个脚本与本文件同级位于 `scripts/`（安装后即 `~/.claude/skills/garbled-text-checker/scripts/`）。

便携版（六种经典类型，单文件零依赖；参数是文件路径，文本可走管道）：

```bash
python -X utf8 scripts/garbled_portable.py 乱码样本.txt
printf '%s' "乱码文本" | python -X utf8 scripts/garbled_portable.py
```

完整版 CLI（11 种类型，支持直接传文本、批量/目录扫描、JSON 输出）：

```bash
python scripts/garbled_fix.py "鑿辨浚瑕佸ソ濼濂藉彛涔犱範"   # 直接传文本
python scripts/garbled_fix.py -f 乱码.txt -f 另一份.csv      # 多文件
python scripts/garbled_fix.py -d data/ -r --check            # 递归扫描+仅检测(有乱码 exit 1)
python scripts/garbled_fix.py -f 乱码.txt --json             # JSON 输出
python scripts/garbled_fix.py --demo                         # 生成 11 种类型演示样本
```

两个脚本输出 `判定:` 与 `修复:` 两行。`修复:` 显示"无法自动还原"时按工作流第 4 条处理，不要重读脚本源码。

## 公式码：终端里的 LaTeX 残留（latex_to_text.py）

终端不渲染数学公式，`$$pV=\frac{m}{M}RT$$` 会原样漏出。脚本与本文件同级 `scripts/latex_to_text.py`（单文件零依赖）：

```bash
python -X utf8 scripts/latex_to_text.py --demo                        # 自检（应 8/8 通过）
python -X utf8 scripts/latex_to_text.py '$$pV = \frac{m}{M}RT$$'      # 文本→纯文本
python -X utf8 scripts/latex_to_text.py -f 笔记.md                    # 原地拉平（多文件各自处理）
python -X utf8 scripts/latex_to_text.py -f 笔记.md --check            # 仅检测(有残留 exit 1)
printf '%s' '含 $10^{23}$ 的文本' | python -X utf8 scripts/latex_to_text.py   # 管道
```

效果示例：`$$pV = \frac{m}{M}RT \quad\Leftrightarrow\quad pV = NkT$$` → `pV = m/M RT ⇔ pV = NkT`

支持：定界符剥除、`\frac`/`\sqrt` 拉平、上下标转 Unicode 上标下标（`10^{23}`→`10²³`）、希腊字母与关系符（`\alpha`→α、`\times`→×、`\Leftrightarrow`→⇔）、`\text{}` 保留内容、残余命令兜底剥反斜杠。局限：裸 `_x`/`^x` 仅转数字和 +/-（防 snake_case 误伤）；`\begin{}` 环境不解析；`--check` 对 Windows 路径反斜杠会误报。

**预防（输出侧规则，比修复更重要）**：给终端/聊天的公式一律用纯文本记法——分式写 `(m/M)`、上标用 Unicode `10²³`、符号用 `× ⇔ α Δ`，禁用 `$$`、`\frac`、`\times`、`^{}`。AI 回复、课堂笔记、代码注释同此规范。

## 工作流

1. 取一段乱码样本（≥10 字，特征才明显），存成临时文件或直接管道给脚本。
2. 运行脚本看 `判定:` 与 `修复:`；完整版 CLI 适合批量/仅检测场景；疑似公式码直接跑 `latex_to_text.py --check`。
3. `fix` 失败时：对照速查表手动反向——字符全在 latin-1 内先 `encode('latin-1')`；含可编码 GBK 汉字试 `encode('gbk')`；得到字节后按目标编码 `decode`。双重乱码（问句码等）需要对还原结果再跑一轮。
4. 含 U+FFFD 替换符的乱码（口字码、锟拷码、问句码的某些变体）原字节已丢失，无法自动还原——回源头重新读取，或用备份/数据库重建。
5. 修复后向用户说明成因与预防规则。

## 预防规则（告知用户/写入编码规范）

- 文件：统一 **UTF-8** 保存，跨系统传输时保留 BOM 或显式声明编码。
- 读取：明确指定编码（`open(f, encoding='utf-8')`），禁用默认系统编码推断。
- 数据库：连接串显式指定 `charset=utf8mb4`；表/列字符集统一，避免 GBK 与 UTF-8 混用。
- 接口/导入导出：CSV/Excel 导入先确认源文件编码（Excel 导出 CSV 常为 GBK，用 `utf-8-sig`/`gbk` 试探）。
- 转换链：严禁"自动检测编码"后再手写回文件——误判即产生上述乱码之一。
- 命令行：Windows 控制台默认 GBK，Python 脚本加 `-X utf8` 或 `PYTHONIOENCODING=utf-8`，避免输出自身乱码。
- 输出：面向终端/聊天的公式禁用 LaTeX 语法（`$$`、`\frac`、`\times`、`^{}`），用纯文本记法（`pV = (m/M)RT`、`10²³`、`⇔`）；已产生的残留交给 `latex_to_text.py` 拉平。
- 验证：写完文本后用脚本检测一遍，无特征再交付。
