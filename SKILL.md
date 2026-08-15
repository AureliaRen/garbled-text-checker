---
name: garbled-text-checker
description: "检测与修复文本乱码：识别古文码/口字码/符号码/拼音码/问句码/锟拷码六种编码错误，给出成因、反向修复与预防规则。"
---

# 乱码检测与修复（Garbled Text Checker）

文本出现乱码时使用：生僻汉字、方框、问号、带重音字母、"锟斤拷"等。先判定类型，再反向修复，最后给出预防建议。

## 六种乱码速查表

| 类型 | 视觉特征 | 成因 | 反向修复 |
|---|---|---|---|
| **古文码** | 生僻古文，夹杂日韩汉字（鑿辨浚瑕佸…） | GBK 误读 UTF-8 | `s.encode('gbk').decode('utf-8')` |
| **口字码** | 小方块/替换符 ◆◇� (U+FFFD) | UTF-8 误读 GBK | `s.encode('utf-8').decode('gbk')` |
| **符号码** | 拉丁字母带重音 çæèåï… | ISO8859-1 误读 UTF-8 | `s.encode('latin-1').decode('utf-8')` |
| **拼音码** | 字母顶带声调符 ÓÉÔÂÇ… | ISO8859-1 误读 GBK | `s.encode('latin-1').decode('gbk')` |
| **问句码** | 偶数字符正常，末尾变 `?` | GBK 读 UTF-8 时字节残缺，替换为 `?` | 交给 `fix()` BFS 自动还原；`?` 处字节已丢失，仅能还原其余部分 |
| **锟拷码** | "锟斤拷"反复出现 | U+FFFD 替换符（EF BF BD）被 GBK 重读 | 字节已丢失不可还原（`s.encode('gbk')` 只能得到 U+FFFD 流）；回源头重新读取 |

## 检测与修复（内嵌脚本，复制运行）

```bash
python - <<'PY'
import re, sys

def detect(s):
    """识别乱码类型，返回 (类型, 置信度说明)"""
    if '锟斤拷' in s or (s.count('拷') >= 3 and '锟' in s):
        return '锟拷码'
    if re.search(r'[�■◆●□▲]', s):
        return '口字码'
    if re.search(r'[çæèåïøðþêâîôûÿ]{3,}', s, re.I):
        return '符号码'
    if re.search(r'[ÓÉÔÂÒÅÇÑÍ]{3,}', s):
        return '拼音码'
    if s.rstrip().endswith('?'):
        return '问句码（末尾问号，疑似双重误读）'
    # 古文码：GBK 编不了 + 汉字多 + 含假名/CJK 兼容符佐证
    # （纯汉字+emoji 的正常文本也会 GBK 编不了，必须有乱码佐证字符才判）
    try:
        s.encode('gbk')
    except UnicodeEncodeError:
        han = sum(1 for c in s if '一' <= c <= '鿿')
        if han >= max(3, len(s) * 0.3) and re.search(r'[぀-ヿ︰-﹏]', s):
            return '古文码'
    return None

def clean_score(t):
    """正常中文评分 0-1：无乱码特征 + GBK 可编码 + 一级汉字占比。中间态得低分。"""
    if detect(t) or re.search(r'[�■◆●□▲]', t):
        return 0
    han = [c for c in t if '一' <= c <= '鿿']
    if len(han) < max(3, len(t) * 0.4):
        return 0
    try:
        level1 = sum(
            1 for c in han if 0xB0A1 <= int.from_bytes(c.encode('gbk'), 'big') <= 0xD7F9
        )
    except UnicodeEncodeError:
        return 0   # 含 GBK 外字符 → 伪古文等中间态
    return level1 / len(han)

def fix(s):
    """BFS 多轮反向还原（双重乱码需要 2-3 轮），返回所有干净候选中评分最高者"""
    frontier, seen, best = {s}, {s}, None
    for _ in range(4):
        nxt = set()
        for cur in frontier:
            for enc_b in ('latin-1', 'utf-8', 'gbk'):
                try:
                    b = cur.encode(enc_b)
                except UnicodeEncodeError:
                    continue
                for dec in ('utf-8', 'gbk', 'gb18030', 'utf-16-le', 'utf-16'):
                    try:
                        r = b.decode(dec)
                    except (UnicodeDecodeError, ValueError):
                        continue
                    if r in seen:
                        continue
                    seen.add(r)
                    score = clean_score(r)
                    if score >= 0.6 and r != s:
                        if not best or score > best[0]:
                            best = (score, f"{enc_b}→{dec}: {r}")
                    else:
                        nxt.add(r)
        if not nxt:
            break
        frontier = nxt
    return best[1] if best else None

if __name__ == '__main__':
    if len(sys.argv) > 1:
        text = open(sys.argv[1], encoding='utf-8', errors='replace').read()
    else:
        text = sys.stdin.read() if not sys.stdin.isatty() else input('粘贴乱码文本: ')

    kind = detect(text)
    print(f'判定: {kind or "未识别到乱码特征"}')
    r = fix(text)  # 始终尝试还原——detect 可能漏判（如无假名佐证的古文码），fix BFS 兜底
    print(f'修复: {r or "无法自动还原（可能已丢失信息，如 U+FFFD 替换符）"}')
PY
```

## 工作流

1. 取一段乱码样本（≥10 字，特征才明显）。
2. 运行上述脚本：先 `detect` 判定类型，再 `fix` 尝试还原。
3. `fix` 失败时：对照速查表手动反向——字符全在 latin-1 内先 `encode('latin-1')`；含可编码 GBK 汉字试 `encode('gbk')`；得到字节后按目标编码 `decode`。双重乱码（问句码/锟拷码）需要对还原结果再跑一轮。
4. 含 U+FFFD 替换符的乱码（口字码、锟拷码、问句码的某些变体）原字节已丢失，无法自动还原——回源头重新读取，或用备份/数据库重建。
5. 修复后向用户说明成因与预防规则。

## 预防规则（告知用户/写入编码规范）

- 文件：统一 **UTF-8** 保存，跨系统传输时保留 BOM 或显式声明编码。
- 读取：明确指定编码（`open(f, encoding='utf-8')`），禁用默认系统编码推断。
- 数据库：连接串显式指定 `charset=utf8mb4`；表/列字符集统一，避免 GBK 与 UTF-8 混用。
- 接口/导入导出：CSV/Excel 导入先确认源文件编码（Excel 导出 CSV 常为 GBK，用 `utf-8-sig`/`gbk` 试探）。
- 转换链：严禁"自动检测编码"后再手写回文件——误判即产生上述六种乱码之一。
- 验证：写完文本后跑一遍 `detect()`，无特征再交付。
