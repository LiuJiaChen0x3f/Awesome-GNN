"""Validate and export cached audit results; never calls an LLM."""
import collections,copy,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from gnn_digest.models import merge_records,identity_keys,norm_title
from gnn_digest.storage import read_json,write_json,lock,export_site
from gnn_digest.summary_policy import validate_method
from gnn_digest.evidence import validate_evidence_list
from gnn_digest.agent import validate_topics
folder=root/'.local/literature-audit';ready=[];outcomes=[];skipped=[];excluded_keys=set()
latest=read_json(root/'data/latest_literature_candidates.json',{})['latest_editions'];latest['emnlp']=2026
scope=read_json(root/'data/literature_audit_scope.json',{})['conferences']
selected_year={s['venue_label']:s['selected_year'] for s in scope}
vldb_research={norm_title(t) for t in read_json(root/'data/vldb_2026_research_program.json',{})['titles']}
for path in (folder/'outcomes').glob('*.json'):
    outcome=read_json(path,{})
    outcomes.append(outcome)
    if outcome['status']!='ready':
        if outcome['status'] in ('excluded_track','irrelevant','superseded_edition'):
            excluded=read_json(folder/'papers'/path.name,{})
            if excluded:excluded_keys.update(identity_keys(excluded))
        continue
    p=read_json(folder/'papers'/path.name,{})
    if p.get('venue_label')=='VLDB' and p.get('conference_year')==2026 and norm_title(p['title']) not in vldb_research:
        skipped.append({'title':p['title'],'reason':'Not on official VLDB 2026 research-session title list'})
        excluded_keys.update(identity_keys(p));continue
    if p.get('venue_label')=='EMNLP' and p.get('conference_year')!=2026:
        skipped.append({'title':p['title'],'reason':'EMNLP 2026 official MAIN list supersedes 2025 for this audit'});continue
    if p.get('venue_label')=='LoG':
        skipped.append({'title':p['title'],'reason':'LoG 2026 acceptance already announced; latest official paper list/track verification remains unresolved'});continue
    if p.get('conference_year') != selected_year.get(p.get('venue_label')):
        skipped.append({'title':p['title'],'reason':'Does not match selected latest conference edition'});continue
    assert p['status']=='ready' and p.get('full_text') and p['fulltext_source']['scope']=='full_text'
    validate_method(p['method']);validate_evidence_list(p['evidence'],p['full_text'])
    validate_topics({'relevant':True,'confidence':p['confidence'],'topics':p['topics'],'topic_evidence':p['topic_evidence']},p['full_text'])
    assert p['conference_year'] in (2025,2026)
    ready.append(p)
ready=merge_records(ready)
for p in ready:
    assert p['status']=='ready', 'Dedup invalidated summary cache; resolve before publishing'
stamp=datetime.now(timezone.utc).isoformat()
with lock(root/'data/pipeline.lock'):
    archive=read_json(root/'data/papers.json',{})
    backup=folder/'archive-before-audit.json'
    if not backup.exists():write_json(backup,archive)
    original=read_json(backup,{})['papers'];original_keys=set().union(*(identity_keys(p) for p in original))
    ready_keys=set().union(*(identity_keys(p) for p in ready))
    removed=[p for p in archive['papers'] if identity_keys(p)&excluded_keys and not identity_keys(p)&(original_keys|ready_keys)]
    current=[p for p in archive['papers'] if p not in removed];new=[]
    seen=set(original_keys)
    for p in ready:
        if not identity_keys(p)&seen:new.append(p)
        seen.update(identity_keys(p))
    merged=merge_records(current+ready)
    # Do not publish metadata-only or invalid summaries from this audit.
    assert len({p['id'] for p in merged})==len(merged)
    archive['papers']=merged;write_json(root/'data/papers.json',archive)
    report={'started_at':read_json(root/'data/literature_candidates.json',{}).get('snapshot_at'),
            'updated_at':stamp,'in_progress':'--final' not in sys.argv,'llm_enabled':True,
            'mode':'latest_edition_catalogue_audit','coverage_complete':False,
            'new_ready_papers':len(new),'verified_audit_papers':len(ready),
            'withdrawn_audit_checkpoint_titles':[p['title'] for p in removed],
            'status_counts':dict(collections.Counter(x['status'] for x in outcomes)),
            'latest_editions':{**latest,'log':None},
            'scope':'latest publicly verifiable edition per conference; EMNLP 2026 main program; LoG latest edition unresolved',
            'venue_counts':dict(collections.Counter(f"{p['conference_year']} {p['venue_label']}" for p in new)),
            'skipped_previous_editions':skipped,'sources':{},'outcomes':outcomes}
    write_json(root/'data/literature_audit_report.json',report)
    write_json(root/'data/literature_audit_results.json',{'updated_at':stamp,'returned':len(new),'results':[{k:p.get(k) for k in ('id','title','venue_label','conference_year','topics','method','pdf_url')} for p in new]})
    public_report={k:v for k,v in report.items() if k not in ('outcomes','skipped_previous_editions')}
    export_site(merged,public_report,root/'site')
    print(json.dumps({'new':len(new),'site_papers':sum(p.get('status')!='irrelevant' for p in merged),'status_counts':report['status_counts']},ensure_ascii=False))
