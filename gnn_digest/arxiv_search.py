"""Extract bounded discovery leads from arXiv's public search page."""

import re
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse

from .http import request
from .models import arxiv_id, clean


class ArxivResults(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.item = None
        self.title_depth = 0
        self.title_parts = []
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get('class', '').split())
        if tag == 'li' and 'arxiv-result' in classes:
            self.item = {'url': '', 'title': ''}
            self.text_parts = []
        if self.item is None:
            return
        if tag == 'p' and 'title' in classes:
            self.title_depth = 1
            self.title_parts = []
        elif self.title_depth:
            self.title_depth += 1
        if tag == 'a':
            url = attrs.get('href', '')
            parsed = urlparse(url)
            if parsed.hostname in ('arxiv.org', 'www.arxiv.org') and parsed.path.startswith('/abs/'):
                aid = arxiv_id(parsed.path)
                if aid:
                    self.item['url'] = 'https://arxiv.org/abs/' + aid

    def handle_endtag(self, tag):
        if self.item is None:
            return
        if self.title_depth:
            self.title_depth -= 1
            if not self.title_depth:
                self.item['title'] = clean(''.join(self.title_parts))
        if tag == 'li':
            text = clean(' '.join(self.text_parts))
            match = re.search(r'Submitted\s+(\d{1,2}\s+[A-Za-z]+,?\s+\d{4})', text, re.I)
            if match:
                for fmt in ('%d %B %Y', '%d %b %Y', '%d %B, %Y', '%d %b, %Y'):
                    try:
                        self.item['submitted'] = datetime.strptime(match.group(1), fmt).date().isoformat()
                        break
                    except ValueError:
                        pass
            if self.item['url'] and self.item['title']:
                self.results.append(self.item)
            self.item = None

    def handle_data(self, data):
        if self.item is not None:
            self.text_parts.append(data)
            if self.title_depth:
                self.title_parts.append(data)


def search_html(query, since, until, *, limit=10, timeout=18):
    params = {'query': query, 'searchtype': 'all', 'abstracts': 'show',
              'order': '-announced_date_first', 'size': 50}
    raw = request('https://arxiv.org/search/?' + urlencode(params), timeout=timeout, attempts=1)
    parser = ArxivResults()
    parser.feed(raw.decode('utf-8', errors='replace'))
    seen, leads = set(), []
    for item in parser.results:
        submitted = item.get('submitted')
        if submitted and not since <= date.fromisoformat(submitted) <= until:
            continue
        if item['url'] in seen:
            continue
        seen.add(item['url'])
        leads.append({'title': item['title'], 'url': item['url']})
        if len(leads) >= limit:
            break
    return leads


def model_arxiv_queries(actions, *, limit=3):
    """Reuse search terms chosen by the model; strip web-engine routing syntax."""
    result, seen = [], set()
    for action in actions:
        for raw in action.get('queries') or [action.get('query', '')]:
            if not isinstance(raw, str) or 'arxiv.org' not in raw.casefold():
                continue
            query = re.sub(r'site:arxiv\.org(?:/[^\s]*)?', ' ', raw, flags=re.I)
            query = re.sub(r'\b20\d{2}\b', ' ', query)
            query = re.sub(r'\b260[1-9]\b', ' ', query)
            query = re.sub(r'\b(?:OR|AND)\b', ' ', query, flags=re.I)
            query = re.sub(r'\barxiv\b', ' ', query, flags=re.I)
            query = re.sub(r'-survey\b', ' ', query, flags=re.I)
            query = re.sub(r'[^\w\s-]', ' ', query)
            query = ' '.join(query.split())[:100]
            if len(query.split()) < 2 or query.casefold() in seen:
                continue
            seen.add(query.casefold())
            result.append(query)
            if len(result) >= limit:
                return result
    return result
