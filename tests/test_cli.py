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
        _, out = run_cli("--version")
        self.assertIn("1.1.0", out)

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
        """demo 生成全部 11 种类型且每种都被判定"""
        _, out = run_cli("--demo", "--json")
        data = json.loads(out)
        self.assertEqual(len(data), 11)
        for item in data:
            with self.subTest(name=item["name"]):
                self.assertIsNotNone(item["detected"], f"{item['name']} 未被判定")

    def test_demo_restore_types(self):
        """demo 中可还原类型（古文/符号/拼音/问句/转义/cp1252/UTF16）都应还原"""
        _, out = run_cli("--demo", "--json")
        data = json.loads(out)
        for item in data:
            if any(k in item["name"] for k in ("古文码", "符号码", "拼音码", "问句码",
                                               "转义码", "cp1252码", "UTF16码")):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
