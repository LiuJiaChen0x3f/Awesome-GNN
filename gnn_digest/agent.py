"""Bounded Responses web-search loop with independent primary-source verification."""
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from .http import RequestError, get_json
from .llm import Summarizer
from .models import content_hash, identity_keys, merge_records
from .storage import export_site, lock, read_json, write_json
from .verification import DOMAINS, TOPICS, VENUES, VerificationError, canonical_url, verify_candidate


def endpoint(base, suffix):
    base = base.rstrip('/')
    for tail in ('/chat/completions', '/responses'):
        if base.endswith(tail):
            base = base[:-len(tail)]
            break
    return base + suffix


def parse_candidates(text, limit):
    text = text.strip()
    if text.startswith('```') and text.endswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    value = json.loads(text)
    if not isinstance(value, dict) or not isinstance(value.get('candidates'), list):
        raise ValueError('Expected a JSON candidates list')
    if len(value['candidates']) > limit:
        raise ValueError('Too many candidates')
    for item in value['candidates']:
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip() for k in ('title', 'url')):
            raise ValueError('Candidate needs title and url')
    return value['candidates'], str(value.get('notes', ''))[:1000]


def validate_topics(result, abstract):
    topics, evidence = result.get('topics'), result.get('topic_evidence')
    if not isinstance(topics, list) or not isinstance(evidence, dict):
        raise ValueError('topics and topic_evidence required')
    if not result['relevant'] or result['confidence'] == 'low':
        if topics or evidence:
            raise ValueError('No topics for irrelevant/insufficient result')
    elif (not topics or any(t not in TOPICS for t in topics) or len(set(topics)) != len(topics)
          or set(evidence) != set(topics)
          or any(not isinstance(s, str) or not 15 <= len(s) <= 200 or s not in abstract for s in evidence.values())):
        raise ValueError('Need allowed topics with verbatim abstract evidence')
    return result


def cited_candidates(citations, limit):
    """Recover only cited primary pages; these still require independent verification."""
    result, seen = [], set()
    for citation in citations:
        try:
            url = canonical_url(citation.get('url'))
        except (TypeError, ValueError):
            continue
        title = re.sub(r'^\[\d{4}\.\d{4,5}(?:v\d+)?\]\s*', '', citation.get('title') or '').strip()
        if title and url not in seen:
            seen.add(url)
            result.append({'title':title, 'url':url})
        if len(result) >= limit:
            break
    return result


def trace_response(response):
    actions, citations, messages = [], [], []
    for item in response.get('output', []):
        if item.get('type') == 'web_search_call':
            action = item.get('action') or {}
            actions.append({'status':item.get('status'), **{k:action[k] for k in ('type','query','queries','url') if k in action}})
        if item.get('type') == 'message':
            texts = []
            for block in item.get('content', []):
                if block.get('type') == 'output_text':
                    texts.append(block.get('text', ''))
                    citations.extend({'url':a.get('url'), 'title':a.get('title')} for a in block.get('annotations', []) if a.get('type') == 'url_citation')
            if texts:
                messages.append('\n'.join(texts))
    # Intermediate commentary may coexist with a valid final JSON message.
    return messages[-1] if messages else '', actions, citations


class WebResearchAgent:
    def __init__(self, llm, options, prompt):
        self.llm, self.options, self.prompt = llm, options, prompt
        self.key, self.model = os.getenv('LLM_API_KEY', ''), os.getenv('LLM_MODEL', '')
        base = os.getenv('LLM_BASE_URL', '')
        if not all((base, self.key, self.model)):
            raise ValueError('Set local LLM_BASE_URL, LLM_API_KEY and LLM_MODEL')
        parsed = urlparse(base)
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost','127.0.0.1','::1')):
            raise ValueError('LLM endpoint must use HTTPS')
        self.url = endpoint(base, '/responses')

    def search(self, context, timeout):
        payload = {'model':self.model, 'instructions':self.prompt,
                   'input':json.dumps(context, ensure_ascii=False),
                   'tools':[{'type':'web_search'}], 'tool_choice':'required',
                   'max_output_tokens':self.options['max_output_tokens'], 'store':False}
        # Some compatible providers reject this official optional parameter.
        # Keep the per-request call target in the prompt and enforce outer budgets locally.
        if self.options.get('send_max_tool_calls', False):
            payload['max_tool_calls'] = self.options['max_tool_calls_per_round']
        payload['instructions'] += f'\nUse at most {self.options["max_tool_calls_per_round"]} web tool calls in this request.'
        effort = os.getenv('LLM_REASONING_EFFORT') or self.llm.get('reasoning_effort')
        if effort:
            payload['reasoning'] = {'effort':effort}
        # No automatic repeat of a paid search request on timeout.
        return get_json(self.url, payload=payload, headers={'Authorization':'Bearer ' + self.key}, timeout=timeout, attempts=1)


def validate_options(options):
    bounds = {'max_rounds':(1,5), 'max_tool_calls_per_round':(1,30),
              'max_output_tokens':(1000,16000), 'candidate_limit':(3,30),
              'timeout':(10,300), 'max_seconds':(30,1800), 'max_summary_papers':(1,50)}
    for key, (lo, hi) in bounds.items():
        if type(options.get(key)) is not int or not lo <= options[key] <= hi:
            raise ValueError(f'search_agent.{key} must be an integer in {lo}..{hi}')


def search(root, config, args):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if args.no_llm:
        raise ValueError('search requires a web-search-capable LLM; use run --no-llm for legacy metadata collection')
    limit = getattr(args, 'limit', 5)
    if not 1 <= limit <= 20:
        raise ValueError('search --limit must be 1..20')
    options = dict(max_rounds=3, max_tool_calls_per_round=12, max_output_tokens=6000,
                   candidate_limit=10, timeout=180, max_seconds=600, max_summary_papers=10)
    options.update(config.get('search_agent', {}))
    validate_options(options)
    today = date.fromisoformat(args.until) if args.until else datetime.now(timezone.utc).date()
    days = args.days if args.days is not None else config['days']
    if days < 1:
        raise ValueError('days must be positive')
    since = today - timedelta(days=days-1)
    request = (root/'prompts/search.request.txt').read_text(encoding='utf-8').strip()
    if not request:
        raise ValueError('Fixed search request is empty')
    agent = WebResearchAgent(config['llm'], options, (root/'prompts/search.agent.txt').read_text(encoding='utf-8'))
    summary_prompt = (root/'prompts/search.summary.zh.txt').read_text(encoding='utf-8')
    summary_prompt += '\n研究需求（仅用于主题相关性判断）：\n' + request
    summarizer = Summarizer(config['llm'], summary_prompt, extra_validator=validate_topics)
    start = time.monotonic()
    deadline = start + options['max_seconds']
    report = {'mode':'responses_web_search', 'started_at':datetime.now(timezone.utc).isoformat(),
              'window':{'since':str(since), 'until':str(today)}, 'llm_enabled':True,
              'requested':limit, 'rounds':[], 'sources':{}, 'rejections':[],
              'request_hash':hashlib.sha256(request.encode()).hexdigest(), 'llm_processed':0,
              'coverage':'Best effort within time/tool budgets; not an exhaustive newest-paper ranking.'}
    with lock(root/'data/pipeline.lock'):
        archive = read_json(root/'data/papers.json', {'schema_version':1, 'papers':[]})['papers']
        accepted, seen, feedback = [], set(), []
        summary_budget = max(limit, options['max_summary_papers'])
        for round_number in range(1, options['max_rounds']+1):
            if time.monotonic() >= deadline:
                break
            print(f'Web research round {round_number}/{options["max_rounds"]}: {len(accepted)}/{limit} verified results', flush=True)
            context = {'research_request':request, 'utc_today':str(today),
                       'date_window':report['window'], 'requested_count':limit,
                       'candidate_limit':options['candidate_limit'], 'primary_source_domains':DOMAINS,
                       'conference_aliases':VENUES, 'accepted':[{'title':p['title'], 'url':p['verification']['url']} for p in accepted],
                       'feedback':feedback[-30:], 'instruction':'Search for additional eligible papers; prioritize newest dates. Do not return accepted or rejected URLs again.'}
            record = {'round':round_number}
            try:
                response = agent.search(context, min(options['timeout'], max(1, deadline-time.monotonic())))
                text, actions, citations = trace_response(response)
                record.update(status=response.get('status'), actions=actions, citations=citations,
                              usage={k:v for k,v in response.get('usage',{}).items() if k in ('input_tokens','output_tokens','total_tokens')})
                if response.get('status') != 'completed':
                    raise ValueError('Responses output incomplete; no candidates admitted')
                if not any(a.get('status') == 'completed' for a in actions):
                    raise ValueError('No completed web_search call; answer is not verified live search')
                try:
                    candidates, notes = parse_candidates(text, options['candidate_limit'])
                except (ValueError, TypeError):
                    candidates = cited_candidates(citations, options['candidate_limit'])
                    if not candidates:
                        raise ValueError('No valid candidates JSON or primary-source citations') from None
                    notes = 'Recovered candidates from response citations; all require primary-source verification.'
                    record['format_recovery'] = 'url_citations'
                record.update(candidate_count=len(candidates), notes=notes)
            except Exception as exc:
                record['error'] = str(exc)[:200] if type(exc) is ValueError or isinstance(exc, RequestError) else type(exc).__name__
                report['rounds'].append(record)
                write_json(root/'data/last_run.json', report)
                feedback.append({'reason':record['error'], 'action':'Correct output or search again with actual tools.'})
                print(f'Round {round_number} did not yield valid candidates: {type(exc).__name__}', flush=True)
                if isinstance(exc, RequestError):
                    # Configuration errors/timeouts must not multiply paid requests.
                    break
                continue
            report['rounds'].append(record)
            write_json(root/'data/last_run.json', report)
            verified = []
            for c in candidates:
                if time.monotonic() >= deadline:
                    break
                try:
                    url = canonical_url(c['url'])
                    if url in seen:
                        continue
                    seen.add(url)
                    p = verify_candidate(c, since, today, timeout=min(25, max(1, deadline-time.monotonic())))
                    verified.append(p)
                except Exception as exc:
                    reason = str(exc)[:200] if isinstance(exc, VerificationError) else type(exc).__name__
                    item = {'url':c['url'], 'title':c['title'][:300], 'reason':reason}
                    feedback.append(item)
                    report['rejections'].append(item)
            verified = merge_records(verified)
            verified.sort(key=lambda p:p.get('display_date',p['published']), reverse=True)
            for p in verified:
                if len(accepted) >= limit or time.monotonic() >= deadline:
                    break
                if any(identity_keys(p) & identity_keys(a) for a in accepted):
                    continue
                cached = next((a for a in archive if identity_keys(p) & identity_keys(a)
                               and content_hash(a) == content_hash(p) and summarizer.cached(a)
                               and a.get('topics') and a.get('topic_evidence')), None)
                if cached:
                    for field in ('keywords','method','confidence','evidence','summary_input_hash','prompt_hash','llm_model','llm_reasoning_effort','summarized_at','topics','topic_evidence','status'):
                        if field in cached:
                            p[field] = cached[field]
                elif report['llm_processed'] < summary_budget:
                    summarizer.config = {**config['llm'], 'timeout':min(config['llm']['timeout'], max(1, deadline-time.monotonic())), 'attempts':1}
                    summarizer.summarize(p)
                    report['llm_processed'] += 1
                else:
                    break
                if p['status'] == 'ready' and p.get('topics'):
                    accepted.append(p)
                    print(f'Accepted {len(accepted)}/{limit}: {p["published"]} | {p["venue_label"]} | {p["title"]}', flush=True)
                    write_json(root/'data/papers.json', {'schema_version':1, 'papers':merge_records(archive+accepted)})
                else:
                    item = {'url':p['verification']['url'], 'title':p['title'], 'reason':'Summary/topic validation: ' + p['status']}
                    feedback.append(item)
                    report['rejections'].append(item)
            if len(accepted) >= limit or report['llm_processed'] >= summary_budget:
                break
            feedback.append({'reason':f'Only {len(accepted)}/{limit} qualified results. Search alternative primary sources or shorter/broader topic phrasing, keeping the same dates and eligibility.'})
        papers = merge_records(archive + accepted) if accepted else archive
        results = []
        for p in accepted:
            persisted = next((a for a in papers if identity_keys(a) & identity_keys(p)), None)
            if persisted:
                # Preserve archive IDs but keep this run's verified date/text, even on a historic --until.
                results.append({**p, 'id':persisted['id']})
        results.sort(key=lambda p:p.get('display_date', p['published']), reverse=True)
        report.update(finished_at=datetime.now(timezone.utc).isoformat(), returned=len(results),
                      total=len(papers), statuses=dict(Counter(p['status'] for p in papers)),
                      result_ids=[p['id'] for p in results], deduplicated=len(archive)+len(accepted)-len(papers),
                      elapsed_seconds=round(time.monotonic()-start,2), shortfall=max(0, limit-len(results)))
        ok = any(any(a.get('status')=='completed' for a in r.get('actions',[])) for r in report['rounds'])
        report['sources']['web_search'] = {'ok':ok, 'mode':'responses', 'verified':len(results), 'truncated':len(results)<limit}
        if not ok:
            report['error'] = 'No completed live web search; archive preserved'
        report['stop_reason'] = ('target_reached' if len(results)>=limit else 'time_budget' if time.monotonic()>=deadline else 'summary_budget' if report['llm_processed']>=summary_budget else 'round_budget')
        if accepted:
            write_json(root/'data/papers.json', {'schema_version':1, 'papers':papers})
        write_json(root/'data/last_run.json', report)
        write_json(root/'data/search_results.json', {'report':report, 'papers':results})
        export_site(papers, report, root/'site')
        print(json.dumps({'returned':len(results), 'requested':limit, 'stop_reason':report['stop_reason'],
                          'results':[{'title':p['title'],'date':p.get('display_date',p['published']), 'venue':p.get('venue_label'), 'topics':p.get('topics'), 'keywords':p['keywords'], 'method':p['method'], 'url':p.get('pdf_url') or p['verification']['url']} for p in results]}, ensure_ascii=False, indent=2), flush=True)
        return 0 if len(results)>=limit else 4 if ok else 2
