#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PostToolUse hook: 检测工具输出中的编码报错/乱码特征，命中时注入提醒让 Claude 调用 garbled-text-checker skill。

用法: 在 settings.json 的 PostToolUse hooks (matcher: Bash|Read) 中配置:
    python "C:\\Users\\任泽鑫\\.claude\\hooks\\check-garbled.py"
stdin 接收 hook 输入 JSON，命中时 stdout 输出带 additionalContext 的 JSON。
"""
import json
import re
import sys

# 强信号：编码错误描述短语——几乎不会出现在正常代码/文档里
# （代码里常见的只是异常类名，如 `except UnicodeEncodeError:`，不是报错本身）
STRONG = re.compile(
    r"'[a-z0-9_.-]+' codec can't (encode|decode)|"
    r"invalid (start|continuation) byte|illegal multibyte sequence|"
    r"cannot encode character|cannot decode byte|incomplete multibyte sequence",
    re.I,
)
# 弱信号：异常类名——代码/文档里常见，必须带 traceback 佐证才算真实报错
WEAK = re.compile(r"Unicode(Encode|Decode|Translate)Error", re.I)
# 乱码特征字符：锟拷码/口字码/符号码/拼音码的高频字符
MOJI = "锟斤拷\ufffd■◆●□▲〇çæèåïøðþêâîôûÿÓÉÔÂÒÅÇÑÍ"
# 配置文件（hooks/skills 目录）含检测特征词属正常，跳过
CONFIG_DIR = re.compile(r"[\\/]\.claude[\\/](hooks|skills)[\\/]")


def detect(text: str):
    """返回 (是否命中, 类型描述)；未命中返回 (False, None)

    编码报错：强信号短语直接命中，或异常类名 + Traceback 佐证。
    乱码：按"行级占比"判断——乱码文本整行都是乱码字符，
    而讨论乱码的文档/代码示例只是零星出现，不会整行被污染。
    """
    if not text:
        return False, None
    if STRONG.search(text) or (WEAK.search(text) and "Traceback" in text):
        return True, "编码报错"
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        # 拉丁扩展字符（U+00A0-U+00FF）：符号码/拼音码的字符全集，
        # 正常中文/英文文本一行内几乎不会过半出现
        lat = sum(1 for ch in line if " " <= ch <= "ÿ")
        if lat / len(line) > 0.5:
            return True, "符号码/拼音码乱码（拉丁扩展字符占比过高）"
        moji = sum(1 for ch in line if ch in MOJI)
        if moji / len(line) > 0.4:
            return True, "乱码文本（行内乱码字符占比过高）"
    if len(re.findall(r"[\ufffd\u25a0\u25c6\u25cf\u25a1\u25b2\u3007]", text)) >= 2:
        return True, "口字码乱码（含替换符/方块字符）"
    return False, None


def collect_strings(obj):
    """递归提取所有字符串值（避免嵌套字段漏检）"""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from collect_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from collect_strings(v)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # 输入异常不阻断主流程

    fp = (data.get("tool_input") or {}).get("file_path") or ""
    if CONFIG_DIR.search(fp):
        return  # hooks/skills 配置文件含检测特征词属正常，跳过
    text = "\n".join(collect_strings(data.get("tool_response") or {}))
    hit, kind = detect(text)
    if not hit:
        return  # 无输出 = 不注入

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"[乱码检测] 工具输出疑似{kind}。请调用 garbled-text-checker skill "
                "（C:\\Users\\任泽鑫\\.claude\\skills\\garbled-text-checker\\SKILL.md）"
                "：先判定乱码类型，再用其内嵌脚本反向还原；若是编码报错，先修正编码设置，"
                "再按该 skill 的预防规则避免复发。"
            ),
        }
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
