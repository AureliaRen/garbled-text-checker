# -*- coding: utf-8 -*-
"""scripts/garbled_fix.py 完整版 CLI 回归测试。

运行: python tests/test_cli.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
SCRIPT = str(PROJ / "scripts" / "garbled_fix.py")

ORIG = "好好学习天天向上"


def run_cli(*args, expect_code=0):
    """运行 CLI，返回 (returncode, stdout)"""
    p = subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert p.returncode == expect_code, f"exit={p.returncode} 期望 {expect_code}\nstdout={p.stdout}\nstderr={p.stderr}"
    return p.returncode, p.stdout


class TestCLIBasic(unittest.TestCase):
    def test_direct_text(self):
        """直接传乱码文本，应输出判定与修复"""
        sample = ORIG.encode("utf-8").decode("latin-1")  # 符号码
        _, out = run_cli(sample)
        self.assertIn("乱码", out)
        self.assertIn(ORIG, out)

    def test_clean_text(self):
        """正常文本应输出"正常"且 exit 0"""
        _, out = run_cli("正常文本没问题")
        self.assertIn("正常", out)

    def test_version(self):
        """--version 输出符合语义化版本格式（不写死具体版本号）"""
        import re
        _, out = run_cli("--version")
        self.assertRegex(out, r"garbled_fix \d+\.\d+\.\d+")

    def test_no_args_help(self):
        """无参数应显示帮助并 exit 2"""
        with self.assertRaises(AssertionError):
            run_cli()  # 期望非 0


class TestCLIFiles(unittest.TestCase):
    def _tmp(self, name, content):
        p = PROJ / "tests" / name
        p.write_text(content, encoding="utf-8")
        self.addCleanup(p.unlink)
        return str(p)

    def test_file_mode(self):
        f = self._tmp("_t_moji.txt", ORIG.encode("utf-8").decode("latin-1"))
        _, out = run_cli("-f", f)
        self.assertIn(ORIG, out)

    def test_check_exit_codes(self):
        """--check：有乱码 exit 1，无乱码 exit 0"""
        bad = self._tmp("_t_bad.txt", ORIG.encode("utf-8").decode("latin-1"))
        good = self._tmp("_t_good.txt", "正常文本没问题")
        run_cli("--check", "-f", bad, expect_code=1)
        run_cli("--check", "-f", good, expect_code=0)

    def test_json_output(self):
        f = self._tmp("_t_json.txt", ORIG.encode("utf-8").decode("latin-1"))
        _, out = run_cli("-f", f, "--json")
        data = json.loads(out)
        self.assertEqual(len(data), 1)
        self.assertIsNotNone(data[0]["detected"])
        self.assertIn(ORIG, data[0]["fix"])

    def test_dir_scan(self):
        """目录递归扫描能找到乱码文件"""
        self._tmp("_t_dir_bad.txt", ORIG.encode("utf-8").decode("latin-1"))
        run_cli("-d", str(PROJ / "tests"), "-r", "--check", expect_code=1)


class TestDemo(unittest.TestCase):
    def test_demo_all_types(self):
        """demo 生成全部 12 种类型且每种都被判定"""
        _, out = run_cli("--demo", "--json")
        data = json.loads(out)
        self.assertEqual(len(data), 12)
        for item in data:
            with self.subTest(name=item["name"]):
                self.assertIsNotNone(item["detected"], f"{item['name']} 未被判定")

    def test_demo_restore_types(self):
        """demo 中可还原类型（古文/符号/拼音/问句/转义/cp1252/UTF16）都应还原"""
        _, out = run_cli("--demo", "--json")
        data = json.loads(out)
        for item in data:
            if any(k in item["name"] for k in ("古文码", "符号码", "拼音码", "问句码",
                                               "转义码", "cp1252码", "UTF16码", "隐形码")):
                with self.subTest(name=item["name"]):
                    self.assertNotEqual(item["fix"], "不可还原", f"{item['name']} 应可还原")

    def test_demo_unrecoverable_types(self):
        """口字码/锟拷码/代理码/控制码应判定不可还原（信息丢失）"""
        _, out = run_cli("--demo", "--json")
        data = json.loads(out)
        for item in data:
            if any(k in item["name"] for k in ("口字码", "锟拷码", "代理码", "控制码")):
                with self.subTest(name=item["name"]):
                    self.assertEqual(item["fix"], "不可还原")


class TestInvisible(unittest.TestCase):
    """隐形码（第 12 类）：不可见 Unicode 检测与剥离。

    测试字符一律用 chr() 构造——源码里写不可见字符字面量本身就是反模式。
    """

    def _tmp(self, name, content):
        p = PROJ / "tests" / name
        p.write_text(content, encoding="utf-8")
        self.addCleanup(p.unlink)
        return str(p)

    def test_detect_and_strip(self):
        """零宽/bidi/tag 字符应判定为隐形码并剥离出干净文本"""
        s = "隐藏" + chr(0x200B) + "的" + chr(0x202E) + "标记" + chr(0xE0041) + "注入"
        _, out = run_cli(s)
        self.assertIn("隐形码", out)
        self.assertIn("隐藏的标记注入", out)

    def test_check_exit_code(self):
        """--check：含隐形码的文件 exit 1"""
        f = self._tmp("_t_inv.txt", "隐藏" + chr(0x200B) + "文本")
        run_cli("--check", "-f", f, expect_code=1)

    def test_bom_not_flagged(self):
        """文件头 BOM（U+FEFF）属正常，不应判定"""
        _, out = run_cli(chr(0xFEFF) + "开头BOM的正常文本")
        self.assertIn("正常", out)

    def test_emoji_zwj_sequence_not_flagged(self):
        """emoji ZWJ 序列（家庭 emoji）属正常，不应判定"""
        fam = chr(0x1F468) + chr(0x200D) + chr(0x1F469) + chr(0x200D) + chr(0x1F466)
        _, out = run_cli("家庭" + fam + "表情正常")
        self.assertIn("正常", out)

    def test_vs16_after_emoji_not_flagged(self):
        """emoji 后的变体选择符 VS16（红心 emoji）属正常，不应判定"""
        _, out = run_cli("红心" + chr(0x2764) + chr(0xFE0F) + "表情正常")
        self.assertIn("正常", out)

    def test_free_vs_threshold(self):
        """游离变体选择符：x2 不报（排版噪音），x3 判定（隐写特征）"""
        _, out = run_cli("文" + chr(0xFE01) + "字" + chr(0xFE01) + "噪音")
        self.assertIn("正常", out)
        f = self._tmp("_t_vs.txt", "文" + chr(0xFE01) * 3 + "字")
        run_cli("--check", "-f", f, expect_code=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
