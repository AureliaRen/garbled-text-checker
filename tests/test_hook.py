# -*- coding: utf-8 -*-
"""check-garbled.py hook 回归测试：命中/防误报场景。

运行: python tests/test_hook.py
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
HOOK = str(PROJ / "hooks" / "check-garbled.py")

# 真实乱码样本（与 test_garbled.py 同源）
ORIG = "好好学习天天向上"
U8 = ORIG.encode("utf-8")
GB = ORIG.encode("gbk")
SAMPLES = {
    "古文码": U8.decode("gbk"),
    "口字码": GB.decode("utf-8", errors="replace"),
    "符号码": U8.decode("latin-1"),
    "拼音码": GB.decode("latin-1"),
    "锟拷码": GB.decode("utf-8", errors="replace").encode("utf-8").decode("gbk"),
}


def run_hook(payload):
    """执行 hook，返回是否命中（stdout 非空）"""
    p = subprocess.run(
        [sys.executable, "-X", "utf8", HOOK],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8",
    )
    return bool(p.stdout.strip())


class TestHookHit(unittest.TestCase):
    """应当命中的场景"""

    def test_real_traceback(self):
        """真实 traceback（异常类名 + Traceback 佐证）"""
        out = "Traceback (most recent call last):\n  File \"<stdin>\", line 1\nUnicodeEncodeError: 'gbk' codec can't encode character"
        self.assertTrue(run_hook({"tool_name": "Bash", "tool_input": {"command": "x"},
                                  "tool_response": {"output": out, "success": False}}))

    def test_strong_phrase(self):
        """强信号短语（codec can't decode / invalid byte 等）"""
        for out in ("UnicodeDecodeError: 'utf-8' codec can't decode byte 0xba",
                    "UnicodeEncodeError: 'gbk' codec can't encode character",
                    "invalid start byte"):
            with self.subTest(out=out):
                self.assertTrue(run_hook({"tool_name": "Bash", "tool_input": {"command": "x"},
                                          "tool_response": {"output": out, "success": False}}))

    def test_garbled_samples(self):
        """六种乱码样本（锟拷码/口字码短样本/符号码/拼音码）"""
        cases = {
            "锟拷码": SAMPLES["锟拷码"],
            "口字码短样本": "学习��向上",
            "符号码": SAMPLES["符号码"],
            "拼音码": SAMPLES["拼音码"],
        }
        for name, out in cases.items():
            with self.subTest(name=name):
                self.assertTrue(run_hook({"tool_name": "Bash", "tool_input": {"command": "cat f"},
                                          "tool_response": {"output": out, "success": True}}))


class TestHookNoHit(unittest.TestCase):
    """不应命中的场景（防误报）"""

    def test_clean_outputs(self):
        """正常输出/正常中文"""
        for out in ("file1.txt\nfile2.txt", "今天天气真不错，适合出去走走。"):
            with self.subTest(out=out):
                self.assertFalse(run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"},
                                           "tool_response": {"output": out, "success": True}}))

    def test_code_with_except_clause(self):
        """代码里含 except UnicodeEncodeError（类名≠报错）"""
        code = "try:\n    print(x)\nexcept UnicodeEncodeError:\n    pass"
        self.assertFalse(run_hook({"tool_name": "Read", "tool_input": {"file_path": "C:/proj/a.py"},
                                   "tool_response": {"content": code}}))

    def test_config_files_skipped(self):
        """.claude/skills 与 .claude/hooks 下的配置文件直接跳过"""
        md = (PROJ / "SKILL.md").read_text(encoding="utf-8")
        hook_src = (PROJ / "hooks" / "check-garbled.py").read_text(encoding="utf-8")
        for path, content in (
            ("C:/Users/任泽鑫/.claude/skills/garbled-text-checker/SKILL.md", md),
            ("C:/Users/任泽鑫/.claude/hooks/check-garbled.py", hook_src),
        ):
            with self.subTest(path=path):
                self.assertFalse(run_hook({"tool_name": "Read", "tool_input": {"file_path": path},
                                           "tool_response": {"content": content}}))

    def test_garbled_mentions_in_doc(self):
        """讨论乱码的文档（零星提及）不误报——文件不在 .claude 下时靠行级占比"""
        doc = "乱码分为六种：古文码、口字码、符号码、拼音码、问句码、锟拷码。\n详见速查表。"
        self.assertFalse(run_hook({"tool_name": "Read", "tool_input": {"file_path": "C:/docs/note.md"},
                                   "tool_response": {"content": doc}}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
