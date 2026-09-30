"""Validate the visible length and supported emphasis of method summaries."""
import re
from .evidence import EvidenceError

BOLD = re.compile(r'\*\*([^*\n]+)\*\*')


def method_visible_text(method):
    return BOLD.sub(lambda m: m.group(1), method)


def method_length(method):
    return len(re.sub(r'\s+', '', method_visible_text(method)))


def validate_method(method):
    highlights = BOLD.findall(method)
    plain = method_visible_text(method)
    if '*' in plain or re.search(r'[<>`]|!?\[[^\]]*\]\(', plain):
        raise EvidenceError('method_markdown', 'method', 'use plain Chinese text and paired **method name** emphasis only; no HTML, links or code')
    if not 1 <= len(highlights) <= 4 or any(not s.strip() or len(s) > 60 for s in highlights):
        raise EvidenceError('method_highlights', 'method', 'bold 1-4 short names of core methods/modules with **name**; do not bold entire sentences')
    length = method_length(method)
    if not 151 <= length <= 200 or not re.search(r'[\u4e00-\u9fff]', plain):
        raise EvidenceError('method_length', 'method',
                            f'expected 151-200 visible Chinese-summary characters, got {length}; Markdown markers and whitespace do not count')
    return method
