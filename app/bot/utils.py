import re
import html
from typing import List
from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

def split_message(text: str, max_length: int = 3900) -> List[str]:
    """
    Splits long plain messages cleanly at newline or whitespace boundaries
    to respect Telegram's 4096 character limit.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = []
    current_len = 0

    lines = text.split("\n")
    for line in lines:
        if current_len + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_len = 0

            # If a single line is longer than max_length, split it hard
            while len(line) > max_length:
                chunks.append(line[:max_length])
                line = line[max_length:]

        current_chunk.append(line)
        current_len += len(line) + 1

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def split_html_message(text: str, max_length: int = 3900) -> List[str]:
    """
    Splits long HTML messages cleanly, ensuring open tags like <b>, <i>, <code>, <pre>, <blockquote>
    are closed at the end of a chunk and reopened at the beginning of the next chunk.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_len = 0
    open_tags = []

    TAG_REGEX = re.compile(r'<\/?([a-zA-Z0-9_-]+)(?:\s+[^>]*)?>')

    for line in lines:
        if current_len + len(line) + 1 > max_length:
            if current_chunk:
                chunk_str = "\n".join(current_chunk)
                # Close any open tags in reverse order
                for t in reversed(open_tags):
                    chunk_str += f"</{t}>"
                chunks.append(chunk_str)

                # Next chunk starts with reopening tags
                current_chunk = []
                current_len = 0
                for t in open_tags:
                    current_chunk.append(f"<{t}>")
                    current_len += len(t) + 2

        # Track tags in line
        for match in TAG_REGEX.finditer(line):
            tag_text = match.group(0)
            tag_name = match.group(1).lower()
            if tag_text.startswith("</"):
                if open_tags and open_tags[-1] == tag_name:
                    open_tags.pop()
                elif tag_name in open_tags:
                    open_tags.remove(tag_name)
            elif not tag_text.endswith("/>"):
                open_tags.append(tag_name)

        current_chunk.append(line)
        current_len += len(line) + 1

    if current_chunk:
        chunk_str = "\n".join(current_chunk)
        for t in reversed(open_tags):
            chunk_str += f"</{t}>"
        chunks.append(chunk_str)

    return chunks


def clean_math_to_unicode(expr: str) -> str:
    """
    Converts LaTeX math expressions into human-readable Unicode text
    for clean and legible display in Telegram without raw LaTeX code.
    Handles matrices, piecewise functions, calculus, roots, and greek letters.
    """
    s = expr.strip()
    s = re.sub(r'^\$+|\$+$', '', s).strip()
    s = re.sub(r'\\(?:text|mathrm|mathbf|mathit|textbf)\{([^{}]+)\}', r'\1', s)

    # 1. Matrices (pmatrix, bmatrix, matrix, vmatrix)
    def format_matrix(m):
        env_type = m.group(1)
        body = m.group(2).strip()
        rows = [r.strip() for r in body.split(r'\\') if r.strip()]
        matrix_rows = []
        for r in rows:
            cols = [c.strip() for c in r.split('&')]
            matrix_rows.append('  '.join(cols))

        bracket_l, bracket_r = ('[', ']') if 'b' in env_type else (('(', ')') if 'p' in env_type else (('|', '|') if 'v' in env_type else ('[', ']')))
        max_len = max(len(r) for r in matrix_rows) if matrix_rows else 0
        res = []
        for idx, r in enumerate(matrix_rows):
            if len(matrix_rows) == 1:
                res.append(f'{bracket_l} {r} {bracket_r}')
            elif idx == 0:
                res.append(f'┌ {r:<{max_len}} ┐')
            elif idx == len(matrix_rows) - 1:
                res.append(f'└ {r:<{max_len}} ┘')
            else:
                res.append(f'│ {r:<{max_len}} │')
        return '\n' + '\n'.join(res) + '\n'

    s = re.sub(r'\\begin\{(matrix|pmatrix|bmatrix|vmatrix)\}(.*?)\\end\{\1\}', format_matrix, s, flags=re.DOTALL)

    # 2. Piecewise functions / cases
    def format_cases(m):
        body = m.group(1).strip()
        rows = [r.strip().replace('&', '  ') for r in body.split(r'\\') if r.strip()]
        return '{\n' + '\n'.join('  ' + r for r in rows) + '\n'
    s = re.sub(r'\\begin\{cases\}(.*?)\\end\{cases\}', format_cases, s, flags=re.DOTALL)

    # 3. Aligned equations
    s = re.sub(r'\\begin\{aligned?\*?\}(.*?)\\end\{aligned?\*?\}', r'\1', s, flags=re.DOTALL)
    s = s.replace('&', '')

    # 4. Partial derivative shortcuts
    s = re.sub(r'\\frac\{\\partial\^2\s*([a-zA-Z])\}\{\\partial\s*([a-zA-Z])\s*\\partial\s*([a-zA-Z])\}', r'∂²\1/∂\2∂\3', s)
    s = re.sub(r'\\frac\{\\partial\^2\s*([a-zA-Z])\}\{\\partial\s*([a-zA-Z])\^2\}', r'∂²\1/∂\2²', s)
    s = re.sub(r'\\frac\{\\partial\s*([a-zA-Z])\}\{\\partial\s*([a-zA-Z])\}', r'∂\1/∂\2', s)
    s = re.sub(r'\\frac\{\\partial\}\{\\partial\s*([a-zA-Z])\}', r'∂/∂\1', s)

    # 5. Ordinary derivatives shortcuts
    s = re.sub(r'\\frac\{d\^2\s*([a-zA-Z])\}\{d\s*([a-zA-Z])\^2\}', r'd²\1/d\2²', s)
    s = re.sub(r'\\frac\{d\s*([a-zA-Z])\}\{d\s*([a-zA-Z])\}', r'd\1/d\2', s)
    s = re.sub(r'\\frac\{d\}\{d\s*([a-zA-Z])\}', r'd/d\1', s)

    # 6. Fractions (handle nested up to 3 levels)
    for _ in range(3):
        if r'\frac' not in s:
            break
        s = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'(\1 / \2)', s)

    # 7. Roots
    s = re.sub(r'\\sqrt\[3\]\{([^{}]+)\}', r'∛(\1)', s)
    s = re.sub(r'\\sqrt\[4\]\{([^{}]+)\}', r'∜(\1)', s)
    s = re.sub(r'\\sqrt\[([^\]]+)\]\{([^{}]+)\}', r'ⁿ√(\1)', s)
    s = re.sub(r'\\sqrt\{([^{}]+)\}', r'√(\1)', s)

    # 8. Common math symbols & operators
    replacements = [
        (r'\\partial\^2', '∂²'),
        (r'\\partial', '∂'),
        (r'\\nabla', '∇'),
        (r'\\int_\{([^{}]+)\}\^\{([^{}]+)\}', r'∫[\1→\2]'),
        (r'\\iint_\{([^{}]+)\}', r'∬[\1]'),
        (r'\\int', '∫'),
        (r'\\iint', '∬'),
        (r'\\iiint', '∭'),
        (r'\\oint', '∮'),
        (r'\\sum_\{([^{}]+)\}\^\{([^{}]+)\}', r'∑[\1→\2]'),
        (r'\\sum_\{([^{}]+)\}', r'∑[\1]'),
        (r'\\sum', '∑'),
        (r'\\prod_\{([^{}]+)\}\^\{([^{}]+)\}', r'∏[\1→\2]'),
        (r'\\prod', '∏'),
        (r'\\lim_\{([^{}]+)\}', r'lim(\1)'),
        (r'\\lim', 'lim'),
        (r'\\pm', '±'),
        (r'\\mp', '∓'),
        (r'\\times', '×'),
        (r'\\cdot', '·'),
        (r'\\div', '÷'),
        (r'\\neq|\\ne', '≠'),
        (r'\\leq|\\le', '≤'),
        (r'\\geq|\\ge', '≥'),
        (r'\\approx', '≈'),
        (r'\\equiv', '≡'),
        (r'\\propto', '∝'),
        (r'\\infty', '∞'),
        (r'\\to|\\rightarrow', '→'),
        (r'\\leftarrow', '←'),
        (r'\\leftrightarrow', '↔'),
        (r'\\Rightarrow|\\implies', '⇒'),
        (r'\\Leftarrow', '⇐'),
        (r'\\Leftrightarrow|\\iff', '⇔'),
        (r'\\in', '∈'),
        (r'\\notin', '∉'),
        (r'\\subset', '⊂'),
        (r'\\subseteq', '⊆'),
        (r'\\cup', '∪'),
        (r'\\cap', '∩'),
        (r'\\emptyset', '∅'),
        (r'\\forall', '∀'),
        (r'\\exists', '∃'),
        (r'\\alpha', 'α'),
        (r'\\beta', 'β'),
        (r'\\gamma', 'γ'),
        (r'\\delta', 'δ'),
        (r'\\Delta', 'Δ'),
        (r'\\epsilon|\\varepsilon', 'ε'),
        (r'\\zeta', 'ζ'),
        (r'\\eta', 'η'),
        (r'\\theta', 'θ'),
        (r'\\Theta', 'Θ'),
        (r'\\iota', 'ι'),
        (r'\\kappa', 'κ'),
        (r'\\lambda', 'λ'),
        (r'\\Lambda', 'Λ'),
        (r'\\mu', 'μ'),
        (r'\\nu', 'ν'),
        (r'\\xi', 'ξ'),
        (r'\\pi', 'π'),
        (r'\\Pi', 'Π'),
        (r'\\rho', 'ρ'),
        (r'\\sigma', 'σ'),
        (r'\\Sigma', 'Σ'),
        (r'\\tau', 'τ'),
        (r'\\phi|\\varphi', 'φ'),
        (r'\\Phi', 'Φ'),
        (r'\\chi', 'χ'),
        (r'\\psi', 'ψ'),
        (r'\\omega', 'ω'),
        (r'\\Omega', 'Ω'),
        (r'\\ln', 'ln'),
        (r'\\log_\{([^{}]+)\}', r'log_{\1}'),
        (r'\\log', 'log'),
        (r'\\sin', 'sin'),
        (r'\\cos', 'cos'),
        (r'\\tan', 'tan'),
        (r'\\cot', 'cot'),
        (r'\\arcsin', 'arcsin'),
        (r'\\arccos', 'arccos'),
        (r'\\arctan', 'arctan'),
        (r'\\sinh', 'sinh'),
        (r'\\cosh', 'cosh'),
        (r'\\tanh', 'tanh'),
        (r'\\exp', 'exp'),
        (r'\\det', 'det'),
        (r'\\left\(', '('),
        (r'\\right\)', ')'),
        (r'\\left\[', '['),
        (r'\\right\]', ']'),
        (r'\\left\\\{', '{'),
        (r'\\right\\\}', '}'),
        (r'\\left\|', '‖'),
        (r'\\right\|', '‖'),
        (r'\\left\|?', '|'),
        (r'\\right\|?', '|'),
        (r'\\left\.', ''),
        (r'\\right\.', ''),
        (r'\\[,;!]|\\quad|\\qquad', ' '),
        (r'\\\\', '\n'),
    ]
    for pattern, rep in replacements:
        s = re.sub(pattern, rep, s)

    # 9. Superscripts mapping
    sup_map = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
        '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
        'n': 'ⁿ', 'i': 'ⁱ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ',
        'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ',
        'k': 'ᵏ', 'm': 'ᵐ', 'p': 'ᵖ', 't': 'ᵗ'
    }
    # 10. Subscripts mapping
    sub_map = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
        '5': '₅', '6': '₆', '7': '₇', '8': '⁸', '9': '₉',
        '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
        'a': 'ₐ', 'e': 'ₑ', 'i': 'ᵢ', 'j': 'ⱼ', 'k': 'ₖ',
        'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ', 'p': 'ₚ', 'r': 'ᵣ',
        's': 'ₛ', 't': 'ₜ', 'u': 'ᵤ', 'v': 'ᵥ', 'x': 'ₓ'
    }

    def replace_sup(m):
        val = m.group(1)
        if all(c in sup_map for c in val):
            return ''.join(sup_map[c] for c in val)
        return f'^({val})'

    s = re.sub(r'\^\{([^{}]+)\}', replace_sup, s)
    s = re.sub(r'\^([0-9nixyzabcdekmpt\+\-])', lambda m: sup_map.get(m.group(1), f'^{m.group(1)}'), s)

    def replace_sub(m):
        val = m.group(1)
        if all(c in sub_map for c in val):
            return ''.join(sub_map[c] for c in val)
        return f'_({val})'

    s = re.sub(r'_\{([^{}]+)\}', replace_sub, s)
    s = re.sub(r'_([0-9aeijkmnoprstuvxy\+\-])', lambda m: sub_map.get(m.group(1), f'_{m.group(1)}'), s)

    # 11. Clean leftover backslashes and braces
    s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)
    s = s.replace('{', '').replace('}', '')

    # 12. Normalize multiple spaces on each line
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in s.split('\n')]
    return '\n'.join(lines).strip()


def convert_markdown_tables(text: str) -> str:
    """
    Transforms markdown pipe tables into clean, structured cards with bold keys
    so they look great in Telegram instead of wrapping awkwardly.
    """
    lines = text.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'^\s*\|.+?\|\s*$', line):
            if i + 1 < len(lines) and re.match(r'^\s*\|?\s*[-:]+[-| :]*\|\s*$', lines[i + 1]):
                headers = [c.strip() for c in line.strip().strip('|').split('|')]
                i += 2
                table_output = []
                while i < len(lines) and re.match(r'^\s*\|.+?\|\s*$', lines[i]):
                    row_cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                    if not any(row_cells):
                        i += 1
                        continue

                    # Case 1: 2-column key-value table
                    if len(headers) == 2 and len(row_cells) >= 2:
                        k, v = row_cells[0], row_cells[1]
                        table_output.append(f'▫️ **{k}:** {v}')
                    # Case 2: Multi-column table
                    elif len(headers) >= 3 and len(row_cells) >= len(headers):
                        first = row_cells[0]
                        if re.match(r'^[0-9۰-۹IVX]+[\.\)]?$', first):
                            title = row_cells[1]
                            details = [f'_{h}:_ {v}' for h, v in zip(headers[2:], row_cells[2:]) if v]
                            det_str = f" ({', '.join(details)})" if details else ''
                            table_output.append(f'▫️ **{first}. {title}**{det_str}')
                        else:
                            details = [f'_{h}:_ {v}' for h, v in zip(headers[1:], row_cells[1:]) if v]
                            table_output.append(f"▫️ **{first}** — {' • '.join(details)}")
                    else:
                        pairs = [f'**{h}:** {v}' for h, v in zip(headers, row_cells) if v]
                        table_output.append(f"▫️ {' | '.join(pairs)}")
                    i += 1

                new_lines.append('\n'.join(table_output))
                continue
        new_lines.append(line)
        i += 1
    return '\n'.join(new_lines)


def markdown_to_telegram_html(text: str) -> str:
    """
    Robust Markdown to Telegram-safe HTML converter.
    Properly handles bold, italic, code blocks, inline code, links, math, tables, and headers.
    Guarantees valid, aesthetic rendering in Telegram.
    """
    if not text:
        return ""

    # 1. Convert markdown pipe tables to clean cards
    text = convert_markdown_tables(text)

    # 2. Protect code blocks
    code_blocks = []
    def save_code_block(m):
        lang = (m.group(1) or "").strip()
        code = m.group(2)
        code_blocks.append((lang, code))
        return f"QQQCODEBLOCK{len(code_blocks)-1}QQQ"

    text = re.sub(r"```([a-zA-Z0-9_-]*)\n?(.*?)```", save_code_block, text, flags=re.DOTALL)

    # 3. Protect inline code
    inline_codes = []
    def save_inline_code(m):
        inline_codes.append(m.group(1))
        return f"QQQINLINECODE{len(inline_codes)-1}QQQ"

    text = re.sub(r"`([^`\n]+)`", save_inline_code, text)

    # 4. Display Math blocks ($$...$$) -> standalone preformatted blocks
    display_math_blocks = []
    def save_display_math(m):
        raw_expr = m.group(1).strip()
        cleaned_expr = clean_math_to_unicode(raw_expr)
        display_math_blocks.append(cleaned_expr)
        return f"\n\nQQQDISPLAYMATH{len(display_math_blocks)-1}QQQ\n\n"

    text = re.sub(r"\$\$(.+?)\$\$", save_display_math, text, flags=re.DOTALL)

    # 5. Inline Math blocks ($...$) -> inline code tags
    inline_math_blocks = []
    def save_inline_math(m):
        raw_expr = m.group(1).strip()
        cleaned_expr = clean_math_to_unicode(raw_expr)
        inline_math_blocks.append(cleaned_expr)
        return f"QQQINLINEMATH{len(inline_math_blocks)-1}QQQ"

    text = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", save_inline_math, text)

    # 5. Protect valid pre-existing Telegram HTML tags
    VALID_HTML_TAG = re.compile(
        r'<\/?(?:b|strong|i|em|u|ins|s|strike|del|code|pre|blockquote|tg-spoiler|tg-emoji|a)(?:\s+[^>]*)?>',
        re.IGNORECASE
    )
    html_tags = []
    def save_html_tag(m):
        html_tags.append(m.group(0))
        return f"QQQHTMLTAG{len(html_tags)-1}QQQ"

    text = VALID_HTML_TAG.sub(save_html_tag, text)

    # 6. Escape HTML for raw text outside tags/code/math
    text = html.escape(text)

    # 7. Convert Markdown Headers (# through ######)
    def replace_header(m):
        level = len(m.group(1))
        content = m.group(2).strip()
        has_emoji = bool(re.match(r'^[^\w\s\d]', content))
        if level == 1:
            icon = "" if has_emoji else "📌 "
            return f"\n\n{icon}<b>{content}</b>\n"
        elif level == 2:
            icon = "" if has_emoji else "📋 "
            return f"\n\n{icon}<b>{content}</b>\n"
        elif level == 3:
            icon = "" if has_emoji else "🔹 "
            return f"\n\n{icon}<b>{content}</b>\n"
        else:
            icon = "" if has_emoji else "▫️ "
            return f"\n\n{icon}<b>{content}</b>\n"

    text = re.sub(r"^(#{1,6})\s+(.+)$", replace_header, text, flags=re.MULTILINE)

    # 8. Convert horizontal rules (---, ***, ___)
    text = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", "\n───────────────\n", text, flags=re.MULTILINE)

    # 9. Convert bullet lists with smart indentation
    def replace_bullet(m):
        spaces = len(m.group(1).replace("\t", "    "))
        content = m.group(2).strip()
        if spaces >= 6:
            return f"      ▪️ {content}"
        elif spaces >= 2:
            return f"    ▫️ {content}"
        else:
            return f"• {content}"

    text = re.sub(r"^([ \t]*)[\*\+\-]\s+(.+)$", replace_bullet, text, flags=re.MULTILINE)

    # 10. Convert numbered lists
    def replace_numbered(m):
        spaces = len(m.group(1).replace("\t", "    "))
        num = m.group(2)
        content = m.group(3).strip()
        prefix = "    " if spaces >= 4 else ("  " if spaces >= 2 else "")
        return f"{prefix}<b>{num}.</b> {content}"

    text = re.sub(r"^([ \t]*)(\d+)[\.\)]\s+(.+)$", replace_numbered, text, flags=re.MULTILINE)

    # 11. Convert blockquotes (> ...)
    text = re.sub(r"^>\s*(.+)$", r"<blockquote>\1</blockquote>", text, flags=re.MULTILINE)

    # 12. Convert Bold, Italic, Strikethrough
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)\*([^\*\n]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # 13. Convert Markdown Links: [text](url)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', text)

    # 14. Restore display math as preformatted code blocks
    for i, mcontent in enumerate(display_math_blocks):
        escaped_math = html.escape(mcontent)
        text = text.replace(f"QQQDISPLAYMATH{i}QQQ", f'<pre><code class="language-math">{escaped_math}</code></pre>')

    # 15. Restore inline math as clean code pills
    for i, mcontent in enumerate(inline_math_blocks):
        escaped_math = html.escape(mcontent)
        text = text.replace(f"QQQINLINEMATH{i}QQQ", f"<code>{escaped_math}</code>")

    # 15. Restore inline code
    for i, icode in enumerate(inline_codes):
        escaped_icode = html.escape(icode)
        text = text.replace(f"QQQINLINECODE{i}QQQ", f"<code>{escaped_icode}</code>")

    # 16. Restore code blocks
    for i, (lang, cblock) in enumerate(code_blocks):
        escaped_cblock = html.escape(cblock.strip("\n"))
        if lang:
            replacement = f'<pre><code class="language-{html.escape(lang)}">{escaped_cblock}</code></pre>'
        else:
            replacement = f"<pre><code>{escaped_cblock}</code></pre>"
        text = text.replace(f"QQQCODEBLOCK{i}QQQ", replacement)

    # 17. Restore pre-existing protected HTML tags
    for i, tag_str in enumerate(html_tags):
        text = text.replace(f"QQQHTMLTAG{i}QQQ", tag_str)

    # 18. Clean up redundant empty lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_html_tags(text: str) -> str:
    """Removes HTML tags for safe fallback plain text display."""
    return re.sub(r'<[^>]+>', '', text)


async def safe_reply(
    message: Message,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML"
) -> List[Message]:
    """
    Sends message safely. If Telegram rejects formatting,
    automatically falls back to plain text so the user never misses an answer.
    """
    is_html = parse_mode and parse_mode.upper() == "HTML"
    chunks = split_html_message(text) if is_html else split_message(text)
    sent_messages = []

    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None

        try:
            msg = await message.answer(chunk, reply_markup=markup, parse_mode=parse_mode)
            sent_messages.append(msg)
        except TelegramBadRequest as e:
            try:
                fallback_chunk = strip_html_tags(chunk) if is_html else chunk
                msg = await message.answer(fallback_chunk, reply_markup=markup, parse_mode=None)
                sent_messages.append(msg)
            except Exception as e2:
                print(f"[SafeReply] Failed to send fallback message: {e2}")
        except Exception as e:
            print(f"[SafeReply] Unexpected error: {e}")

    return sent_messages


async def safe_edit_or_reply(
    placeholder_msg: Message,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML"
) -> List[Message]:
    """
    Edits placeholder_msg with the first chunk, and sends any additional chunks as replies.
    Falls back gracefully to plain text if formatting errors occur.
    """
    is_html = parse_mode and parse_mode.upper() == "HTML"
    chunks = split_html_message(text) if is_html else split_message(text)
    sent_messages = []

    first_chunk = chunks[0]
    first_markup = reply_markup if len(chunks) == 1 else None

    edited = False
    try:
        msg = await placeholder_msg.edit_text(first_chunk, reply_markup=first_markup, parse_mode=parse_mode)
        sent_messages.append(msg)
        edited = True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            edited = True
        else:
            try:
                fallback_chunk = strip_html_tags(first_chunk) if is_html else first_chunk
                msg = await placeholder_msg.edit_text(fallback_chunk, reply_markup=first_markup, parse_mode=None)
                sent_messages.append(msg)
                edited = True
            except TelegramBadRequest as e2:
                if "message is not modified" in str(e2).lower():
                    edited = True
            except Exception:
                pass
    except Exception:
        pass

    if not edited:
        try:
            fallback_chunk = strip_html_tags(first_chunk) if is_html else first_chunk
            msg = await placeholder_msg.answer(fallback_chunk, reply_markup=first_markup, parse_mode=None)
            sent_messages.append(msg)
        except Exception:
            pass

    # Send subsequent chunks if any
    for i in range(1, len(chunks)):
        chunk = chunks[i]
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            msg = await placeholder_msg.answer(chunk, reply_markup=markup, parse_mode=parse_mode)
            sent_messages.append(msg)
        except TelegramBadRequest:
            try:
                fallback_chunk = strip_html_tags(chunk) if is_html else chunk
                msg = await placeholder_msg.answer(fallback_chunk, reply_markup=markup, parse_mode=None)
                sent_messages.append(msg)
            except Exception:
                pass
        except Exception:
            pass

    return sent_messages


def format_thinking_block(thinking_text: str, title: str = "فرآیند تحلیل و تفکر عمیق") -> str:
    """
    Format reasoning process cleanly for Telegram as a native expandable blockquote.
    Displays the thinking process inside a clean Quote card at the top,
    with the main response seamlessly displayed right below it in the same message.
    """
    if not thinking_text or not thinking_text.strip():
        return ""
    clean = thinking_text.strip()
    
    # Cap excessive thinking length so it fits comfortably within Telegram's single-message limit
    if len(clean) > 2200:
        clean = clean[:2200].rsplit(" ", 1)[0] + "\n... (ادامه تحلیل در مدل محفوظ است)"

    escaped_title = html.escape(title)
    escaped_thinking = html.escape(clean)
    return f"<blockquote expandable><b>💭 {escaped_title}:</b>\n{escaped_thinking}</blockquote>\n\n"


def deduplicate_text(text: str) -> str:
    """
    Detects and eliminates accidental repetition where the model
    or streaming pipeline repeats the entire response or large blocks.
    """
    if not text:
        return text
    clean = text.strip()
    n = len(clean)
    if n < 20:
        return clean

    # 1. Exact half duplication: A + A (e.g. p1 == p2)
    if n % 2 == 0:
        half = n // 2
        if clean[:half] == clean[half:]:
            return clean[:half].strip()

    # 2. Separated duplication: A + separator + A
    for sep in ["\n\n", "\n", " "]:
        if sep in clean:
            parts = clean.split(sep)
            if len(parts) == 2 and parts[0].strip() == parts[1].strip():
                return parts[0].strip()

    # 3. Fuzzy midpoint split (allowing slight whitespace offset around center)
    for offset in range(-6, 7):
        mid = (n // 2) + offset
        if 15 < mid < n - 15:
            left = clean[:mid].strip()
            right = clean[mid:].strip()
            if left and left == right:
                return left

    # 4. Long repeating suffix: if the text ends with an exact duplicate of its first half
    for block_len in range(n // 2, 40, -1):
        block = clean[:block_len].strip()
        rest = clean[block_len:].strip()
        if block and rest == block:
            return block

    return clean


def detect_aspect_ratio(width: int, height: int) -> str:
    """
    Detects the closest standard aspect ratio from image or video dimensions.
    Supported ratios:
      - 1:1  (Square)
      - 16:9 (Widescreen landscape)
      - 9:16 (Story / Reel portrait)
      - 4:3  (Standard landscape)
      - 3:4  (Standard portrait)
      - 3:2  (Classic photo landscape)
      - 2:3  (Classic photo portrait)
      - 21:9 (Ultrawide cinematic)
    """
    if not width or not height or width <= 0 or height <= 0:
        return "1:1"

    ratio_val = float(width) / float(height)

    target_ratios = [
        ("1:1", 1.0),
        ("16:9", 16.0 / 9.0),   # ~1.778
        ("9:16", 9.0 / 16.0),   # ~0.5625
        ("4:3", 4.0 / 3.0),     # ~1.333
        ("3:4", 3.0 / 4.0),     # ~0.75
        ("3:2", 3.0 / 2.0),     # ~1.5
        ("2:3", 2.0 / 3.0),     # ~0.667
        ("21:9", 21.0 / 9.0),   # ~2.333
    ]

    closest_ratio = min(target_ratios, key=lambda r: abs(ratio_val - r[1]))[0]
    return closest_ratio

