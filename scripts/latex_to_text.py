#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""latex_to_text.py — 把终端里未渲染的 LaTeX 公式残留（公式码）拉平为可读纯文本。

公式码不属于编码错乱：输出端按 Markdown-LaTeX 写公式（$$..$$、\\frac、\\times、^{}`,
\\quad 等），而终端只按纯文本显示，命令原样漏出。处理策略 = 结构拉平 +
Unicode 符号替换，无 BFS 还原。

用法:
  python -X utf8 latex_to_text.py '$$pV = \\frac{m}{M}RT$$'   # 直接传文本
  python -X utf8 latex_to_text.py -f 笔记.md [-o out.md]       # 处理文件(单文件无 -o 原地覆盖)
  cat 笔记.md | python -X utf8 latex_to_text.py               # 管道
  python -X utf8 latex_to_text.py --check -f 笔记.md           # 仅检测(有残留 exit 1)
  python -X utf8 latex_to_text.py --demo                       # 自检样例

局限: 裸 _x/^x 仅转换数字和 +/-（防 snake_case 误伤）；复杂宏环境（amsmath 对齐、
\\begin{..}）不解析，走残留命令兜底剥反斜杠；--check 对 Windows 路径 C:\\Users 会误报。
"""
import re
import sys
import argparse

# ---------- 符号表（使用时按 key 长度降序匹配，防 \ne 抢 \neq、\in 抢 \int、\eta 抢 \beta）----------
SYMBOLS = {
    '\\Leftrightarrow': '⇔', '\\leftrightarrow': '↔', '\\Rightleftharpoons': '⇌',
    '\\Longrightarrow': '⟹', '\\longrightarrow': '⟶',
    '\\Rightarrow': '⇒', '\\leftarrow': '←', '\\rightarrow': '→',
    '\\Leftarrow': '⇐', '\\hookrightarrow': '↪', '\\mapsto': '↦', '\\to': '→',
    '\\approx': '≈', '\\simeq': '≃', '\\cong': '≅', '\\equiv': '≡', '\\sim': '∼',
    '\\neq': '≠', '\\ne': '≠',
    '\\leqslant': '≤', '\\geqslant': '≥',
    '\\leq': '≤', '\\geq': '≥', '\\le': '≤', '\\ge': '≥',
    '\\times': '×', '\\cdot': '·', '\\div': '÷',
    '\\pm': '±', '\\mp': '∓', '\\propto': '∝',
    '\\infty': '∞', '\\partial': '∂', '\\nabla': '∇',
    '\\sum': 'Σ', '\\prod': 'Π', '\\int': '∫', '\\oint': '∮',
    '\\degree': '°',
    '\\perp': '⊥', '\\parallel': '∥', '\\angle': '∠',
    '\\subseteq': '⊆', '\\subset': '⊂', '\\notin': '∉', '\\cup': '∪', '\\cap': '∩', '\\in': '∈',
    '\\Delta': 'Δ', '\\Gamma': 'Γ', '\\Theta': 'Θ', '\\Lambda': 'Λ', '\\Sigma': 'Σ',
    '\\Omega': 'Ω', '\\Phi': 'Φ', '\\Psi': 'Ψ', '\\Xi': 'Ξ', '\\Upsilon': 'Υ',
    '\\alpha': 'α', '\\beta': 'β', '\\gamma': 'γ', '\\delta': 'δ',
    '\\epsilon': 'ε', '\\varepsilon': 'ε', '\\zeta': 'ζ', '\\eta': 'η',
    '\\theta': 'θ', '\\vartheta': 'ϑ', '\\iota': 'ι', '\\kappa': 'κ',
    '\\lambda': 'λ', '\\mu': 'μ', '\\nu': 'ν', '\\xi': 'ξ', '\\pi': 'π',
    '\\rho': 'ρ', '\\sigma': 'σ', '\\varsigma': 'ς', '\\tau': 'τ',
    '\\upsilon': 'υ', '\\phi': 'φ', '\\varphi': 'φ', '\\chi': 'χ',
    '\\psi': 'ψ', '\\omega': 'ω', '\\hbar': 'ℏ', '\\ell': 'ℓ',
    '\\quad': ' ', '\\qquad': '  ',
    '\\,': ' ', '\\;': ' ', '\\:': ' ', '\\!': '',
    '\\left': '', '\\right': '', '\\displaystyle': '', '\\limits': '',
    '\\nolimits': '', '\\big': '', '\\Big': '', '\\bigg': '',
    '\\{': '{', '\\}': '}',
}

SUPER = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶',
         '7': '⁷', '8': '⁸', '9': '⁹', '+': '⁺', '-': '⁻', '−': '⁻',
         '(': '⁽', ')': '⁾', 'n': 'ⁿ', 'i': 'ⁱ',
         'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ',
         'h': 'ʰ', 'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'o': 'ᵒ', 'p': 'ᵖ',
         'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ', 'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ',
         'y': 'ʸ', 'z': 'ᶻ', 'T': 'ᵀ', 'N': 'ᴺ'}
SUB = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆',
       '7': '₇', '8': '₈', '9': '₉', '+': '₊', '-': '₋', '−': '₋',
       'a': 'ₐ', 'e': 'ₑ', 'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ', 'k': 'ₖ', 'l': 'ₗ',
       'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ', 'p': 'ₚ', 'r': 'ᵣ', 's': 'ₛ', 't': 'ₜ',
       'u': 'ᵤ', 'v': 'ᵥ', 'x': 'ₓ'}

MATH_TEXT_CMDS = re.compile(
    r'\\(?:text|mathrm|mathbf|mathit|mathcal|mathsf|mathtt|mathbb|operatorname'
    r'|textbf|textit|textup|emph|bm)\s*\{([^{}]*)\}')

# 仅检测用：出现即判定为公式码残留
LATEX_SIGNAL = re.compile(
    r'\$\$|\\frac\s*\{|\\sqrt\s*[{\[]|\\quad|\\qquad|\\times\b|\\cdot\b'
    r'|\\left\b|\\right\b|\^\{|_\{|\\[a-zA-Z]|\$[^$\n]+\$')


def _wrap(s: str) -> str:
    """frac 的分子/分母：含义简单就不加括号。"""
    s = s.strip()
    if any(ch in s for ch in ' +-−=·×/') or len(s) > 8:
        return '(' + s + ')'
    return s


def _frac_repl(m) -> str:
    num, den = _wrap(m.group(1)), _wrap(m.group(2))
    nxt = m.string[m.end():m.end() + 1]
    # 分母是裸词且后面紧跟字母数字时补空格，防 m/M+RT 黏成 m/MRT
    if not den.startswith('(') and nxt and (nxt.isalnum()):
        den += ' '
    return num + '/' + den


def _sub_braced(text: str, pattern: str, table: dict, fmt_fallback) -> str:
    """把 ^{...}/_{...} 拉平；字符全在映射表才用 Unicode，否则走兜底格式。"""
    pat = re.compile(pattern)
    while True:
        m = pat.search(text)
        if not m:
            return text
        content = m.group(1)
        if content and all(ch in table for ch in content):
            rep = ''.join(table[ch] for ch in content)
        else:
            rep = fmt_fallback(content)
        text = text[:m.start()] + rep + text[m.end():]


def latex_to_text(s: str) -> str:
    # 1) 剥定界符：$$..$$、\[..\]、\(..\)、$..$
    s = re.sub(r'\$\$(.+?)\$\$', r'\1', s, flags=re.S)
    s = re.sub(r'\\\[(.+?)\\\]', r'\1', s, flags=re.S)
    s = re.sub(r'\\\((.+?)\\\)', r'\1', s, flags=re.S)
    s = re.sub(r'(?<![\w$])\$([^$\n]+?)\$(?![\w$])', r'\1', s)
    # 2) 度数（须在上下标之前）
    s = s.replace('^{\\circ}', '°').replace('^\\circ', '°')
    # 3) frac（由内向外循环剥，须在 sqrt 之前，sqrt 体里常有 frac）
    while True:
        new = re.sub(r'\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}', _frac_repl, s)
        if new == s:
            break
        s = new
    # 4) 根号
    s = re.sub(r'\\sqrt\s*\[([^\]]+)\]\s*\{([^{}]*)\}',
               lambda m: _wrap(m.group(2)) + '^(1/' + m.group(1).strip() + ')', s)
    s = re.sub(r'\\sqrt\s*\{([^{}]*)\}', lambda m: '√(' + m.group(1) + ')', s)
    # 5) 文本类命令保留内容
    while MATH_TEXT_CMDS.search(s):
        s = MATH_TEXT_CMDS.sub(r'\1', s)
    # 6) 上下标：带花括号的全转；裸 ^x/_x 仅数字和 +/-(防 snake_case 误伤)
    s = _sub_braced(s, r'\^\{([^{}]*)\}', SUPER, lambda c: '^(' + c + ')')
    s = _sub_braced(s, r'_\{([^{}]*)\}', SUB, lambda c: '_(' + c + ')')
    s = re.sub(r'(?<=[\w)\]])\^([0-9+−-])', lambda m: SUPER.get(m.group(1), m.group(1)), s)
    s = re.sub(r'(?<=[\w)\]])_([0-9+−-])', lambda m: SUB.get(m.group(1), m.group(1)), s)
    # 7) 符号表整体替换（长命令优先）
    for cmd in sorted(SYMBOLS, key=len, reverse=True):
        s = s.replace(cmd, SYMBOLS[cmd])
    # 8) 兜底：残余命令剥反斜杠留名字，清孤儿花括号
    s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)
    s = s.replace('{', '').replace('}', '')
    # 9) 排版清理
    s = re.sub(r'[ \t]{2,}', ' ', s)
    s = re.sub(r' +([,.;:!?，。；：！？])', r'\1', s)
    return s.strip()


def has_latex(s: str) -> bool:
    return bool(LATEX_SIGNAL.search(s))


def main():
    ap = argparse.ArgumentParser(description='LaTeX 公式残留(公式码)拉平为纯文本')
    ap.add_argument('text', nargs='*', help='直接传文本')
    ap.add_argument('-f', '--file', action='append', default=[], help='输入文件(可多个)')
    ap.add_argument('-o', '--output', help='输出文件(与多 -f 合用=合并输出)')
    ap.add_argument('--check', action='store_true', help='仅检测，有残留 exit 1')
    ap.add_argument('--demo', action='store_true', help='运行自检样例')
    args = ap.parse_args()

    if args.demo:
        demos = [
            '$$pV = \\frac{m}{M}RT \\quad\\Leftrightarrow\\quad pV = NkT '
            '\\quad\\Leftrightarrow\\quad p = nkT$$',
            'v_\\text{rms} = \\sqrt{\\frac{3RT}{M}}，$N = 6.02\\times10^{23}$',
            'T = 47\\,^{\\circ}C，p = 10^{5}\\,Pa，\\alpha = 10^{-3}/K',
        ]
        for d in demos:
            print('原文: %s\n拉平: %s\n' % (d, latex_to_text(d)))
        joined = ' '.join(latex_to_text(d) for d in demos)
        expects = ['m/M', '⇔', 'NkT', '√(3RT/M)', '×10²³', '47 °C', '10⁵ Pa', '10⁻³/K']
        missing = [e for e in expects if e not in joined]
        print('自检:', '通过（%d/%d）' % (len(expects) - len(missing), len(expects))
              if not missing else '失败: 未找到 %r' % missing)
        sys.exit(0 if not missing else 1)

    if args.check:
        if args.file:
            src = '\n'.join(open(f, encoding='utf-8').read() for f in args.file)
        elif args.text:
            src = ' '.join(args.text)
        else:
            src = sys.stdin.read()
        found = has_latex(src)
        print('判定:', '公式码残留（终端会显示原始 LaTeX 标记）' if found else '无 LaTeX 残留')
        sys.exit(1 if found else 0)

    if args.file:
        if args.output:
            src = '\n'.join(open(f, encoding='utf-8').read() for f in args.file)
            with open(args.output, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(latex_to_text(src))
            print('修复: 已写入 %s' % args.output)
        else:
            for f in args.file:  # 单文件原地覆盖；多文件各自原地
                with open(f, encoding='utf-8') as fh:
                    src = fh.read()
                with open(f, 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write(latex_to_text(src))
                print('修复: %s (原地覆盖)' % f)
    elif args.text:
        sys.stdout.buffer.write(latex_to_text(' '.join(args.text)).encode('utf-8'))
        print()
    else:
        sys.stdout.buffer.write(latex_to_text(sys.stdin.read()).encode('utf-8'))
        print()


if __name__ == '__main__':
    main()
