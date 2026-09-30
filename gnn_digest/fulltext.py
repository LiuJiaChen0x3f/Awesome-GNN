"""Fetch bounded public full text for grounded paper summaries."""
import gzip
import io
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from urllib.parse import urlencode, urlparse
from html.parser import HTMLParser

from .models import clean, norm_title, arxiv_id
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
            return '\n'.join(page.extract_text() or '' for page in reader.pages), 'pdf'
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise VerificationError('Unsupported full-text content type')
        parser = Sections(); parser.feed(raw.decode('utf-8', errors='replace'))
        return ''.join(parser.parts), 'html'


def load_fulltext(p, timeout=45, max_characters=120000):
    if p.get('full_text') and p.get('fulltext_source', {}).get('scope') == 'full_text': return
    lookup_started=time.monotonic()
    if p.get('_allow_arxiv_lookup') and not p.get('arxiv_id') and (
            not p.get('pdf_url') or urlparse(p.get('pdf_url','')).hostname in ('dl.acm.org','openreview.net','ieeexplore.ieee.org')):
        try:
            match=find_arxiv_fulltext(p['title'],min(15,max(1,timeout/2)))
            if match:
                p.update(arxiv_id=match['arxiv_id'],pdf_url=match['pdf_url'],
                         fulltext_alternate_verification=match['verification'])
        except Exception:
            pass  # Try the independently verified publisher PDF below.
    timeout=max(1,timeout-(time.monotonic()-lookup_started))
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
            text = '\n'.join(clean(line) for line in text.splitlines() if clean(line))
            if len(text) < 500:
                raise VerificationError('Extracted full text is too short')
            if len(text) > max_characters:
                raise VerificationError(f'Extracted full text exceeds {max_characters} character model limit')
            # Require title words in the document as an additional mismatch guard.
            words = re.findall(r'[a-z]{4,}', p['title'].casefold())
            plain = clean(text).casefold()
            if words and sum(word in plain for word in words) < max(1, len(words)//2):
                raise VerificationError('Full-text title does not match the verified paper')
            p.update(full_text=text, fulltext_source={'url':url, 'format':kind,
                     'scope':'full_text', 'characters':len(text)})
            return
        except Exception as exc:
            detail = str(exc)[:160] if isinstance(exc, VerificationError) else type(exc).__name__
            errors.append(detail)
    raise VerificationError('Full text unavailable: ' + ', '.join(errors or ['no full-text URL']))


def find_arxiv_fulltext(title, timeout=15):
    """Resolve a known conference title, never discover papers via fixed terms."""
    from .http import request
    from .verification import verify_candidate
    query=urlencode({'search_query':'ti:"'+title.replace('"','')+'"','max_results':3})
    raw=request('https://export.arxiv.org/api/query?'+query,timeout=timeout,attempts=1)
    ns={'a':'http://www.w3.org/2005/Atom'}
    for entry in ET.fromstring(raw).findall('a:entry',ns):
        found=clean(entry.findtext('a:title','',ns))
        aid=arxiv_id(entry.findtext('a:id','',ns))
        if aid and norm_title(found)==norm_title(title):
            return verify_candidate({'title':title,'url':'https://arxiv.org/abs/'+aid},
                                    date(1991,1,1),date.today(),timeout=timeout)
    return None


def coerce_legacy_fulltext(p):
    """Adapt an older test/integration result without accepting old archives.

    Historical records explicitly carry ``scope=method_sections`` and are not
    converted.  A scope-less result is only used as a compatibility adapter
    for callers that patch the loader.
    """
    source = p.get('fulltext_source') or {}
    if (not p.get('full_text') and p.get('method_text') and
            source.get('scope') not in ('method_sections', 'full_text')):
        p['full_text'] = '\n'.join(x for x in (p.get('abstract', ''), p['method_text']) if x)
        p['fulltext_source'] = {**source, 'scope': 'full_text',
                                'characters': len(p['full_text'])}
    return p


# Compatibility name for callers written before summaries switched to full text.
# New code should use load_fulltext; this alias never invokes method-section parsing.
load_methods = load_fulltext
