import concurrent.futures,copy,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from gnn_digest.cli import load_env
from gnn_digest.llm import Summarizer,validate_summary
from gnn_digest.agent import validate_topics
from gnn_digest.evidence import fulltext_segments,resolve_evidence_ids
from gnn_digest.models import content_hash
from gnn_digest.http import get_json
from gnn_digest.storage import read_json,write_json
load_env(root/'.env');folder=root/'.local/literature-audit'
cfg=read_json(root/'config.json',{})['llm'];prompt=(root/'prompts/search.summary.zh.txt').read_text(encoding='utf-8')
engine=Summarizer({**cfg,'require_fulltext':True,'evidence_mode':'segments','attempts':2,'timeout':120},prompt,extra_validator=validate_topics)
def run(batch):
    docs=[];lookup={}
    for path,p,outcome in batch:
        segments=fulltext_segments(p['full_text']);key=path.stem
        lookup[key]=(path,p,outcome,segments)
        docs.append({'id':key,'title':p['title'],'full_text_segments':[{'id':s['id'],'text':s['text']} for s in segments]})
    batch_prompt=prompt+'\n本次是独立论文批次，每篇全文与编号各自隔离，不能跨论文引用。将每篇上述JSON放入papers数组并附上该论文的id。顶层仅输出 {"papers":[{"id":"输入id",...单篇字段...}]}，对每篇都必须作出判断，不可遗漏。'
    payload={'model':engine.model,'messages':[{'role':'system','content':batch_prompt},{'role':'user','content':json.dumps({'papers':docs},ensure_ascii=False)}],'response_format':{'type':'json_object'},'max_completion_tokens':6500,'reasoning_effort':engine.reasoning_effort}
    try:
        r=get_json(engine.endpoint,payload=payload,headers={'Authorization':'Bearer '+engine.key},timeout=100,attempts=1)
        values=json.loads(r['choices'][0]['message']['content'])['papers']
        if len(values)!=len(batch) or {v.get('id') for v in values}!=set(lookup):raise ValueError('missing or duplicate paper ids')
        for v in values:
            path,p,outcome,segments=lookup[v['id']]
            try:
                result=validate_topics(validate_summary(resolve_evidence_ids(v,segments),p['full_text']),p['full_text'])
                p.update({k:result[k] for k in ('keywords','method','confidence','evidence','topics','topic_evidence')})
                for k in ('evidence_locations','topic_evidence_locations'):p[k]=result.get(k,{} if k.startswith('topic') else [])
                p.update(status='irrelevant' if not result['relevant'] else 'insufficient' if result['confidence']=='low' else 'ready',summary_input_hash=content_hash(p),prompt_hash=engine.prompt_hash,llm_model=engine.model,llm_reasoning_effort=engine.reasoning_effort,summarized_at=datetime.now(timezone.utc).isoformat(),validation_errors=[])
                outcome.update(status=p['status'],topics=p['topics'],summary_mode='independent_fulltext_batch')
                outcome.pop('error', None)
                write_json(path,p);write_json(folder/'outcomes'/path.name,outcome)
                print(p['status'],p['venue_label'],p['title'],flush=True)
            except Exception as e:
                outcome.update(status='summary_validation_failed',error=str(e)[:240]);write_json(folder/'outcomes'/path.name,outcome)
                write_json(folder/'invalid-summaries'/path.name,{'result':v,'error':str(e)[:240]})
                print('validation_failed',p['title'],type(e).__name__,flush=True)
    except Exception as e:
        for path,p,outcome in batch:
            outcome.update(status='summary_request_failed',error=str(e)[:240]);write_json(folder/'outcomes'/path.name,outcome)
        print('batch_request_failed',len(batch),type(e).__name__,flush=True)
        return False
    return True


def main():
    import argparse
    from gnn_digest.storage import lock
    parser=argparse.ArgumentParser(description="Resume cached complete-text summaries; never rediscover papers.")
    parser.add_argument('--limit',type=int,default=150)
    parser.add_argument('--retry-failed',action='store_true')
    parser.add_argument('--workers',type=int,choices=(1,2),default=2)
    args=parser.parse_args()
    statuses={'fulltext_prepared'}
    if args.retry_failed:statuses.add('summary_request_failed')
    with lock(folder/'summary-recovery.lock'):
        items=[]
        for path in (folder/'papers').glob('*.json'):
            outcome=read_json(folder/'outcomes'/path.name,{})
            if outcome.get('status') not in statuses:continue
            p=read_json(path,{})
            if p.get('venue_label')=='EMNLP' and p.get('conference_year')!=2026:continue
            if p.get('venue_label')=='LoG':continue
            if not p.get('full_text') or p.get('fulltext_source',{}).get('scope')!='full_text':continue
            items.append((path,p,outcome))
        # Explicit topic candidates first, then shorter complete texts. Never truncate.
        import re
        items.sort(key=lambda x:(not bool(re.search(r'text.attributed|out.of.distribution|domain|distribution shift|test.time|graph.*language',x[1]['title'],re.I)),len(x[1]['full_text'])))
        items=items[:args.limit];batches=[];batch=[];chars=0
        for item in items:
            n=len(item[1]['full_text'])
            if batch and (len(batch)>=2 or chars+n>160000):batches.append(batch);batch=[];chars=0
            batch.append(item);chars+=n
        if batch:batches.append(batch)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        history=folder/'retry-history'/stamp
        for path,p,outcome in items:write_json(history/path.name,outcome)
        print('recovery',len(items),'papers',len(batches),'batches',flush=True)
        # Submit one worker-sized wave at a time so a broken network cannot
        # consume every queued item. Stop after three failed requests in a row.
        failed=0;processed=0;halted=False
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            for start in range(0,len(batches),args.workers):
                wave=batches[start:start+args.workers]
                for ok in ex.map(run,wave):
                    processed+=1;failed=0 if ok else failed+1
                if failed>=3:
                    halted=True;print('circuit_breaker: consecutive request failures',flush=True);break
        write_json(folder/'summary-recovery-report.json',{'at':stamp,'selected_papers':len(items),'total_batches':len(batches),'processed_batches':processed,'stopped_on_request_failures':halted})

if __name__=='__main__':main()
