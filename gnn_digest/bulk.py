"""Finite venue/year sweep, with arXiv shortfalls transferred to conferences."""
import copy
import time
from collections import Counter
from datetime import datetime, timezone

from .models import identity_keys
from .storage import export_site, lock, read_json, write_json
from .verification import VENUES


def bulk_targets(limit, arxiv_returned=None):
    arxiv = limit // 5
    if arxiv_returned is not None:
        arxiv = min(arxiv, arxiv_returned)
    return {'conference':limit-arxiv, 'arxiv':arxiv}


def conference_schedule(years):
    # Keep IJCAI in the same sweep as every other enabled conference.
    return [{'bucket':'conference', 'venue':venue, 'year':year}
            for year in years for venue in VENUES
            if not (venue == 'ICCV' and year % 2 == 0)]


def bulk_search(root, config, args):
    from .agent import search, source_windows, quota_progress
    from datetime import date
    limit = args.limit
    if not 1 <= limit <= 100:
        raise ValueError('search --limit must be 1..100')
    opts = {**{'conference_years':[2026,2025], 'batch_limit':12, 'arxiv_rounds':4,
               'conference_passes':2, 'max_seconds':7200, 'max_summary_papers':240},
            **config.get('bulk_search', {})}
    today = date.fromisoformat(args.until) if args.until else datetime.now(timezone.utc).date()
    windows = source_windows(config, args, today)
    initial_targets = bulk_targets(limit)
    targets = dict(initial_targets)
    started, accepted, used, rounds = time.monotonic(), [], set(), []
    report = {'mode':'venue_year_sweep', 'started_at':datetime.now(timezone.utc).isoformat(),
              'requested':limit, 'active_topics':['TAG','OOD'], 'source_windows':windows,
              'initial_source_quotas':initial_targets, 'source_quotas':targets,
              'fallback_policy':'Transfer unfilled arXiv slots to conferences after bounded arXiv discovery.',
              'rounds':rounds, 'llm_processed':0, 'sources':{}, 'rejections':[],
              'coverage':'Finite searches per eligible venue and edition; not proof of exhaustive coverage.'}
    halt = None

    if getattr(args,'resume',False):
        previous=read_json(root/'data/bulk_run.json',{})
        saved=read_json(root/'data/search_results.json',{})
        if previous.get('requested')!=limit or previous.get('source_windows')!=windows:
            raise ValueError('Bulk checkpoint does not match requested count/date windows')
        accepted=saved.get('papers',[])
        if set(previous.get('result_ids',[]))!={p['id'] for p in accepted}:
            raise ValueError('Bulk result checkpoint is inconsistent; inspect before resuming')
        report=previous
        report.pop('finished_at',None);report.pop('stop_reason',None)
        report['resumed_at']=datetime.now(timezone.utc).isoformat()
        rounds=report['rounds'];targets=dict(report['source_quotas'])
        report['source_quotas']=targets
        used={key for p in accepted for key in (identity_keys(p)|{'archive_id:'+p['id']})}
        started-=report.get('elapsed_seconds',0)

    def checkpoint(final=False):
        archive = read_json(root/'data/papers.json', {'papers':[]})['papers']
        report.update(returned=len(accepted), shortfall=max(0,limit-len(accepted)),
                      updated_at=datetime.now(timezone.utc).isoformat(), in_progress=not final, llm_enabled=True,
                      quota_progress=quota_progress(accepted,targets),
                      total=len(archive), statuses=dict(Counter(p['status'] for p in archive)),
                      elapsed_seconds=round(time.monotonic()-started,2),
                      result_ids=[p['id'] for p in accepted])
        report['sources']['web_search'] = {'ok':any(r.get('live_search_completed') for r in rounds),
            'mode':'venue_year_sweep', 'verified':len(accepted), 'truncated':len(accepted)<limit}
        if final:
            report['finished_at'] = datetime.now(timezone.utc).isoformat()
        write_json(root/'data/bulk_run.json', report)
        write_json(root/'data/last_run.json', report)
        write_json(root/'data/search_results.json', {'report':report,'papers':accepted})
        export_site(archive, report, root/'site')

    def run_batch(scope, remaining, pass_number):
        nonlocal halt
        if any(r['scope']==scope and r.get('pass')==pass_number and r.get('live_search_completed')
               and not r.get('retry_requested') for r in rounds):
            return
        elapsed = time.monotonic()-started
        if elapsed >= opts['max_seconds']:
            halt = 'time_budget'; return
        budget = opts['max_summary_papers']-report['llm_processed']
        if budget <= 0 and remaining > 0:
            halt = 'summary_budget'; return
        count = max(1,min(opts['batch_limit'],remaining,20))
        recent=[r for r in rounds if r['scope']==scope]
        network_retry=bool(recent and not recent[-1].get('live_search_completed') and
                           any('timeout' in str(r.get('error','')).lower() or 'network' in str(r.get('error','')).lower()
                               for r in recent[-1].get('rounds',[])))
        if network_retry:
            count=min(count,4)
        child = copy.deepcopy(config)
        child['_bulk_child'], child['_lock_held'] = True, True
        child['_discovery_only'] = remaining <= 0
        child['_source_quotas'] = {b:count if b == scope['bucket'] else 0 for b in targets}
        child['_search_scope'] = {**scope, 'pass':pass_number,
            'instruction':'Search only this bucket, venue and conference edition. Check whether its proceedings are published. Discover TAG/OOD papers broadly, excluding the supplied titles; do not substitute IJCAI or another venue. If unavailable or no additional eligible titles are found, return empty and explain. Exact title matching arXiv fulltext_url can supply a PDF for a separately verified conference record.'}
        child['_exclude_titles'] = [p['title'] for p in accepted]
        child['_prior_feedback'] = [item for r in rounds if r['scope']==scope and not r.get('retry_requested')
                                    for item in r.get('rejections',[])][-30:]
        child['search_agent'].update(max_rounds=1, candidate_limit=20, max_tool_calls_per_round=8,
            max_output_tokens=6000, max_seconds=max(30,min(900,int(opts['max_seconds']-elapsed))),
            max_summary_papers=max(1,min(30,budget)))
        if network_retry:
            child['search_agent'].update(candidate_limit=8,max_tool_calls_per_round=4,max_output_tokens=4000)
        child_args = copy.copy(args); child_args.limit = count; child_args.until = str(today)
        print(f"Bulk batch {len(rounds)+1}: {scope} | accepted {len(accepted)}/{limit}", flush=True)
        code = search(root,child,child_args)
        batch = read_json(root/'data/search_results.json', {})
        child_report = batch.get('report',{})
        additions = []
        for p in batch.get('papers',[]):
            keys = identity_keys(p)|{'archive_id:'+p['id']}
            if keys & used:
                continue
            used.update(keys); accepted.append(p); additions.append(p['id'])
        report['llm_processed'] += child_report.get('llm_processed',0)
        live = child_report.get('sources',{}).get('web_search',{}).get('ok',False)
        rounds.append({'scope':scope, 'pass':pass_number,'exit_code':code,
            'discovery_only':remaining<=0,
            'returned':len(additions), 'result_ids':additions,'live_search_completed':live,
            'elapsed_seconds':child_report.get('elapsed_seconds'),
            'rounds':child_report.get('rounds',[]), 'rejections':child_report.get('rejections',[])})
        report['rejections'].extend(child_report.get('rejections',[]))
        checkpoint()
        # Auth/config/provider outages should not trigger dozens of paid retries.
        if code == 2 and any('RequestError' in str(r.get('error','')) or 'HTTP' in str(r.get('error',''))
                             or 'timeout' in str(r.get('error','')).lower() for r in child_report.get('rounds',[])):
            halt = 'provider_error'

    with lock(root/'data/pipeline.lock'):
        checkpoint()
        for attempt in range(opts['arxiv_rounds']):
            count = sum(p['selection_bucket']=='arxiv' for p in accepted)
            if count >= initial_targets['arxiv'] or halt:
                break
            run_batch({'bucket':'arxiv','year':2026, 'topic_focus':'TAG' if attempt%2 == 0 else 'OOD'},
                      initial_targets['arxiv']-count,attempt+1)
        arxiv_count = sum(p['selection_bucket']=='arxiv' for p in accepted)
        targets.update(bulk_targets(limit,arxiv_count))
        report['arxiv_shortfall_transferred'] = initial_targets['arxiv']-arxiv_count
        schedule = conference_schedule(opts['conference_years'])
        report['planned_conference_scopes'] = schedule
        for pass_number in range(1, opts['conference_passes']+1):
            before_pass = len(accepted)
            for scope in schedule:
                if halt:
                    break
                remaining = limit-len(accepted)
                if remaining <= 0 and pass_number > 1:
                    break
                allocation=remaining
                if pass_number==1 and remaining>0:
                    pending=sum(not any(r['scope']==s and r.get('pass')==1 and
                                r.get('live_search_completed') and not r.get('retry_requested')
                                for r in rounds) for s in schedule)
                    # Reserve opportunities for later venues instead of
                    # filling all slots from whichever publisher comes first.
                    allocation=min(remaining,max(3,(remaining+max(1,pending)-1)//max(1,pending)))
                run_batch(scope,allocation,pass_number)
            if halt or len(accepted)>=limit:
                break
            # A resumed pass may skip all earlier successful batches. Judge
            # progress across the whole recorded pass, not this process only.
            if not any(r.get('returned',0) for r in rounds if r['scope']['bucket']=='conference' and r.get('pass')==pass_number):
                break
        visited = {(r['scope'].get('venue'),r['scope'].get('year')) for r in rounds if r['scope']['bucket']=='conference'}
        report['unvisited_conference_scopes'] = [s for s in schedule if (s['venue'],s['year']) not in visited]
        report['stop_reason'] = ('target_reached' if len(accepted)>=limit else halt or 'coverage_sweep_complete')
        accepted.sort(key=lambda p:p.get('display_date',p['published']),reverse=True)
        checkpoint(final=True)
        print(f"Bulk finished: {len(accepted)}/{limit}; conference {sum(p['selection_bucket']=='conference' for p in accepted)}, arxiv {arxiv_count}; {report['stop_reason']}",flush=True)
    return 0 if len(accepted)>=limit else 4
