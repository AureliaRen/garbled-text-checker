#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公式码（LaTeX 残留拉平）测试：scripts/latex_to_text.py"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "latex_to_text.py")


def run(*args, stdin=None):
    return subprocess.run([sys.executable, "-X", "utf8", SCRIPT, *args],
                          input=stdin, capture_output=True, text=True,
                          encoding="utf-8")


class TestLatexToText(unittest.TestCase):

    def test_demo_selfcheck(self):
        """--demo 内置 8 项断言全部通过"""
        r = run("--demo")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("自检: 通过（8/8）", r.stdout)

    def test_delimiters_and_frac(self):
        """$$..$$ 定界符剥除 + frac 拉平 + 符号替换"""
        r = run("$$pV = \\frac{m}{M}RT \\quad\\Leftrightarrow\\quad pV = NkT$$")
        self.assertIn("pV = m/M RT ⇔ pV = NkT", r.stdout)
        self.assertNotIn("\\frac", r.stdout)
        self.assertNotIn("$$", r.stdout)

    def test_sup_sub_and_greek(self):
        """上下标 Unicode 化 + 希腊字母/度数"""
        r = run("$N = 6.02\\times10^{23}$，\\alpha = 10^{-3}/K，T = 47\\,^{\\circ}C")
        self.assertIn("6.02×10²³", r.stdout)
        self.assertIn("α = 10⁻³/K", r.stdout)
        self.assertIn("47 °C", r.stdout)

    def test_frac_in_sqrt_nested(self):
        """sqrt 内嵌 frac：由内向外剥"""
        r = run("v_\\text{rms} = \\sqrt{\\frac{3RT}{M}}")
        self.assertIn("v_rms = √(3RT/M)", r.stdout)

    def test_snake_case_untouched(self):
        """裸 _x/_n 为字母时不转下标（防 snake_case 误伤）"""
        r = run("file_name and my_var stay plain")
        self.assertIn("file_name", r.stdout)
        self.assertIn("my_var", r.stdout)

    def test_check_exit_codes(self):
        """--check：有残留 exit 1，干净文本 exit 0"""
        dirty = run("--check", "$$x^{2}$$")
        self.assertEqual(dirty.returncode, 1)
        self.assertIn("公式码残留", dirty.stdout)
        clean = run("--check", "plain text pV = nkT only")
        self.assertEqual(clean.returncode, 0)
        self.assertIn("无 LaTeX 残留", clean.stdout)

    def test_file_inplace_and_check(self):
        """文件模式：--check 判残留 → 原地拉平 → 复检干净"""
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "note.md")
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write("理想气体 $$pV = nkT$$ 状态方程\n")
            self.assertEqual(run("--check", "-f", p).returncode, 1)
            self.assertEqual(run("-f", p).returncode, 0)
            with open(p, encoding="utf-8") as f:
                out = f.read()
            self.assertNotIn("$$", out)
            self.assertIn("pV = nkT", out)
            self.assertEqual(run("--check", "-f", p).returncode, 0)

    def test_stdin_pipe(self):
        """管道输入"""
        r = run(stdin="含 $10^{23}$ 的文本")
        self.assertIn("10²³", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
