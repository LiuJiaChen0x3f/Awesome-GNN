"""Read-only, bounded official conference source audit (no LLM or archive writes)."""
import argparse
import gzip
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.current=None; self.meta={}; self.parts=[]; self.ignored=0
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag in ('script','style'): self.ignored+=1
        if tag=='a': self.current=[a.get('href') or '','']
        if tag=='meta': self.meta[a.get('name',a.get('property','')).lower()]=a.get('content','')
    def handle_data(self, text):
        if not self.ignored: self.parts.append(text)
        if self.current is not None: self.current[1]+=text
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.ignored=max(0,self.ignored-1)
        if tag=='a' and self.current is not None:
            self.links.append(self.current); self.current=None

def fetch(url, pdf=False):
    start=time.monotonic()
    result={'url':url}
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Awesome-GNN/0.3 source availability audit'})
        with urllib.request.urlopen(req,timeout=18) as r:
            raw=r.read(1024 if pdf else 6_000_001)
            result.update(http=r.status,final_url=r.url,content_type=r.headers.get('Content-Type',''),bytes_read=len(raw))
            encoding=r.headers.get('Content-Encoding','')
        if not pdf and (encoding=='gzip' or raw.startswith(b'\x1f\x8b')): raw=gzip.decompress(raw)
        if pdf:
            result['pdf_signature']=raw.startswith(b'%PDF-'); return result,None
        page=Page(); page.feed(raw.decode('utf8',errors='replace'))
        result.update(truncated=len(raw)>6_000_000, title=page.meta.get('citation_title',''),
            date=page.meta.get('citation_publication_date',page.meta.get('dc.date','')),
            venue=page.meta.get('citation_conference_title',page.meta.get('citation_inbook_title','')),
            text_excerpt=' '.join(' '.join(page.parts).split())[:300])
        return result,page
    except urllib.error.HTTPError as e: result['http']=e.code
    except Exception as e: result['error']=type(e).__name__
    finally: result['seconds']=round(time.monotonic()-start,2)
    return result,None

PATTERN=r'/virtual/\d{4}/(?:poster|oral)/\d+|/hash/.*Abstract|/html/.*\.html|/proceedings/\d{4}/\d+|/\d{4}\.(?:acl|emnlp)-(?:main|long|short)\.\d+/?$|/article/view/\d+|/v\d+/[^/]+\.html|/doi/(?:abs/)?10\.|/document/\d+|/papers/.*\.pdf|/vol\d+/[^/]+\.pdf'

def audit(entry):
    result={k:v for k,v in entry.items() if k!='urls'}; result['attempts']=[]
    for url in entry['urls']:
        listing,page=fetch(url); result['attempts'].append(listing)
        if page is None: continue
        links=[]
        for href,title in page.links:
            u=urllib.parse.urljoin(url,href)
            if re.search(PATTERN,u) and u.startswith('https://') and u not in [x[0] for x in links]:
                links.append((u,' '.join(title.split())))
        result['paper_link_count']=len(links)
        result['discovery_links']=[{'url':urllib.parse.urljoin(url,u),'text':' '.join(t.split())[:140]} for u,t in page.links if any(s in (u+' '+t).lower() for s in ('proceeding','accepted','openreview','paper','2026','2025'))][:40]
        if not links: continue
        graph=[x for x in links if re.search(r'\bgraphs?\b|\bgnns?\b|heterophil|hypergraph',x[1],re.I)]
        result['graph_link_count']=len(graph)
        choices=graph or links
        chosen=next((x for x in choices if not x[0].lower().endswith('.pdf')),choices[0])
        result['sample_anchor_title']=chosen[1]
        detail,p=fetch(chosen[0],chosen[0].lower().endswith('.pdf')); result['sample']=detail
        if p:
            text=' '.join(' '.join(p.parts).split())
            matches=list(re.finditer(r'\bAbstract\b',text,re.I))
            match=matches[-1] if matches else None
            detail['abstract_section_excerpt']=text[match.end():match.end()+1100] if match else ''
            detail['citation_metadata']={k:v for k,v in p.meta.items() if k.startswith('citation_')}
            detail['related_links']=[{'url':urllib.parse.urljoin(chosen[0],u),'text':' '.join(t.split())[:100]} for u,t in p.links if any(s in u for s in ('.pdf','openreview.net','proceedings.mlr.press'))][:10]
            pdf=p.meta.get('citation_pdf_url') or next((urllib.parse.urljoin(chosen[0],u) for u,t in p.links if '/paper/' in u.lower() and '.pdf' in u.lower()),'')
            if pdf and pdf.startswith('https://'): detail['pdf_probe']=fetch(pdf,True)[0]
        if detail.get('http')==200: break
    print(f"{entry['venue']} {entry['year']}: list={result['attempts'][-1].get('http',result['attempts'][-1].get('error'))} links={result.get('paper_link_count',0)} sample={result.get('sample',{}).get('http')}",flush=True)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',default='docs/conference_sources.json')
    parser.add_argument('--output',default='docs/conference_source_audit.json')
    args=parser.parse_args()
    catalog=json.loads(Path(args.catalog).read_text(encoding='utf8'))
    with ThreadPoolExecutor(max_workers=4) as ex: results=list(ex.map(audit,catalog['probes']))
    output={'checked_at':datetime.now(timezone.utc).isoformat(),'scope':'Availability samples, not exhaustive paper ingestion or eligibility verification. HTTP 200 alone is not proof of usable metadata.','results':results}
    Path(args.output).write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

if __name__=='__main__': main()
