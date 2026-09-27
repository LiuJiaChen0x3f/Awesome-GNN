"""Read public scholarly landing pages; model guesses never become metadata."""
import re
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .models import arxiv_id, clean, norm_title, paper

TOPICS = ('GNN', 'SSL', 'CL', 'OOD', 'TAG', 'GSL', 'HGT', 'TGN', 'KG', 'KGE', 'HGNN')
# Explicit project scope, not a claim to cover every CCF-A conference.
VENUES = {
    'NeurIPS': ('neural information processing systems', 'neurips', 'nips'),
    'ICML': ('international conference on machine learning', 'icml'),
    'KDD': ('knowledge discovery and data mining', 'kdd'),
    'AAAI': ('aaai conference on artificial intelligence', 'aaai'),
    'IJCAI': ('international joint conference on artificial intelligence', 'ijcai'),
    'ACL': ('annual meeting of the association for computational linguistics', 'acl'),
    'CVPR': ('computer vision and pattern recognition', 'cvpr'),
    'ICCV': ('international conference on computer vision', 'iccv'),
    'SIGMOD': ('management of data', 'sigmod'),
    'VLDB': ('very large data bases', 'vldb'),
    'SIGIR': ('research and development in information retrieval', 'sigir'),
    'WWW': ('the web conference', 'international world wide web conference', 'www'),
    'ICDE': ('international conference on data engineering', 'icde'),
    'EMNLP': ('empirical methods in natural language processing', 'emnlp'),
}
DOMAINS = ('arxiv.org', 'aclanthology.org', 'proceedings.mlr.press', 'proceedings.neurips.cc',
           'papers.nips.cc', 'openaccess.thecvf.com', 'dl.acm.org', 'ieeexplore.ieee.org',
           'ojs.aaai.org', 'ijcai.org', 'vldb.org', 'proceedings.com')
DIRECTORY_SOURCES = {
    'KDD': ('https://kdd2026.kdd.org/papers/',),
    'WWW': ('https://www2026.thewebconf.org/',),
    'SIGIR': ('https://sigir2025.dei.unipd.it/proceedings.html',),
    'SIGMOD': ('https://2025.sigmod.org/sigmod_papers.shtml', 'https://2026.sigmod.org/sigmod_papers.shtml'),
    'VLDB': ('https://www.vldb.org/pvldb/volumes/18/', 'https://www.vldb.org/pvldb/volumes/19/'),
    'ICDE': (),
    'ACM MM': ('https://acmmm2025.org/accepted-regular-papers/',),
}


class VerificationError(ValueError):
    pass


def safe_scholarly_url(value):
    if not isinstance(value, str) or len(value) > 2000:
        raise VerificationError('Invalid source URL')
    u = urlparse(value)
    host = (u.hostname or '').lower()
    if u.scheme != 'https' or u.username or u.password or u.port not in (None, 443):
        raise VerificationError('Source must be a public HTTPS scholarly URL')
    if not any(host == d or host.endswith('.' + d) for d in DOMAINS):
        raise VerificationError('Source domain is not an enabled primary source')
    return value


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_scholarly_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_page(url, timeout=25):
    safe_scholarly_url(url)
    req = urllib.request.Request(url, headers={'User-Agent': 'Awesome-GNN/0.2 scholarly metadata verification'})
    with urllib.request.build_opener(CheckedRedirect).open(req, timeout=timeout) as response:
        safe_scholarly_url(response.url)
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise VerificationError('Need a paper landing page, not a PDF or binary file')
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise VerificationError('Source page too large')
        return raw.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.text, self.abstract_parts = {}, [], []
        self.depth, self.abstract_depth, self.ignore_depth = 0, None, None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            key = (attrs.get('name') or attrs.get('property') or '').lower()
            self.meta.setdefault(key, []).append(attrs.get('content', ''))
        if tag not in ('meta', 'link', 'br', 'hr', 'img', 'input', 'wbr', 'source', 'area', 'base', 'embed', 'param'):
            self.depth += 1
            if tag in ('script', 'style') and self.ignore_depth is None:
                self.ignore_depth = self.depth
            classes = attrs.get('class', '').split()
            if self.abstract_depth is None and (attrs.get('id') == 'abstract' or 'abstract' in classes) and tag in ('div', 'blockquote', 'section', 'p'):
                self.abstract_depth = self.depth

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in ('meta', 'link', 'br', 'hr', 'img', 'input', 'wbr', 'source', 'area', 'base', 'embed', 'param'):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in ('meta', 'link', 'br', 'hr', 'img', 'input', 'wbr', 'source', 'area', 'base', 'embed', 'param'):
            return
        if self.depth == self.abstract_depth:
            self.abstract_depth = None
        if self.depth == self.ignore_depth:
            self.ignore_depth = None
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if self.ignore_depth is None:
            self.text.append(data)
            if self.abstract_depth is not None:
                self.abstract_parts.append(data)

    def first(self, *names):
        return next((clean(self.meta[n][0]) for n in names if self.meta.get(n) and self.meta[n][0]), '')


def exact_date(value):
    value = value.strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d %b %Y', '%d %B %Y'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise VerificationError('Publication date missing or lacks exact day precision')


def venue_abbreviation(value):
    value = clean(value).casefold()
    if re.search(r'\b(workshops?|findings|demonstrations?|companion|tutorials?)\b', value):
        return ''
    for name, aliases in VENUES.items():
        if any(re.search(r'(?<![a-z0-9])' + re.escape(a) + r'(?![a-z0-9])', value) for a in aliases):
            return name
    return ''


def canonical_url(value):
    value = safe_scholarly_url(value)
    u = urlparse(value)
    if u.hostname in ('arxiv.org', 'www.arxiv.org', 'export.arxiv.org'):
        aid = arxiv_id(u.path)
        if not aid or not re.fullmatch(r'/(abs|pdf)/[^?#]+', u.path):
            raise VerificationError('Not an arXiv paper page')
        return 'https://arxiv.org/abs/' + aid
    return value


def verify_candidate(candidate, since, until, timeout=25):
    if not isinstance(candidate, dict) or not isinstance(candidate.get('title'), str):
        raise VerificationError('Candidate must have a title and primary-source URL')
    url = canonical_url(candidate.get('url'))
    page = MetadataParser()
    page.feed(fetch_page(url, timeout=timeout))
    title = page.first('citation_title', 'dc.title')
    if not title or norm_title(title) != norm_title(candidate['title']):
        raise VerificationError('Candidate title does not match primary-source metadata')
    abstract = clean(' '.join(page.abstract_parts)) or page.first('citation_abstract', 'dc.description', 'description')
    abstract = re.sub(r'^Abstract\s*:?\s*', '', abstract, flags=re.I).strip()
    if len(abstract) < 80 or len(abstract) > 25000:
        raise VerificationError('Primary source does not provide a usable abstract')
    authors = [clean(a) for a in page.meta.get('citation_author', [])]
    is_arxiv = urlparse(url).hostname == 'arxiv.org'
    if is_arxiv:
        text = clean(' '.join(page.text))
        first = re.search(r'Submitted on\s+(\d{1,2} [A-Za-z]+ \d{4})', text)
        if not first:
            raise VerificationError('Cannot verify arXiv v1 submission date')
        published = exact_date(first.group(1))
        aid = arxiv_id(url)
        p = paper(source='arxiv', source_id=aid, title=title, abstract=abstract,
                  authors=authors, published=published, arxiv=aid, url=url,
                  publication_type='preprint', date_basis='arxiv_first_submission')
        label, basis = 'arXiv', 'arxiv_first_submission'
        pdf = 'https://arxiv.org/pdf/' + aid
    else:
        venue = page.first('citation_conference_title', 'citation_inbook_title', 'prism.publicationname')
        # Journal metadata is not conference evidence (including PACM/VLDB until verified explicitly).
        label = venue_abbreviation(venue)
        if not label:
            raise VerificationError('No verified allowed main-conference venue in source metadata')
        if urlparse(url).hostname == 'aclanthology.org' and not re.search(r'/(\d{4})\.(acl|emnlp)-(long|short)\.\d+/?$', urlparse(url).path):
            raise VerificationError('ACL/EMNLP record is not a main-conference paper')
        published = exact_date(page.first('citation_online_date', 'citation_publication_date', 'dc.date'))
        doi = page.first('citation_doi')
        p = paper(source='conference', source_id=doi or url, title=title, abstract=abstract,
                  authors=authors, published=published, doi=doi, url=url, venue=label,
                  publication_type='conference', date_basis='conference_publication')
        basis = 'conference_publication'
        raw_pdf = page.first('citation_pdf_url')
        try:
            pdf = safe_scholarly_url(urljoin(url, raw_pdf)) if raw_pdf else ''
        except ValueError:
            pdf = ''
    if not since <= date.fromisoformat(published) <= until:
        raise VerificationError('Verified publication date outside requested window: ' + published)
    p.update(venue_label=label, date_basis=basis, display_date=published, pdf_url=pdf,
             verification={'url':url, 'method':'primary_source_metadata', 'date':published},
             publication_events=[{'date':published, 'basis':basis, 'url':url, 'venue':label}],
             ccf_venue=not is_arxiv)
    return p


def verify_directory_match(title, directory_url, timeout=15):
    """A directory hit narrows discovery; it never establishes a conference route."""
    venue = next((name for name, urls in DIRECTORY_SOURCES.items() if directory_url in urls), None)
    if not venue:
        raise VerificationError('Directory URL is not an audited conference source')
    req = urllib.request.Request(directory_url, headers={'User-Agent':'Awesome-GNN/0.3 directory verification'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.url != directory_url:
            raise VerificationError('Directory redirected outside audited URL')
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise VerificationError('Directory too large')
        if raw.startswith(b'\x1f\x8b'):
            import gzip
            raw = gzip.decompress(raw)
    page = MetadataParser(); page.feed(raw.decode('utf-8', errors='replace'))
    text = clean(' '.join(page.text))
    normalized = norm_title(title)
    if len(normalized) < 20 or normalized not in norm_title(text):
        raise VerificationError('Exact paper title absent from audited conference directory')
    return {'venue':venue, 'directory_url':directory_url, 'status':'title_listed_only'}
