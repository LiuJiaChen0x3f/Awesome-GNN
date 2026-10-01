"""Read public scholarly landing pages; model guesses never become metadata."""
import re
import calendar
import gzip
import io
import json
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser
from functools import lru_cache
from urllib.parse import urljoin, urlparse, quote, parse_qs

from .models import arxiv_id, clean, norm_title, paper

TOPICS = ('TAG', 'OOD')
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
    'WWW': ('the web conference', 'acm web conference', 'acm on web conference', 'international world wide web conference', 'www'),
    'ICDE': ('international conference on data engineering', 'icde'),
    'EMNLP': ('empirical methods in natural language processing', 'emnlp'),
    'ACM MM': ('acm international conference on multimedia', 'acm multimedia', 'acm mm'),
    'ICLR': ('international conference on learning representations', 'iclr'),
    'LoG': ('learning on graphs conference', 'learning on graphs', 'log'),
    'ICDM': ('international conference on data mining', 'icdm'),
    'WSDM': ('web search and data mining', 'wsdm'),
    'NAACL': ('north american chapter of the association for computational linguistics', 'nations of the americas chapter of the association for computational linguistics', 'naacl'),
}
DOMAINS = ('arxiv.org', 'doi.org', 'aclanthology.org', 'proceedings.mlr.press', 'proceedings.neurips.cc',
           'papers.nips.cc', 'openaccess.thecvf.com', 'dl.acm.org', 'ieeexplore.ieee.org',
           'ojs.aaai.org', 'ijcai.org', 'vldb.org', 'proceedings.com')
DOMAINS += ('icml.cc', 'iclr.cc', 'openreview.net', 'sigmod.org', 'logconference.org', 'mn.cs.tsinghua.edu.cn')
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
        if raw.startswith(b'\x1f\x8b'):
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                raw = stream.read(3_000_001)
        if len(raw) > 3_000_000:
            raise VerificationError('Source page too large')
        return raw.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')


class MetadataParser(HTMLParser):
    def __init__(self, ijcai_abstract=False):
        super().__init__(convert_charrefs=True)
        self.meta, self.text, self.abstract_parts = {}, [], []
        self.depth, self.abstract_depth, self.ignore_depth = 0, None, None
        self.ijcai_abstract = ijcai_abstract

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
            if self.abstract_depth is None and (attrs.get('id') == 'abstract' or 'abstract' in classes or
                    (self.ijcai_abstract and 'col-md-12' in classes)) and tag in ('div', 'blockquote', 'section', 'p'):
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


def publication_date(value, since, until):
    """Preserve coarse publisher precision for wide windows; never invent a day."""
    try:
        result = exact_date(value)
        if not since <= date.fromisoformat(result) <= until:
            raise VerificationError('Verified publication date outside requested window: ' + result)
        return result, 'day'
    except VerificationError as error:
        if 'outside' in str(error):
            raise
    value = value.strip().replace('/', '-')
    if re.fullmatch(r'\d{4}-\d{1,2}', value):
        year, month = map(int, value.split('-'))
        value=f'{year:04d}-{month:02d}'
        lo = date(year, month, 1)
        hi = date(year, month, calendar.monthrange(year, month)[1])
        precision = 'month'
    elif re.fullmatch(r'\d{4}', value):
        year = int(value)
        lo, hi = date(year, 1, 1), date(year, 12, 31)
        precision = 'year'
    else:
        raise VerificationError('Publication date missing or unrecognized precision')
    # A published primary proceedings page has been fetched now. This permits
    # the current incomplete year/month only for a window ending today.
    if since <= lo and (hi <= until or (until == date.today() and lo <= until)):
        return value, precision
    raise VerificationError('Partial publication date cannot establish requested window eligibility')


def conference_edition(url, venue, published):
    path = urlparse(url).path
    match = re.search(r'(?:/proceedings/|/paper/|/content/[^/]*|/)(20\d{2})(?:[/.?_-]|$)', path, re.I)
    if not match:
        match = re.search(r'\b(20\d{2})\b', venue)
    return int(match.group(1)) if match else int(published[:4])


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


def verify_icml_program(candidate, since, until, timeout):
    """Verify the official program's own structured publication record."""
    url = canonical_url(candidate['url'])
    label = {'icml.cc':'ICML', 'iclr.cc':'ICLR'}.get(urlparse(url).hostname)
    if not label:
        raise VerificationError('Unsupported official program host')
    match = re.search(r'/virtual/(20\d{2})/(?:poster|oral)/\d+$',urlparse(url).path)
    if not match:
        raise VerificationError('Need an individual ICML conference program paper')
    year = int(match.group(1))
    raw = fetch_page(url, timeout)
    ids = re.findall(r'https://openreview.net/forum\?id=([A-Za-z0-9_-]+)',raw)
    if not ids:
        raise VerificationError('Official ICML paper has no OpenReview record')
    records=[]
    for block in re.findall(r'<script\b[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>',raw,re.S|re.I):
        try:
            value=json.loads(block)
            if isinstance(value,dict): records.append(value)
        except ValueError:
            pass
    record=next((r for r in records if r.get('@type')=='CreativeWork' and
        norm_title(r.get('name',''))==norm_title(candidate['title']) and r.get('creditText')==f'{label} {year}'),None)
    if not record:
        raise VerificationError('Official ICML structured title/edition record missing or mismatched')
    title=record['name']
    published,precision=publication_date(record.get('datePublished',''),since,until)
    parser=MetadataParser();parser.feed(raw)
    p=paper(source='conference',source_id=url,title=title,abstract=clean(' '.join(parser.abstract_parts)),
            authors=[a['name'] for a in record.get('author',[]) if isinstance(a,dict) and a.get('name')],
            published=published,url=url,venue=label,publication_type='conference',date_basis='conference_program_publication')
    pdf='https://openreview.net/pdf?id='+ids[0]
    p.update(venue_label=label,date_basis='conference_program_publication',date_precision=precision,
        conference_year=year,display_date=published,pdf_url=pdf,ccf_venue=True,
        verification={'url':url,'method':'official_program_jsonld','date':published,'openreview_id':ids[0]},
        publication_events=[{'date':published,'basis':'conference_program_publication','url':url,'venue':label}])
    return p


def verify_crossref(candidate, since, until, timeout):
    """Publisher-deposited DOI metadata for inaccessible ACM/IEEE detail pages."""
    from .http import get_json
    url=canonical_url(candidate['url'])
    match=re.search(r'(10\.\d{4,9}/[^?#]+)',url)
    if not match:
        raise VerificationError('Inaccessible proceedings page without a DOI')
    doi=match.group(1).rstrip('/')
    value=get_json('https://api.crossref.org/works/'+quote(doi,safe=''),timeout=timeout,attempts=1)['message']
    title=clean((value.get('title') or [''])[0])
    venue=' '.join(value.get('container-title',[]))
    label=venue_abbreviation(venue)
    if norm_title(title)!=norm_title(candidate['title']):
        raise VerificationError('Candidate title does not match publisher DOI metadata')
    membership=None
    if value.get('type')=='journal-article':
        # These conferences use journal-style proceedings. Both the publisher
        # record and the exact title on the edition's research list are needed.
        if venue.casefold()=='proceedings of the acm on management of data':
            label='SIGMOD'
        elif venue.casefold() in ('proceedings of the vldb endowment','proceedings of the vldb endowment (pvldb)'):
            label='VLDB'
        else:
            label=''
        if label:
            membership=verify_program_membership(title,label,candidate.get('_conference_year'))
    if not label or (value.get('type')!='proceedings-article' and not membership):
        raise VerificationError('DOI is not an eligible main-conference proceedings article')
    parts=next((value[k]['date-parts'][0] for k in ('published-online','published-print','published','issued') if value.get(k,{}).get('date-parts')),[])
    raw='-'.join(str(x) if i==0 else f'{x:02d}' for i,x in enumerate(parts))
    published,precision=publication_date(raw,since,until)
    authors=[' '.join(filter(None,(a.get('given'),a.get('family')))) for a in value.get('author',[])]
    p=paper(source='conference',source_id=doi,title=title,abstract=value.get('abstract',''),authors=authors,
            published=published,doi=doi,url=url,venue=label,publication_type='conference',date_basis='conference_publication')
    pdf=''
    for link in value.get('link',[]):
        raw=link.get('URL','')
        if link.get('content-type')=='application/pdf' or re.search(r'\.pdf(?:\?|$)|/doi/pdf/',raw,re.I):
            try:
                pdf=safe_scholarly_url('https://'+raw[7:] if raw.startswith('http://') else raw)
                break
            except VerificationError:
                continue
    if label=='VLDB' and re.fullmatch(r'\d{1,3}',str(value.get('volume',''))):
        try:
            # The DOI may advertise only an ACM mirror. The official volume
            # index embeds its original PDF links as structured Next.js data.
            pdf=vldb_pdf_index(str(value['volume'])).get(norm_title(title),pdf)
        except Exception:
            pass
    # The discovery agent must supply an independently verified matching
    # arXiv record when the publisher PDF is inaccessible.
    p.update(venue_label=label,date_basis='conference_publication',date_precision=precision,
        conference_year=membership['year'] if membership else conference_edition(url,venue,published),display_date=published,pdf_url=pdf,ccf_venue=True,
        verification={'url':url,'method':'publisher_deposited_crossref','date':published,'doi':doi},
        publication_events=[{'date':published,'basis':'conference_publication','url':url,'venue':label}])
    if membership:
        p.update(conference_evidence=membership,publication_type='conference-associated-journal')
    return p


class VLDBResearchProgramParser(HTMLParser):
    """Read paper titles only within the 2026 program's research sessions.

    The same page also contains tutorials, demos and workshops. Their mere
    presence must never establish membership in the main research track.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.titles, self.parts = [], [], []
        self.title_depth = None

    def handle_starttag(self, tag, attrs):
        if tag in ('meta', 'link', 'br', 'hr', 'img', 'input', 'wbr', 'source', 'area', 'base', 'embed', 'param'):
            return
        attrs = dict(attrs)
        self.stack.append((tag, attrs.get('id', '')))
        research = any(re.fullmatch(r'res-\d+', ident) for _, ident in self.stack)
        if self.title_depth is None and research and 'ptitle' in attrs.get('class', '').split():
            self.title_depth = len(self.stack)
            self.parts = []

    def handle_data(self, data):
        if self.title_depth is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        positions = [i for i, (name, _) in enumerate(self.stack) if name == tag]
        if not positions:
            return
        index = positions[-1]
        if self.title_depth is not None and index < self.title_depth:
            self.titles.append(clean(' '.join(self.parts)))
            self.title_depth = None
        del self.stack[index:]


@lru_cache(maxsize=8)
def program_text(url):
    raw = fetch_page(url, timeout=20)
    if url == 'https://www.vldb.org/2026/program.html':
        parser = VLDBResearchProgramParser()
        parser.feed(raw)
        if not parser.titles:
            raise VerificationError('VLDB research-session titles unavailable; do not fall back to all program text')
        return '\n'.join(parser.titles)
    parser=MetadataParser();parser.feed(raw)
    return clean(' '.join(parser.text))


@lru_cache(maxsize=4)
def vldb_pdf_index(volume):
    if not re.fullmatch(r'\d{1,3}',volume):
        raise VerificationError('Invalid PVLDB volume')
    raw=fetch_page(f'https://www.vldb.org/pvldb/volumes/{volume}/',timeout=20)
    match=re.search(r'<script\b[^>]*id=[\"\']__NEXT_DATA__[\"\'][^>]*>(.*?)</script>',raw,re.S|re.I)
    if not match:
        return {}
    records={}
    def visit(node):
        if isinstance(node,dict):
            if isinstance(node.get('title'),str) and isinstance(node.get('pdf'),str):
                try:
                    pdf=safe_scholarly_url(node['pdf'])
                    parsed=urlparse(pdf)
                    if parsed.hostname in ('vldb.org','www.vldb.org') and parsed.path.startswith('/pvldb/vol'+volume+'/'):
                        records.setdefault(norm_title(node['title']),set()).add(pdf)
                except VerificationError:
                    pass
            for value in node.values(): visit(value)
        elif isinstance(node,list):
            for value in node: visit(value)
    visit(json.loads(match.group(1)))
    return {title:next(iter(urls)) for title,urls in records.items() if len(urls)==1}


def verify_program_membership(title, venue, expected_year=None):
    years=[expected_year] if expected_year in (2025,2026) else [2026,2025]
    for year in years:
        url=(f'https://{year}.sigmod.org/sigmod_papers.shtml' if venue=='SIGMOD'
             else f'https://www.vldb.org/{year}/program.html')
        try:
            text=program_text(url)
            if len(norm_title(title))>=20 and norm_title(title) in norm_title(text):
                return {'venue':venue,'year':year,'url':url,'status':'exact_title_on_official_research_program'}
        except Exception:
            continue
    raise VerificationError('Journal-style proceedings title not verified on official conference research program')


def verify_vldb_pdf(candidate,since,until,timeout):
    from .fulltext import read_document
    url=canonical_url(candidate['url'])
    text,kind=read_document(url,timeout)
    text='\n'.join(clean(line) for line in text.splitlines() if clean(line))
    if kind!='pdf' or not 500<=len(text)<=120000 or norm_title(candidate['title']) not in norm_title(text[:10000]):
        raise VerificationError('VLDB PDF title/full-text bounds could not be verified')
    match=re.search(r'10\.14778/\d+\.\d+',text[:10000])
    if not match:
        raise VerificationError('VLDB PDF has no publisher DOI in its first pages')
    p=verify_crossref({**candidate,'url':'https://doi.org/'+match.group()},since,until,timeout)
    if p['venue_label']!='VLDB' or not p.get('conference_evidence'):
        raise VerificationError('VLDB PDF is not linked to an eligible conference edition')
    p.update(pdf_url=url,full_text=text,fulltext_source={'url':url,'format':'pdf','scope':'full_text','characters':len(text)})
    return p


def verify_candidate(candidate, since, until, timeout=25):
    if not isinstance(candidate, dict) or not isinstance(candidate.get('title'), str):
        raise VerificationError('Candidate must have a title and primary-source URL')
    url = canonical_url(candidate.get('url'))
    host = urlparse(url).hostname
    if host in ('openreview.net','www.openreview.net'):
        raise VerificationError('An OpenReview submission forum alone cannot establish main-conference acceptance; use official proceedings/program')
    if host in ('icml.cc', 'iclr.cc'):
        return verify_icml_program(candidate,since,until,timeout)
    if host in ('www.vldb.org','vldb.org') and re.fullmatch(r'/pvldb/vol\d+/[^/]+\.pdf',urlparse(url).path):
        return verify_vldb_pdf(candidate,since,until,timeout)
    page = MetadataParser(ijcai_abstract=host in ('ijcai.org', 'www.ijcai.org'))
    try:
        page.feed(fetch_page(url, timeout=timeout))
    except Exception:
        if host in ('dl.acm.org','doi.org') and re.search(r'10\.\d{4,9}/',url):
            return verify_crossref(candidate,since,until,timeout)
        raise
    title = page.first('citation_title', 'dc.title')
    if not title and host in ('dl.acm.org','doi.org') and re.search(r'10\.\d{4,9}/',url):
        return verify_crossref(candidate,since,until,timeout)
    if not title or norm_title(title) != norm_title(candidate['title']):
        raise VerificationError('Candidate title does not match primary-source metadata')
    abstract = clean(' '.join(page.abstract_parts)) or page.first('citation_abstract', 'dc.description', 'description')
    abstract = re.sub(r'^Abstract\s*:?\s*', '', abstract, flags=re.I).strip()
    if len(abstract) > 25000:
        abstract = ''
    authors = [clean(a) for a in page.meta.get('citation_author', [])]
    is_arxiv = host == 'arxiv.org'
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
        text = clean(' '.join(page.text))
        track = ''
        if host == 'ojs.aaai.org' and re.search(r'/AAAI/article/view/\d+', url):
            if not re.search(r'Technical Tracks?', text, re.I):
                raise VerificationError('AAAI page does not identify a technical main track')
            venue = page.first('citation_journal_title') or venue
        if host in ('proceedings.neurips.cc','papers.nips.cc','proceedings.iclr.cc'):
            path = urlparse(url).path
            datasets = (host != 'proceedings.iclr.cc' and
                        path.endswith('-Abstract-Datasets_and_Benchmarks_Track.html') and
                        'Datasets and Benchmarks Track' in text)
            if not re.search(r'-Abstract(?:-Conference)?\.html$', path) and not datasets:
                raise VerificationError('Proceedings record is not an allowed archival research track')
            track = 'Datasets and Benchmarks' if datasets else 'Main Track'
            venue = page.first('citation_journal_title') or venue
        # Journal metadata is not conference evidence (including PACM/VLDB until verified explicitly).
        label = venue_abbreviation(venue)
        if not label:
            raise VerificationError('No verified allowed main-conference venue in source metadata')
        if host in ('ijcai.org', 'www.ijcai.org'):
            match = re.search(r'\b(Main Track|AI and Social Good|AI and Health|AI4Tech(?:: AI Enabling Technologies)?)\.\s*Pages\b', text)
            if not match:
                raise VerificationError('IJCAI record is not an allowed archival research track')
            track = match.group(1)
        if urlparse(url).hostname == 'aclanthology.org' and not re.search(r'/(\d{4})\.(acl|emnlp|naacl)-(main|long|short)\.\d+/?$', urlparse(url).path):
            raise VerificationError('ACL/EMNLP record is not a main-conference paper')
        published, precision = publication_date(page.first('citation_online_date', 'citation_publication_date', 'dc.date', 'citation_date'), since, until)
        doi = page.first('citation_doi')
        p = paper(source='conference', source_id=doi or url, title=title, abstract=abstract,
                  authors=authors, published=published, doi=doi, url=url, venue=label,
                  publication_type='conference', date_basis='conference_publication')
        basis = 'conference_publication'
        p.update(date_precision=precision, conference_year=conference_edition(url, venue, published))
        if track:
            p['publication_track'] = track
        raw_pdf = page.first('citation_pdf_url')
        try:
            pdf = safe_scholarly_url(urljoin(url, raw_pdf)) if raw_pdf else ''
        except ValueError:
            pdf = ''
    if is_arxiv and not since <= date.fromisoformat(published) <= until:
        raise VerificationError('Verified publication date outside requested window: ' + published)
    p.update(venue_label=label, date_basis=basis, display_date=published, pdf_url=pdf,
             verification={'url':url, 'method':'primary_source_metadata', 'date':published},
             publication_events=[{'date':published, 'basis':basis, 'url':url, 'venue':label}],
             ccf_venue=not is_arxiv)
    if p.get('publication_track'):
        p['verification']['track'] = p['publication_track']
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
