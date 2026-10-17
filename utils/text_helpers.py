"""
Text utilities for message splitting and formatting in Telegram.
Converts AI Markdown into native Telegram HTML with blockquotes, bold, italic, and code.
Performs comprehensive LaTeX & math cleaning with clean Unicode typography.
"""
import re
import html
import logging
from typing import List, Optional
from aiogram.types import Message, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 3500

def clean_math_formatting(text: str) -> str:
    """
    Cleans raw unrendered LaTeX tags, converts math symbols to standard Unicode,
    cleans powers/indices, and structures equations into ChatGPT-standard typography.
    """
    if not text:
        return text

    # 1. Convert block math $$ ... $$ to Markdown blockquotes >
    def replace_block_math(match):
        inner = match.group(1).strip()
        lines = [line.strip() for line in inner.split('\n') if line.strip()]
        quoted = '\n'.join(f"> {l}" for l in lines)
        return f"\n{quoted}\n"

    text = re.sub(r'\$\$(.+?)\$\$', replace_block_math, text, flags=re.DOTALL)

    # 2. Convert common LaTeX symbols to clean Unicode
    replacements = [
        (r'\\cdot', '·'),
        (r'\\times', '×'),
        (r'\\div', '÷'),
        (r'\\pm', '±'),
        (r'\\mp', '∓'),
        (r'\\neq', '≠'),
        (r'\\leq', '≤'),
        (r'\\geq', '≥'),
        (r'\\approx', '≈'),
        (r'\\equiv', '≡'),
        (r'\\infty', '∞'),
        (r'\\rightarrow', '→'),
        (r'\\to\b', '→'),
        (r'\\Rightarrow', '⟹'),
        (r'\\implies\b', '⟹'),
        (r'\\partial', '∂'),
        (r'\\int', '∫'),
        (r'\\sum', '∑'),
        (r'\\prod', '∏'),
        (r'\\pi\b', 'π'),
        (r'\\theta\b', 'θ'),
        (r'\\alpha\b', 'α'),
        (r'\\beta\b', 'β'),
        (r'\\gamma\b', 'γ'),
        (r'\\lambda\b', 'λ'),
        (r'\\Delta\b', 'Δ'),
        (r'\\sigma\b', 'σ'),
        (r'\\mu\b', 'μ'),
        (r'\\omega\b', 'ω'),
        (r'\\sin\b', 'sin'),
        (r'\\cos\b', 'cos'),
        (r'\\tan\b', 'tan'),
        (r'\\cot\b', 'cot'),
        (r'\\arcsin\b', 'arcsin'),
        (r'\\arccos\b', 'arccos'),
        (r'\\arctan\b', 'arctan'),
        (r'\\ln\b', 'ln'),
        (r'\\log\b', 'log'),
        (r'\\sqrt\{([^}]+)\}', r'√(\1)'),
        (r'\\sqrt([a-zA-Z0-9])', r'√\1'),
        (r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1) / (\2)'),
        (r'\\text\{([^}]+)\}', r'\1'),
        (r'\\det\b', 'det'),
        (r'\\adj\b', 'adj'),
        (r'\\lim_\{([^}]+)\}', r'lim(\1)'),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)

    # 3. Clean powers (superscripts): ^2 -> ², ^3 -> ³, etc.
    sup_map = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
        '+': '⁺', '-': '⁻', 'n': 'ⁿ', 'x': 'ˣ', 'y': 'ʸ', 'i': 'ⁱ'
    }
    def replace_sup(match):
        val = match.group(1)
        if all(c in sup_map for c in val):
            return ''.join(sup_map[c] for c in val)
        return f'^({val})'

    text = re.sub(r'\^\{([0-9+\-nxyi]+)\}', replace_sup, text)
    text = re.sub(r'\^([0-9nxyi])', lambda m: sup_map.get(m.group(1), m.group(0)), text)

    # 4. Clean subscripts: _0 -> ₀, _1 -> ₁, etc.
    sub_map = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
        '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
        'i': 'ᵢ', 'j': 'ⱼ', 'k': 'ₖ', 'n': 'ₙ', 'm': 'ₘ'
    }
    text = re.sub(r'_\{([0-9ijknm])\}', lambda m: sub_map.get(m.group(1), m.group(0)), text)
    text = re.sub(r'_([0-9ijknm])', lambda m: sub_map.get(m.group(1), m.group(0)), text)

    # 5. Clean arrows & multipliers
    text = re.sub(r'(?<=\s)=>(?=\s)', '➜', text)
    text = re.sub(r'(?<=[a-zA-Z0-9\)])\s*\*\s*(?=[a-zA-Z0-9\(])', ' · ', text)

    # 6. LaTeX matrices into clean monospace visual boxes
    def clean_matrix(match):
        content = match.group(1).strip()
        rows = [r.strip() for r in content.split(r'\\') if r.strip()]
        formatted_rows = []
        for row in rows:
            cols = [c.strip() for c in row.split('&')]
            formatted_rows.append('  '.join(cols))
        inner = '\n'.join(f"[ {r} ]" for r in formatted_rows)
        return f"\n```\n{inner}\n```\n"

    text = re.sub(r'\\begin\{(?:b|p|v|B)matrix\}(.+?)\\end\{(?:b|p|v|B)matrix\}', clean_matrix, text, flags=re.DOTALL)

    # 7. Remove single $ around variables/formulas outside code blocks
    text = re.sub(r'(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)', r'\1', text)

    return text

def split_text_for_telegram(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Splits long Markdown text cleanly at paragraphs or section boundaries
    before converting each chunk to HTML.
    """
    if len(text) <= max_len:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_len:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            if len(para) > max_len:
                lines = para.split("\n")
                for line in lines:
                    if len(current_chunk) + len(line) + 1 <= max_len:
                        if current_chunk:
                            current_chunk += "\n" + line
                        else:
                            current_chunk = line
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                            current_chunk = ""
                        if len(line) > max_len:
                            for i in range(0, len(line), max_len):
                                chunks.append(line[i:i + max_len])
                        else:
                            current_chunk = line
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def markdown_to_telegram_html(text: str) -> str:
    """
    Converts AI Markdown formatting into rich, reliable Telegram HTML:
    - Blockquotes (lines starting with >) -> <blockquote>...</blockquote>
    - Code blocks (```...```) -> <pre><code>...</code></pre>
    - Inline code (`...`) -> <code>...</code>
    - Bold (**...** or __...__) -> <b>...</b>
    - Italic (*...* or _..._) -> <i>...</i>
    - Headers (### ...) -> <b>...</b>
    - Markdown links [text](url) -> <a href="url">text</a>
    """
    if not text:
        return text

    # 1. Protect multiline code blocks
    code_blocks = []
    def save_code_block(match):
        lang = match.group(1) or ''
        code = match.group(2)
        escaped_code = html.escape(code.strip('\n'))
        idx = len(code_blocks)
        placeholder = f"@@@CB{idx}@@@"
        if lang:
            code_blocks.append(f'<pre><code class="language-{lang}">{escaped_code}</code></pre>')
        else:
            code_blocks.append(f'<pre>{escaped_code}</pre>')
        return placeholder

    text = re.sub(r'```([a-zA-Z0-9_-]*)\n?(.*?)```', save_code_block, text, flags=re.DOTALL)

    # 2. Protect inline code
    inline_codes = []
    def save_inline_code(match):
        code = match.group(1)
        escaped = html.escape(code)
        idx = len(inline_codes)
        placeholder = f"@@@IN{idx}@@@"
        inline_codes.append(f'<code>{escaped}</code>')
        return placeholder

    text = re.sub(r'`([^`\n]+)`', save_inline_code, text)

    # 3. Process blockquotes (contiguous lines starting with >)
    lines = text.split('\n')
    new_lines = []
    in_quote = False
    quote_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('>'):
            q_content = re.sub(r'^>\s?', '', line)
            quote_lines.append(q_content)
            in_quote = True
        else:
            if in_quote:
                new_lines.append('@@@QSTART@@@' + '\n'.join(quote_lines) + '@@@QEND@@@')
                quote_lines = []
                in_quote = False
            new_lines.append(line)
    if in_quote:
        new_lines.append('@@@QSTART@@@' + '\n'.join(quote_lines) + '@@@QEND@@@')

    text = '\n'.join(new_lines)

    # 4. Escape remaining HTML in text (&, <, >)
    text = html.escape(text, quote=False)

    # 5. Convert markdown headers to bold: # Title, ## Title, ### Title
    text = re.sub(r'^(?:#{1,6})\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # 6. Convert markdown bold: **bold** or __bold__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # 7. Convert markdown italic: *italic* (not followed or preceded by *)
    text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<i>\1</i>', text)

    # 8. Convert links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2">\1</a>', text)

    # 9. Restore blockquotes as Telegram <blockquote>
    def format_quote(match):
        inner = match.group(1).strip()
        return f'<blockquote>{inner}</blockquote>'

    text = re.sub(r'@@@QSTART@@@(.*?)@@@QEND@@@', format_quote, text, flags=re.DOTALL)

    # 10. Restore inline code
    for i, code in enumerate(inline_codes):
        text = text.replace(f"@@@IN{i}@@@", code)

    # 11. Restore multiline code blocks
    for i, block in enumerate(code_blocks):
        text = text.replace(f"@@@CB{i}@@@", block)

    return text

async def send_formatted_telegram_response(
    target_message: Message,
    response_text: str,
    status_msg: Optional[Message] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> None:
    """
    Cleans math formatting, splits if necessary, converts to Telegram HTML,
    and sends with full fallbacks.
    """
    cleaned_text = clean_math_formatting(response_text)
    raw_chunks = split_text_for_telegram(cleaned_text)
    html_chunks = [markdown_to_telegram_html(c) for c in raw_chunks]

    if status_msg and len(html_chunks) == 1:
        try:
            await status_msg.edit_text(html_chunks[0], reply_markup=reply_markup, parse_mode="HTML")
            return
        except Exception as e_html:
            logger.debug(f"HTML edit failed, falling back to Markdown: {e_html}")
            try:
                await status_msg.edit_text(raw_chunks[0], reply_markup=reply_markup, parse_mode="Markdown")
                return
            except Exception as e_md:
                logger.debug(f"Markdown edit failed, falling back to plain: {e_md}")
                await status_msg.edit_text(raw_chunks[0], reply_markup=reply_markup)
                return

    if status_msg and len(html_chunks) > 1:
        try:
            await status_msg.delete()
        except Exception:
            pass

    for i, (raw_c, html_c) in enumerate(zip(raw_chunks, html_chunks)):
        kb = reply_markup if i == len(html_chunks) - 1 else None
        try:
            await target_message.answer(html_c, reply_markup=kb, parse_mode="HTML")
        except Exception as e_html:
            logger.debug(f"HTML answer failed, falling back to Markdown: {e_html}")
            try:
                await target_message.answer(raw_c, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await target_message.answer(raw_c, reply_markup=kb)
