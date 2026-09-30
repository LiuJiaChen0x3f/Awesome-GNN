"""Snapshot a public literature index for a separate, reproducible coverage audit.

This only discovers candidates. Repository labels never establish acceptance,
topic relevance, or permission to include a paper in the public index.
"""
import concurrent.futures
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gnn_digest.models import norm_title
from gnn_digest.storage import read_json, write_json

CACHE = ROOT / '.local/literature-audit'
REPO = 'naganandy/graph-based-deep-learning-literature'
ALLOWED = {'aaai', 'acl', 'cvpr', 'emnlp', 'iccv', 'icml', 'ijcai', 'kdd', 'neurips', 'webconf', 'sigir', 'sigmod', 'vldb', 'icde', 'mm'}

def fetch(path):
    local = CACHE / (hashlib.sha256(path.encode()).hexdigest() + '.md')
    if not local.exists():
        r = requests.get(f'https://raw.githubusercontent.com/{REPO}/master/{path}', timeout=60)
        r.raise_for_status()
        local.write_text(r.content.decode('utf-8'), encoding='utf-8')
    return local.read_text(encoding='utf-8')

def discover():
    CACHE.mkdir(exist_ok=True, parents=True)
    tree = read_json(CACHE / 'tree.json', {})
    if not tree:
        r = requests.get(f'https://api.github.com/repos/{REPO}/git/trees/master?recursive=1', timeout=90)
        r.raise_for_status(); tree = r.json(); write_json(CACHE / 'tree.json', tree)
    if tree.get('truncated'):
        raise RuntimeError('Incomplete Git tree; do not claim full index coverage')
    paths = [x['path'] for x in tree['tree'] if re.fullmatch(r'conference-publications/folders/years/202[56]/publications_[^/]+/README.md', x['path'])]
    archive = read_json(ROOT / 'data/papers.json', {})['papers']
    known = {norm_title(p['title']):p['id'] for p in archive}
    candidates, indexes = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for path, content in zip(paths, pool.map(fetch, paths)):
            edition = re.search(r'/publications_(\w+)(\d{2})/', path)
            venue, year = edition[1], int('20' + edition[2])
            heading = ''; count = 0
            for line in content.splitlines():
                if line.startswith('#'): heading = line.lstrip('# ').strip()
                match = re.match(r'- \[(.+)\]\(https://github.com/' + re.escape(REPO) + r'/blob/master/([^ )]+)\)', line)
                if not match: continue
                title, detail = match.groups(); count += 1
                candidates.append({'title':title, 'venue':venue, 'year':year, 'category':heading,
                    'index_path':path, 'detail_path':detail, 'in_scope':venue in ALLOWED,
                    'existing_id':known.get(norm_title(title)), 'discovered_via':'literature_repository'})
            indexes.append({'path':path, 'venue':venue, 'year':year, 'entries':count, 'in_scope':venue in ALLOWED})
    report = {'snapshot_at':datetime.now(timezone.utc).isoformat(), 'tree_sha':tree['sha'], 'repository':REPO, 'indexes':indexes, 'candidates':candidates}
    write_json(ROOT / 'data/literature_candidates.json', report)
    print(json.dumps({'indexes':len(indexes), 'entries':len(candidates), 'in_scope':sum(c['in_scope'] for c in candidates), 'known':sum(bool(c['existing_id']) for c in candidates)}, ensure_ascii=False))
    (CACHE/'catalog.tsv').write_text('\n'.join(f"{i}\t{c['venue']}{c['year']}\t{c['category']}\t{c['title']}\t{bool(c['existing_id'])}" for i,c in enumerate(candidates)), encoding='utf-8')

if __name__ == '__main__':
    discover()
