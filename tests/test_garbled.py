# -*- coding: utf-8 -*-
"""garbled-text-checker skill 内嵌脚本回归测试。

运行: python tests/test_garbled.py   （或 python -m unittest tests.test_garbled）
"""
import re
import sys
import unittest
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
SKILL_MD = PROJ / "SKILL.md"

# 从 SKILL.md 提取内嵌脚本并加载 detect/fix
md = SKILL_MD.read_text(encoding="utf-8")
m = re.search(r"python - <<'PY'\n(.*?)\nPY", md, re.S)
assert m, "SKILL.md 中未找到内嵌脚本"
NS = {"__name__": "__not_main__"}  # 阻止内嵌脚本的主执行代码在 import 时运行
exec(m.group(1), NS)
detect, fix = NS["detect"], NS["fix"]

ORIG = "好好学习天天向上"
U8 = ORIG.encode("utf-8")
GB = ORIG.encode("gbk")


class TestDetect(unittest.TestCase):
    def _make_samples(self):
        """六种真实编码错误链构造的乱码样本"""
        return {
            "古文码": U8.decode("gbk"),                                     # GBK 误读 UTF-8
            "口字码": GB.decode("utf-8", errors="replace"),                  # UTF-8 误读 GBK
            "符号码": U8.decode("latin-1"),                                  # latin-1 误读 UTF-8
            "拼音码": GB.decode("latin-1"),                                  # latin-1 误读 GBK
            "问句码": U8.decode("gbk", errors="replace"),                    # GBK 读 UTF-8 字节残缺
            "锟拷码": GB.decode("utf-8", errors="replace").encode("utf-8").decode("gbk"),
        }

    def test_fix_restores_reversible_types(self):
        """古文码/符号码/拼音码/问句码应还原为原文"""
        for name, s in self._make_samples().items():
            with self.subTest(name=name):
                if name in ("口字码", "锟拷码"):
                    continue  # 含 U+FFFD，信息丢失，不可还原（见 test_unrecoverable）
                r = fix(s)
                self.assertTrue(r and ORIG in r, f"{name} 未能还原: {r!r}")

    def test_detect_and_unrecoverable(self):
        """口字码/锟拷码应被判定且确认不可还原（U+FFFD 已替换）"""
        for name in ("口字码", "锟拷码"):
            with self.subTest(name=name):
                s = self._make_samples()[name]
                self.assertEqual(detect(s), name)
                self.assertIsNone(fix(s))

    def test_clean_text_not_flagged(self):
        """正常中文不应被判定为乱码，也不应被修改"""
        for t in ("今天天气真不错，适合出去走走。", "今天天气🚀真不错，适合出去走走。"):
            with self.subTest(t=t):
                self.assertIsNone(detect(t))
                self.assertIsNone(fix(t))

    def test_short_sample(self):
        """短样本不应崩溃"""
        self.assertIsNone(detect("好"))
        self.assertIsNone(fix(""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
