# -*- coding: utf-8 -*-
"""garbled-text-checker 便携版（六种经典乱码检测与 BFS 反向还原）。

用法（参数是文件路径，不是文本本身；完整版 garbled_fix.py 才支持直接传文本）:
    python -X utf8 garbled_portable.py 乱码样本.txt
    cat 乱码样本.txt | python -X utf8 garbled_portable.py
    python -X utf8 garbled_portable.py                # 交互粘贴
完整版（11 种类型、批量/目录扫描、JSON 输出）见 scripts/garbled_fix.py。
"""
import re, sys

def detect(s):
    """识别乱码类型，返回类型 key；未识别返回 None"""
    if not s:
        return None
    if '锟斤拷' in s or (s.count('拷') >= 3 and '锟' in s):
        return '锟拷码'
    if re.search(r'[�■◆●□▲]', s):
        return '口字码'
    # 符号码/拼音码本质：大部分字符是 latin-1 扩展字符（U+0080-U+00FF）。
    # 拼音码（GBK→latin-1）普遍 ≥U+00C0；符号码（UTF-8→latin-1）大量 0xA0-0xBF
    if _ratio(s, r'[-ÿ]') > 0.5:
        return '拼音码' if _ratio(s, r'[À-ÿ]') > 0.4 else '符号码'
    if s.rstrip().endswith('?'):
        return '问句码（末尾问号）'
    # 古文码：GBK 编不了 + 汉字多 + 含假名/CJK 兼容符佐证
    try:
        s.encode('gbk')
    except UnicodeEncodeError:
        han = sum(1 for c in s if '一' <= c <= '鿿')
        if han >= max(3, len(s) * 0.3) and re.search(r'[぀-ヿ︰-﹏]', s):
            return '古文码'
    return None

def _ratio(s, pattern):
    if not s:
        return 0.0
    return len(re.findall(pattern, s)) / len(s)

def clean_score(t):
    """可读性评分 0-1：含汉字→一级汉字区占比≥0.6；无汉字→可打印且非CJK占比≥0.9"""
    if detect(t) or re.search(r'[�■◆●□▲]', t) or '�' in t:
        return 0.0
    if re.search(r'ï¿½|Ã¿', t):
        return 0.0  # U+FFFD 的 cp1252 误读痕迹
    if not t or len(t) < 3:
        return 0.0
    han = [c for c in t if '一' <= c <= '鿿']
    if han:
        if len(han) < max(3, len(t) * 0.4):
            return 0.0
        try:
            t.encode('gbk')  # 全文本必须 GBK 可编码（伪还原混入谚文/私有区会被拒）
        except UnicodeEncodeError:
            return 0.0
        try:
            level1 = sum(1 for c in han if 0xB0A1 <= int.from_bytes(c.encode('gbk'), 'big') <= 0xD7F9)
        except UnicodeEncodeError:
            return 0.0
        ratio = level1 / len(han)
        return ratio if ratio >= 0.6 else 0.0
    good = sum(1 for c in t if c.isprintable() and ord(c) < 0x3000)
    return 1.0 if good / len(t) >= 0.9 else 0.0

def fix(s):
    """BFS 多轮反向还原（双重乱码需 2-3 轮），返回所有干净候选中评分最高者"""
    if '�' in s:
        return None  # 替换符=字节已丢失，任何字节级还原都不可信
    src_han = sum(1 for c in s if '一' <= c <= '鿿') / max(1, len(s))
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
                    if src_han > 0.3 and not any('一' <= c <= '鿿' for c in r):
                        score = 0.0  # 汉字密集输入的候选必须含汉字
                    if score >= 0.6 and r != s:
                        if not best or score > best[0]:
                            best = (score, f'{enc_b}→{dec}: {r}')
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
    r = fix(text)  # 始终尝试还原——detect 可能漏判，fix BFS 兜底
    print(f'修复: {r or "无法自动还原（可能已丢失信息，如 U+FFFD 替换符）"}')
