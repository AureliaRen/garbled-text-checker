#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""garbled_fix — 乱码检测与修复 CLI（garbled-text-checker skill 的完整实现）

识别并修复文本乱码（编码错误）：六种经典类型（古文码 / 口字码 / 符号码 /
拼音码 / 问句码 / 锟拷码）+ 六种扩展类型（HTML 双重转义 / 孤立代理项 /
cp1252 误读 / UTF-16 误读 / C1 控制符 / 隐形码）。
隐形码不是编码错误而是不可见 Unicode（零宽符 / bidi 控制 / tag 字符 /
变体选择符，AI 水印与隐形注入的常见载体），修复动作是剥离而非反向还原。

用法:
  garbled_fix.py "鑿辨浚瑕佸ソ濼濂藉彛涔犱範"    # 直接传乱码文本
  garbled_fix.py -f file.txt                     # 读取文件（可多次）
  garbled_fix.py -d dir/ -r                      # 递归扫描目录
  garbled_fix.py --json                          # JSON 输出（机器可读）
  garbled_fix.py --check -f data.csv             # 仅检测，有乱码退出码 1
  garbled_fix.py --demo                          # 生成各类型演示样本

设计要点:
  * detect()  特征正则 + 启发式判定类型（古文码需假名佐证，避免 emoji 误报）
  * fix()     BFS 多轮反向解码（双重乱码需 2-3 轮），按一级汉字区占比评分
              返回所有干净候选中评分最高者；含 U+FFFD 的乱码原字节已丢失，
              返回 None 属正确行为（需回源头重新读取）
  * 本文件是完整实现；SKILL.md 内嵌的便携版脚本（六种经典类型）与之保持同步
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

__version__ = "1.3.0"

# ============================================================
# 检测
# ============================================================

# 假名 + CJK 兼容符：古文码的高频佐证字符（正常中文几乎不含）
KANA_CJK = re.compile(r"[぀-ヿ︰-﹏]")
# cp1252 误读 UTF-8 的典型序列：UTF-8 双字节（C2/C3 开头）按 cp1252 读
CP1252_PAT = re.compile(r"â[€œš™¤¢¦]|Ã[©«¯°©±ª]|Â[£¥§¨°±²]")

# 隐形码预过滤（C 速度正则先扫一遍，clean 文本直接短路，避免逐字符循环拖慢 BFS）
INV_PREFILTER = re.compile(
    r"[\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff"
    r"[\ufe00-\ufe0f\U000e0000-\U000e007f\U000e0100-\U000e01ef]"
)
# emoji 疑似基字符：ZWJ 序列与 VS16 表现层（红心+VS16 之类）的语境判断用；
# U+2100-U+2BFF 已覆盖箭头/杂项符号/杂锦符号，另补 (C)(R)(TM)
EMOJIISH = re.compile(
    r"[\u2100-\u2bff\U0001f000-\U0001faff\u00a9\u00ae\u2122]"
)

TYPE_NAMES = {
    "mojibake-guwen": "古文码（GBK 误读 UTF-8）",
    "mojibake-kou": "口字码（UTF-8 误读 GBK）",
    "mojibake-fuhao": "符号码（ISO8859-1 误读 UTF-8）",
    "mojibake-pinyin": "拼音码（ISO8859-1 误读 GBK）",
    "mojibake-wenju": "问句码（GBK 读 UTF-8 字节残缺）",
    "mojibake-kunkao": "锟拷码（U+FFFD 被 GBK 重读）",
    "html-double-escape": "转义码（HTML 双重转义）",
    "lone-surrogate": "代理码（孤立代理项）",
    "cp1252-misread": "cp1252码（Windows-1252 误读 UTF-8）",
    "utf16-misread": "UTF16码（UTF-16 误读）",
    "c1-control": "控制码（C1 控制符密集）",
    "invisible": "隐形码（不可见 Unicode：零宽/bidi/tag/变体选择符）",
}


def _ratio(s: str, pattern: str) -> float:
    """pattern 命中的字符占总长度比例"""
    if not s:
        return 0.0
    return len(re.findall(pattern, s)) / len(s)


def _emojiish(c: str) -> bool:
    """是否 emoji 疑似基字符（ZWJ/VS 的语境判断）"""
    return bool(c) and bool(EMOJIISH.match(c))


def _iter_invisible(s: str):
    """产出 (索引, 类别)：可行动的隐形字符位置。

    不计（正常文本合法出现）：文件头 BOM（U+FEFF 首位）、emoji 语境的
    ZWJ（\u200d 夹在 emoji 基字符之间）与 VS16（如 \u2764\ufe0f）、
    游离 <3 个的变体选择符（排版噪音）。
    """
    for i, c in enumerate(s):
        if c in "\u200b\u200c\u2060\u180e":
            yield i, "零宽"
        elif c == "\ufeff":
            if i > 0:
                yield i, "零宽"  # 文件头 BOM 除外
        elif c == "\u200d":
            prev = s[i - 1] if i else ""
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if not (_emojiish(prev) or _emojiish(nxt)):
                yield i, "零宽"
        elif "\U000e0000" <= c <= "\U000e007f":
            yield i, "tag"
        elif "\U000e0100" <= c <= "\U000e01ef":
            yield i, "变体选择符"
        elif ("\u202a" <= c <= "\u202e" or "\u2066" <= c <= "\u2069"
              or c in "\u200e\u200f\u2061\u2062\u2063\u2064"):
            yield i, "bidi/运算符"
        elif "\ufe00" <= c <= "\ufe0f":
            prev = s[i - 1] if i else ""
            if not _emojiish(prev):
                yield i, "变体选择符(游离)"


def invisible_inventory(s: str) -> dict[str, int]:
    """按类别统计可行动的隐形字符；空 dict = 无隐形码"""
    if not s or not INV_PREFILTER.search(s):
        return {}
    inv: dict[str, int] = {}
    for _, cat in _iter_invisible(s):
        inv[cat] = inv.get(cat, 0) + 1
    # 游离变体选择符（非 emoji 语境的 VS1-16）<3 个视为表现层噪音；
    # 成批出现才是 VS 隐写/注水的特征
    if inv.get("变体选择符(游离)", 0) < 3:
        inv.pop("变体选择符(游离)", None)
    return inv


def detect(s: str) -> str | None:
    """识别乱码类型，返回类型 key；未识别返回 None"""
    if not s:
        return None
    # —— 扩展类型：具体特征优先 ——
    if re.search(r"&amp;(amp;|lt;|gt;|quot;|#\d+;)", s, re.I):
        return "html-double-escape"
    if re.search(r"[\ud800-\udfff]", s):
        return "lone-surrogate"
    if invisible_inventory(s):
        return "invisible"
    # —— 经典类型 ——
    if "锟斤拷" in s or (s.count("拷") >= 3 and "锟" in s):
        return "mojibake-kunkao"
    if re.search(r"[�■◆●□▲]", s):
        return "mojibake-kou"
    # —— 扩展类型：宽泛特征 ——
    if CP1252_PAT.search(s):
        return "cp1252-misread"
    if _ratio(s, r"[\u0080-\u009f]") > 0.3:
        # C1 控制符在 latin-1 占比检测范围内，必须先判
        return "c1-control"
    # 符号码/拼音码本质：文本大部分是 latin-1 扩展字符（U+0080-U+00FF）。
    # 区分：拼音码（GBK→latin-1）字符普遍 ≥U+00C0；符号码（UTF-8→latin-1）
    # 大量 0xA0-0xBF 区间字符（¥½¦¹¤© 等）
    if _ratio(s, r"[\u0080-\u00ff]") > 0.5:
        if _ratio(s, r"[\u00c0-\u00ff]") > 0.4:
            return "mojibake-pinyin"
        return "mojibake-fuhao"
    if "\x00" in s or _ratio(s, r"[\uff00-\uffef]") > 0.5:
        return "utf16-misread"
    if s.rstrip().endswith("?"):
        return "mojibake-wenju"
    # 古文码：汉字密集 + 含假名/CJK 兼容符佐证（正常中文几乎不含假名与 U+FE30-FE4F，
    # emoji/生僻字文本不含——不会误报）
    han = sum(1 for c in s if "一" <= c <= "鿿")
    if han >= max(3, len(s) * 0.3) and KANA_CJK.search(s):
        return "mojibake-guwen"
    return None


# ============================================================
# 评分
# ============================================================

def clean_score(t: str) -> float:
    """文本可读性评分 0-1，双路径：

    1) 含汉字 → 一级汉字区（0xB0A1-0xD7F9 常用字）占比 ≥0.6 才给分，
       伪古文（生僻字/异体字密集）占比低得 0 分。
    2) 无汉字 → 可打印且非 CJK（<U+3000）字符占比 ≥0.9 才给分，
       覆盖英文/符号文本（如 cp1252 误读的 "café — €"），
       伪还原的 CJK 生僻字（>U+3000）自然被排除。
    """
    if detect(t) or re.search(r"[�■◆●□▲]", t) or "�" in t:
        return 0.0
    # U+FFFD 的 UTF-8 字节（EF BF BD）按 cp1252/latin-1 误读的表示——替换符痕迹，不可信
    if re.search(r"ï¿½|Ã¿", t):
        return 0.0
    if not t or len(t) < 3:
        return 0.0
    han = [c for c in t if "一" <= c <= "鿿"]
    if han:
        if len(han) < max(3, len(t) * 0.4):
            return 0.0
        try:
            t.encode("gbk")  # 全文本必须 GBK 可编码：伪还原常混入谚文/私有区/emoji，
            # 而正常中文（含标点）全文本 GBK 均可编码
        except UnicodeEncodeError:
            return 0.0
        try:
            level1 = sum(
                1 for c in han if 0xB0A1 <= int.from_bytes(c.encode("gbk"), "big") <= 0xD7F9
            )
        except UnicodeEncodeError:
            return 0.0  # 含 GBK 外字符 → 伪古文等中间态
        ratio = level1 / len(han)
        return ratio if ratio >= 0.6 else 0.0
    # 无汉字：可打印 + 非 CJK 密集（伪还原的生僻字 >U+3000 不算）；
    # 换行/制表等空白属正常文本，计入可读字符
    good = sum(1 for c in t if (c.isprintable() or c in "\n\r\t") and ord(c) < 0x3000)
    return 1.0 if good / len(t) >= 0.9 else 0.0


# ============================================================
# 修复
# ============================================================

ENCODINGS = ("latin-1", "utf-8", "gbk", "cp1252")
DECODINGS = ("utf-8", "gbk", "gb18030", "utf-16-le", "utf-16-be", "utf-16", "cp1252")


def fix_html_entities(s: str) -> str | None:
    """修复重复 HTML 转义（&amp;amp; → &amp; → &），循环 unescape 直到稳定"""
    if "&amp;" not in s and "&lt;" not in s and "&gt;" not in s:
        return None
    prev = s
    for _ in range(5):
        nxt = html.unescape(prev)
        if nxt == prev:
            break
        prev = nxt
    if prev != s and not re.search(r"&(amp|lt|gt|quot|#\d+);", prev, re.I):
        return f"html.unescape: {prev}"
    return None


def fix(s: str) -> str | None:
    """BFS 多轮反向还原（双重乱码需要 2-3 轮），返回所有干净候选中评分最高者"""
    r = fix_html_entities(s)
    if r:
        return r
    kind = detect(s)
    if kind == "invisible":
        return fix_invisible(s)
    if kind in ("c1-control", "mojibake-kunkao"):
        # c1-control：GBK 字节流的单字节残留，需与相邻字节重新配对（字节重组问题），
        # 单文本 BFS 链无法可靠还原。
        # mojibake-kunkao：含"锟斤拷"即证明经历过 U+FFFD 替换（EF BF BD 流），
        # 原始字节必然已丢失，任何字节级还原都不可信。
        return None
    if "�" in s:
        # 含替换符 U+FFFD：原字节已丢失（口字码/锟拷码等），
        # 字节级反向还原会产生不可信的"伪还原"，直接判定不可还原
        return None
    # 汉字密集的输入，其还原结果也必须是汉字文本——编码链不会把汉字变成纯拉丁字符，
    # 纯拉丁候选（如 utf-8→cp1252 链的伪还原）不可信
    src_han_ratio = sum(1 for c in s if "一" <= c <= "鿿") / max(1, len(s))
    frontier, seen, best = {s}, {s}, None
    for _ in range(4):
        nxt = set()
        for cur in frontier:
            for enc in ENCODINGS:
                try:
                    b = cur.encode(enc)
                except UnicodeEncodeError:
                    continue
                for dec in DECODINGS:
                    try:
                        r2 = b.decode(dec)
                    except (UnicodeDecodeError, ValueError):
                        continue
                    if r2 in seen:
                        continue
                    seen.add(r2)
                    score = clean_score(r2)
                    if src_han_ratio > 0.3 and not any("一" <= c <= "鿿" for c in r2):
                        score = 0.0  # 汉字密集输入的候选必须含汉字
                    if score >= 0.6 and r2 != s:
                        if not best or score > best[0]:
                            best = (score, f"{enc}→{dec}: {r2}")
                    else:
                        nxt.add(r2)
        if not nxt:
            break
        frontier = nxt
    return best[1] if best else None


def fix_invisible(s: str) -> str:
    """隐形码修复：剥离可行动的不可见字符（不是编码错误，剥离即还原）"""
    inv = invisible_inventory(s)
    drop = {i for i, cat in _iter_invisible(s) if cat in inv}
    label = "+".join(f"{cat}x{n}" for cat, n in inv.items())
    cleaned = "".join(c for i, c in enumerate(s) if i not in drop)
    return f"strip-invisible({label}): {cleaned}"


# ============================================================
# 演示样本
# ============================================================

def demo_samples() -> dict[str, str]:
    """用真实编码错误链生成各类型乱码样本"""
    orig = "好好学习天天向上"
    u8 = orig.encode("utf-8")
    gb = orig.encode("gbk")
    return {
        "mojibake-guwen": u8.decode("gbk"),                                            # GBK 读 UTF-8
        "mojibake-kou": gb.decode("utf-8", errors="replace"),                          # UTF-8 读 GBK
        "mojibake-fuhao": u8.decode("latin-1"),                                        # latin-1 读 UTF-8
        "mojibake-pinyin": gb.decode("latin-1"),                                       # latin-1 读 GBK
        "mojibake-wenju": u8.decode("gbk", errors="replace"),                          # GBK 读 UTF-8 残缺
        "mojibake-kunkao": gb.decode("utf-8", errors="replace").encode("utf-8").decode("gbk"),
        "html-double-escape": "a &amp;amp; b &lt;tag&gt; &amp;#123;",
        "lone-surrogate": "前半\ud800后半",                                            # 孤立高代理项
        # 所有字节在 cp1252 中均有定义（避免 0x81/0x8D/0x9D 未定义字节产生替换符；
        # 注意不能用 U+201D 右引号，其 UTF-8 含 0x9D）
        "cp1252-misread": "café — € ½".encode("utf-8").decode("cp1252"),
        # 混合文本（ASCII+中文）的 UTF-16LE 误读：ASCII 的 LE 字节含 NUL（\x00）特征
        "utf16-misread": "abc 学习编程".encode("utf-16-le").decode("latin-1"),
        "c1-control": "\u0080\u0081\u0082\u0083\u0090中文",        # C1 控制符密集
        "invisible": "隐藏\u200b的\u2060标记\u202e与\U000e0041注入",
    }


# ============================================================
# CLI
# ============================================================

def _collect_inputs(args) -> list[tuple[str, str]]:
    """收集所有输入：命令行文本 / 文件 / 目录，返回 [(名称, 文本)]"""
    inputs: list[tuple[str, str]] = []
    for t in args.texts:
        inputs.append(("text", t))
    for f in args.file or []:
        p = Path(f)
        if not p.exists():
            print(f"错误: 文件不存在 {f}", file=sys.stderr)
            continue
        try:
            inputs.append((f, p.read_text(encoding="utf-8", errors="replace")))
        except OSError as e:
            print(f"错误: 无法读取 {f}: {e}", file=sys.stderr)
    if args.dir:
        base = Path(args.dir)
        if not base.is_dir():
            print(f"错误: 目录不存在 {args.dir}", file=sys.stderr)
        else:
            pattern = "**/*" if args.recursive else "*"
            for p in sorted(base.glob(pattern)):
                if p.is_file():
                    try:
                        inputs.append((str(p), p.read_text(encoding="utf-8", errors="replace")))
                    except OSError:
                        pass
    return inputs


def main(argv=None) -> int:
    # Windows 控制台默认 GBK：强制 UTF-8 输出，避免 CLI 自身产生显示乱码
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(
        prog="garbled_fix",
        description="乱码检测与修复：六种经典乱码 + 六种扩展类型（含隐形码）。"
                    "detect 判定类型，fix BFS 多轮反向还原。",
        epilog="示例: garbled_fix.py -f 乱码.txt --json | garbled_fix.py --demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("texts", nargs="*", help="直接传入的乱码文本")
    ap.add_argument("-f", "--file", action="append", help="读取文件（可多次指定）")
    ap.add_argument("-d", "--dir", help="扫描目录中的文件")
    ap.add_argument("-r", "--recursive", action="store_true", help="与 -d 配合，递归子目录")
    ap.add_argument("--json", action="store_true", help="JSON 输出（机器可读）")
    ap.add_argument("--check", action="store_true",
                    help="仅检测不修复；任一输入判定为乱码时退出码为 1")
    ap.add_argument("--demo", action="store_true", help="生成各类型演示样本并检测")
    ap.add_argument("--version", action="version", version=f"garbled_fix {__version__}")
    args = ap.parse_args(argv)

    if args.demo:
        results = []
        for key, sample in demo_samples().items():
            kind = detect(sample)
            results.append({
                "name": TYPE_NAMES.get(key, key),
                "sample": sample,
                "detected": kind,
                "fix": fix(sample) or "不可还原",
            })
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for r in results:
                fix_out = r["fix"]
                if isinstance(fix_out, str) and ": " in fix_out:
                    fix_out = fix_out.split(": ", 1)[1]
                print(f"[{r['name']}] 判定={r['detected']} | 修复={fix_out}")
        return 0

    inputs = _collect_inputs(args)
    if not inputs:
        ap.print_help()
        return 2

    results = []
    any_garbled = False
    for name, text in inputs:
        kind = detect(text)
        if kind:
            any_garbled = True
        r = fix(text) if kind else None
        results.append({"name": name, "detected": kind, "fix": r})

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            status = "✓ 正常" if not r["detected"] else f"乱码: {TYPE_NAMES.get(r['detected'], r['detected'])}"
            print(f"{r['name']}: {status}")
            if r["fix"]:
                fixed = r["fix"].split(": ", 1)[1] if ": " in r["fix"] else r["fix"]
                print(f"   修复 ({r['fix'].split(': ', 1)[0]}): {fixed}")
            elif r["detected"]:
                print("   无法自动还原（可能已丢失信息，如 U+FFFD 替换符）→ 回源头重新读取")
    return 1 if (args.check and any_garbled) else 0


if __name__ == "__main__":
    sys.exit(main())
