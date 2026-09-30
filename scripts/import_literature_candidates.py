"""Verify and summarize a reviewed candidate manifest without search quotas.

Usage: python scripts/import_literature_candidates.py --manifest PATH
Each completed item is cached. Only ready, full-text-grounded records may later
be merged into the public archive; unresolved records remain in the audit.
"""
import argparse
import concurrent.futures
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gnn_digest.agent import validate_topics
from gnn_digest.cli import load_env
from gnn_digest.fulltext import load_fulltext
from gnn_digest.llm import Summarizer
from gnn_digest.models import norm_title, identity_keys, paper
from gnn_digest.storage import read_json, write_json
from gnn_digest.verification import verify_candidate, VerificationError, fetch_page, MetadataParser
from scripts.audit_literature import fetch

FOLDER = ROOT / '.local/literature-audit'
ICLR_PROCEEDINGS = {norm_title(x['title']):x for x in read_json(FOLDER/'iclr-proceedings.json',[])}

def verify_log_schedule(c):
    """Use an independently fetched official embedded public schedule snapshot."""
    records=read_json(ROOT/'data/log_official_program.json',[])
    match=next((x for x in records if norm_title(x['title'])==norm_title(c['title']) and x['year']==c['year']),None)
    if not match:
        raise VerificationError('Exact title missing from verified main-conference schedule')
    snapshot=FOLDER/match['csv_snapshot']
    if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=match['sha256']:
        raise VerificationError('Official schedule snapshot changed')
    year=str(match['year']);url=match['program_url'];oid=match['openreview_url'].split('id=')[1]
    p=paper(source='conference',source_id=match['openreview_url'],title=match['title'],published=year,url=url,venue='LoG',publication_type='conference',date_basis='conference_edition')
    p.update(venue_label='LoG',conference_year=match['year'],date_basis='conference_edition',date_precision='year',display_date=year,pdf_url='https://openreview.net/pdf?id='+oid,ccf_venue=True,
             verification={'url':url,'method':'official_embedded_poster_schedule','date':year,'openreview_id':oid,'snapshot_sha256':match['sha256']},publication_events=[{'url':url,'date':year,'basis':'conference_edition','venue':'LoG'}])
    return p

def verify_emnlp_schedule(c):
    records=read_json(ROOT/'data/emnlp_2026_official_papers.json',[])
    match=next((x for x in records if norm_title(x['title'])==norm_title(c['title']) and x['track']=='MAIN' and x['year']==c['year']),None)
    if not match:raise VerificationError('Exact title absent from official MAIN program')
    snapshot=FOLDER/'emnlp2026-program.csv'
    if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=match['snapshot_sha256']:raise VerificationError('Official program snapshot changed')
    year=str(match['year']);url=match['program_url']
    p=paper(source='conference',source_id='EMNLP:2026:'+match['paper_id'],title=match['title'],published=year,url=url,venue='EMNLP',publication_type='conference',date_basis='conference_edition')
    p.update(venue_label='EMNLP',conference_year=2026,date_basis='conference_edition',date_precision='year',display_date=year,pdf_url='',ccf_venue=True,
             verification={'url':url,'method':'official_main_program_csv','date':year,'program_paper_id':match['paper_id'],'public_csv_url':match['public_csv_url'],'snapshot_sha256':match['snapshot_sha256']},publication_events=[{'url':url,'date':year,'basis':'conference_edition','venue':'EMNLP'}])
    return p

def item_key(c):
    return hashlib.sha256(norm_title(c['title']).encode()).hexdigest()[:24]

def process(c, engine, known_keys):
    key = item_key(c); destination = FOLDER/'outcomes'/f'{key}.json'
    if destination.exists(): return read_json(destination,{})
    result = {'title':c['title'],'venue':c['venue_label'],'year':c['year'],
              'discovery':{k:c[k] for k in ('detail_path','directory_url','discovered_via','category','catalog_id') if k in c},
              'checked_at':datetime.now(timezone.utc).isoformat()}
    urls = []
    if c['venue_label']=='ICLR' and norm_title(c['title']) in ICLR_PROCEEDINGS:
        urls.append(ICLR_PROCEEDINGS[norm_title(c['title'])]['url'])
    urls += [x['url'] for x in c.get('official_matches',[]) if '/virtual/' in x['url']]
    if c.get('url'): urls.append(c['url'])
    detail = ''
    if c.get('detail_path'):
        try:
            detail=fetch(c['detail_path'])
            urls += re.findall(r'\[[^\]]+\]\((https?://[^)]+)\)',detail)
        except Exception as exc: result['detail_error']=type(exc).__name__
    errors=[]; p=None
    if c['venue_label']=='EMNLP' and c['year']==2026:
        try:p=verify_emnlp_schedule(c)
        except Exception as exc:errors.append({'error':str(exc)[:200]})
    if c['venue_label']=='LoG':
        try:p=verify_log_schedule(c)
        except Exception as exc:errors.append({'error':str(exc)[:200]})
    for raw in dict.fromkeys(urls):
        if p is not None:break
        url=re.sub(r'^http:','https:',raw)
        if not any(host in url for host in ('doi.org/','dl.acm.org/','ojs.aaai.org/','ijcai.org/','aclanthology.org/','proceedings.mlr.press/','neurips.cc/','papers.nips.cc/','openaccess.thecvf.com/','icml.cc/virtual/','iclr.cc/virtual/','proceedings.iclr.cc/','vldb.org/','ieeexplore.ieee.org/')): continue
        try:
            candidate={'title':c['title'],'url':url,'_conference_year':c['year']}
            verified=verify_candidate(candidate,date(2025,1,1),date.today(),timeout=22)
            if verified.get('venue_label')!=c['venue_label'] or verified.get('conference_year')!=c['year']:
                raise VerificationError('Verified conference edition does not match latest selected edition')
            p=verified;break
        except Exception as exc:
            errors.append({'url':url,'error':str(exc)[:200] if isinstance(exc,ValueError) else type(exc).__name__})
            if isinstance(exc,VerificationError) and 'title does not match primary-source metadata' in str(exc):
                # A catalogue title is a discovery hint. Read the actual linked
                # paper's title and verify that record, without claiming the
                # original (possibly malformed) title was correct.
                try:
                    meta=MetadataParser();meta.feed(fetch_page(url,timeout=15))
                    actual=meta.first('citation_title','dc.title')
                    verified=verify_candidate({'title':actual,'url':url,'_conference_year':c['year']},date(2025,1,1),date.today(),timeout=20)
                    if verified.get('venue_label')==c['venue_label'] and verified.get('conference_year')==c['year']:
                        result.update(original_catalog_title=c['title'],title=verified['title']);p=verified;break
                except Exception:pass
    if p is None:
        result.update(status='metadata_unresolved',errors=errors or [{'error':'No accessible eligible official source link'}])
    elif identity_keys(p)&known_keys:
        result.update(status='already_in_archive',paper_id=p['id'])
    else:
        p['_allow_arxiv_lookup']=True
        mirrors=read_json(ROOT/'data/literature_fulltext_mirrors.json',[])
        mirror=next((x for x in mirrors if norm_title(x['title'])==norm_title(p['title'])),None)
        if mirror:
            p.update(pdf_url=mirror['pdf_url'],fulltext_mirror_discovery=mirror)
        # A repository's arXiv link is only a hint. Independently verify it.
        for raw in urls:
            if 'arxiv.org/' not in raw:continue
            try:
                alt=verify_candidate({'title':p['title'],'url':re.sub(r'^http:','https:',raw)},date(1991,1,1),date.today(),timeout=15)
                p.update(arxiv_id=alt['arxiv_id'],fulltext_alternate_verification=alt['verification'])
                if not p.get('pdf_url') or any(host in p['pdf_url'] for host in ('openreview','dl.acm','ieeexplore')): p['pdf_url']=alt['pdf_url']
                break
            except Exception: pass
        try:
            write_json(FOLDER/'papers'/f'{key}.json',p)
            load_fulltext(p,timeout=60,max_characters=240000)
            if engine is not None:engine.summarize(p)
            result.update(status=p['status'] if engine is not None else 'fulltext_prepared',paper_id=p['id'],topics=p.get('topics',[]),validation_errors=p.get('validation_errors',[]))
            p.pop('_allow_arxiv_lookup',None)
            write_json(FOLDER/'papers'/f'{key}.json',p)
        except Exception as exc:
            result.update(status='fulltext_unresolved',error=str(exc)[:250] if isinstance(exc,ValueError) else type(exc).__name__)
        if errors:result['earlier_source_errors']=errors
    write_json(destination,result)
    print(json.dumps({k:result[k] for k in ('status','venue','title')},ensure_ascii=False),flush=True)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--workers',type=int,default=3);parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args();load_env(ROOT/'.env')
    cfg=read_json(ROOT/'config.json',{})['llm']
    engine=None if args.prepare_only else Summarizer({**cfg,'require_fulltext':True,'evidence_mode':'segments','attempts':2,'timeout':120},(ROOT/'prompts/search.summary.zh.txt').read_text(encoding='utf-8'),extra_validator=validate_topics)
    archive=read_json(ROOT/'data/papers.json',{})['papers'];known_keys=set().union(*(identity_keys(p) for p in archive if p.get('status')=='ready'))
    manifest=read_json(Path(args.manifest),{})['candidates']
    manifest=[c for c in manifest if not c.get('existing_id')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        outcomes=list(pool.map(lambda c:process(c,engine,known_keys),manifest))
    write_json(ROOT/'data/literature_import_report.json',{'finished_at':datetime.now(timezone.utc).isoformat(),'manifest':args.manifest,'outcomes':outcomes})
    from collections import Counter
    print(json.dumps(dict(Counter(x['status'] for x in outcomes)),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
