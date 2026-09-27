"""Fetch bounded public full text and retain method sections, never abstract fallback."""
import gzip
import io
import re
import time
import urllib.request
from html.parser import HTMLParser

from .models import clean
from .verification import CheckedRedirect, VerificationError, safe_scholarly_url


class Sections(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.heading, self.ignored = [], False, 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav'): self.ignored += 1
        if tag in ('h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n## '); self.heading = True
        elif tag in ('p', 'div', 'section', 'li'): self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav'): self.ignored = max(0, self.ignored - 1)
        if tag in ('h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n'); self.heading = False

    def handle_data(self, value):
        if not self.ignored: self.parts.append(value)


def method_sections(text):
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    heading = re.compile(r'^(?:##\s*(?:\d+(?:\.\d+)*\s*[.：:]?\s*)?|\d+(?:\.\d+)*\s*[.：:]?\s*)(?:problem formulation and |proposed\s+)?(?:method(?:ology|s)?|approach|framework|model architecture|our model)\b', re.I)
    named_heading = re.compile(r'^(?:##\s*)?\d+(?:\.\d+)*\s+[\w -]{0,100}\b(?:model|framework|architecture|algorithm|training)\b', re.I)
    start = next((i for i, line in enumerate(lines) if len(line) < 160 and
                  (heading.match(line) or named_heading.match(line)) and
                  not re.search(r'\b(background|related work|experiments?|introduction)\b', line, re.I)), None)
    if start is None:
        raise VerificationError('No identifiable method section in full text')
    end = next((i for i in range(start + 1, len(lines)) if len(lines[i]) < 100 and
                re.match(r'^(?:##\s*)?(?:\d+(?:\.\d+)*\s*[.：:]?\s*)?(?:experiments?|experimental (?:results|evaluation|setup)|results|conclusions?|references|acknowledg)', lines[i], re.I)), len(lines))
    result = '\n'.join(lines[start:end])[:24000]
    if len(result) < 500:
        raise VerificationError('Method section too short for grounded summary')
    return result


def read_document(url, timeout):
    safe_scholarly_url(url)
    req = urllib.request.Request(url, headers={'User-Agent': 'Awesome-GNN/0.3 full-text research'})
    with urllib.request.build_opener(CheckedRedirect).open(req, timeout=timeout) as response:
        safe_scholarly_url(response.url)
        raw = response.read(24_000_001)
        if len(raw) > 24_000_000: raise VerificationError('Full text exceeds 24 MB limit')
        if response.headers.get('Content-Encoding') == 'gzip': raw = gzip.decompress(raw)
        if raw.startswith(b'%PDF-'):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            if len(reader.pages) > 100: raise VerificationError('PDF exceeds 100 page limit')
            return '\n'.join(page.extract_text() or '' for page in reader.pages[:40]), 'pdf'
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise VerificationError('Unsupported full-text content type')
        parser = Sections(); parser.feed(raw.decode('utf-8', errors='replace'))
        return ''.join(parser.parts), 'html'


def load_methods(p, timeout=45):
    if p.get('method_text') and p.get('fulltext_source'): return
    urls = []
    if p.get('arxiv_id'):
        urls.append('https://arxiv.org/html/' + p['arxiv_id'])
    if p.get('pdf_url'): urls.append(p['pdf_url'])
    if p.get('arxiv_id'): urls.append('https://arxiv.org/pdf/' + p['arxiv_id'])
    errors, deadline = [], time.monotonic() + timeout
    for url in dict.fromkeys(urls):
        if time.monotonic() >= deadline: break
        try:
            text, kind = read_document(url, min(20, max(1, deadline-time.monotonic())))
            methods = method_sections(text)
            # Require title words in the document as an additional mismatch guard.
            words = re.findall(r'[a-z]{4,}', p['title'].casefold())
            plain = clean(text).casefold()
            if words and sum(word in plain for word in words) < max(1, len(words)//2):
                raise VerificationError('Full-text title does not match the verified paper')
            p.update(method_text=methods, fulltext_source={'url':url, 'format':kind,
                     'scope':'method_sections', 'characters':len(methods)})
            return
        except Exception as exc:
            errors.append(type(exc).__name__)
    raise VerificationError('Method full text unavailable: ' + ', '.join(errors or ['no full-text URL']))
