"""Bounded Responses web-search loop with independent primary-source verification."""
import hashlib
import json
import os
import re
import sys
import time
from contextlib import nullcontext
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse
import xml.etree.ElementTree as ET

from .http import RequestError, get_json, request
from .llm import Summarizer
from .evidence import locate_evidence
from .models import arxiv_id, clean, content_hash, identity_keys, merge_records, paper
from .storage import export_site, lock, read_json, write_json
from .verification import DOMAINS, TOPICS, VENUES, DIRECTORY_SOURCES, VerificationError, canonical_url, verify_candidate, verify_directory_match
from .fulltext import load_fulltext, coerce_legacy_fulltext

# Compatibility patch point; the implementation now always reads full text.
load_methods = load_fulltext


def endpoint(base, suffix):
    base = base.rstrip('/')
    for tail in ('/chat/completions', '/responses'):
        if base.endswith(tail):
            base = base[:-len(tail)]
            break
    return base + suffix


def source_windows(config, args, today):
    """Specific CLI window > shared --days > per-source config > defaults."""
    configured = config.get('search_windows', {})
    windows = {}
    for bucket, default in (('conference', 90), ('arxiv', 14)):
        days = getattr(args, bucket+'_days', None)
        if days is None:
            days = getattr(args, 'days', None)
        if days is None:
            start = getattr(args, bucket+'_since', None) or configured.get(bucket+'_since')
            if start:
                start = date.fromisoformat(start)
                if start > today:
                    raise ValueError(f'{bucket}_since is after the cutoff')
                windows[bucket] = {'since':str(start), 'until':str(today), 'days':(today-start).days+1}
                continue
            days = configured.get(bucket+'_days', default)
        if type(days) is not int or not 1 <= days <= 3660:
            raise ValueError(f'{bucket}_days must be an integer in 1..3660')
        windows[bucket] = {'since':str(today-timedelta(days=days-1)), 'until':str(today), 'days':days}
    return windows


def recovery_feedback(stage, error):
    """Concrete next steps, without accepting model-supplied metadata as proof."""
    detail = str(error)
    lower = detail.casefold()
    if stage == 'fulltext' and ('exceeds' in lower or 'too large' in lower):
        code, action = 'fulltext_too_large', 'The available full text exceeds the configured processing limit. Seek an eligible different paper with obtainable full text; do not truncate silently or summarize only its abstract.'
    elif 'outside requested window' in lower:
        code, action = 'outside_window', 'Find a different paper within source_windows for that route; never replace publication with revision/acceptance dates.'
    elif re.search(r'\bdate\b|\bprecision\b', lower):
        code, action = 'missing_date', 'Open the official proceedings detail/BibTeX/DOI record to find a landing page with exact publication metadata. Do not invent dates.'
    elif 'conference' in lower or 'main track' in lower:
        code, action = 'missing_venue', 'Find an allowed main-proceedings detail page with track/venue metadata. An arXiv or directory mention cannot fill a conference slot.'
    elif 'title' in lower:
        code, action = 'title_mismatch', 'Open the primary page and copy its exact title before resubmitting the candidate.'
    elif any(s in lower for s in ('http', 'urlerror', 'ssl', 'timeout', 'connection', 'oserror')):
        code, action = 'source_unreachable', 'Use web open_page to inspect accessibility and search the exact title for an alternative allowed primary page; local verification is still required.'
    elif stage == 'fulltext':
        code, action = 'missing_fulltext', 'Search the exact title for an accessible official PDF or matching arXiv version; submit its primary landing page for verification. Do not summarize snippets.'
    else:
        code, action = 'validation_failed', 'Use the field-specific validation detail; find another eligible candidate if the paper cannot be verified.'
    return {'stage':stage, 'code':code, 'next_action':action,
            'retry_same_url':stage == 'metadata' and code in ('source_unreachable', 'title_mismatch')}


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
        if 'directory_url' in item and not isinstance(item['directory_url'], str):
            raise ValueError('directory_url must be a string')
    return value['candidates'], str(value.get('notes', ''))[:1000]


def validate_topics(result, full_text):
    topics, evidence = result.get('topics'), result.get('topic_evidence')
    if not isinstance(topics, list) or not isinstance(evidence, dict):
        raise ValueError('topics and topic_evidence required')
    if not result['relevant'] or result['confidence'] == 'low':
        if topics or evidence:
            raise ValueError('No topics for irrelevant/insufficient result')
    else:
        if not topics or any(t not in TOPICS for t in topics) or len(set(topics)) != len(topics):
            raise ValueError('topics: expected unique allowed topic names')
        if set(evidence) != set(topics):
            raise ValueError('topic_evidence: keys must match topics exactly')
        matches = {t:locate_evidence(evidence[t], full_text, f'topic_evidence.{t}') for t in topics}
        result = {**result, 'topic_evidence':{t:m[0] for t,m in matches.items()},
                  'topic_evidence_locations':{t:m[1] for t,m in matches.items()}}
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
        # Citation titles can include the publisher's page suffix; strip only
        # known suffixes on that publisher, then still require exact metadata match.
        host = urlparse(url).hostname
        suffixes = {'aclanthology.org': r'\s+-\s+ACL Anthology$',
                    'ijcai.org': r'\s+\|\s+IJCAI$'}
        pattern = suffixes.get(host.removeprefix('www.'))
        if pattern:
            title = re.sub(pattern, '', title, flags=re.I).strip()
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
        self.chat_url = endpoint(base, '/chat/completions')
        # DeepSeek currently exposes function calling but does not execute the
        # Responses ``web_search`` tool. Use the local scholarly search tool so
        # the model still chooses and iterates queries instead of using a fixed
        # query list. Other compatible providers keep the native Responses path.
        self.search_mode = 'function_tool' if parsed.hostname in ('api.deepseek.com', 'api.deepseek.com.cn') else 'responses_web_search'

    def _local_scholar_search(self, query, context):
        """Run one model-requested scholarly search and return safe leads.

        The returned metadata is only a lead. Every URL is independently
        fetched and verified by ``verify_candidate`` before admission.
        """
        query = re.sub(r'\s+', ' ', str(query)).strip()[:180]
        windows = context.get('source_windows') or {}
        window = windows.get('arxiv') or context.get('date_window') or {}
        since = date.fromisoformat(window['since'])
        until = date.fromisoformat(window['until'])
        conference_window = windows.get('conference') or window
        source_config = {
            'queries': [query],
            'max_per_source': max(10, min(40, self.options['candidate_limit'] * 3)),
            'arxiv_categories': ['cs.LG', 'cs.AI', 'cs.SI', 'stat.ML'],
        }
        leads, errors = [], []

        def html_arxiv_results(search_query):
            params = {'query': search_query, 'searchtype': 'all', 'abstracts': 'show',
                      'order': '-announced_date_first', 'size': 50}
            page = request('https://arxiv.org/search/?' + urlencode(params),
                           timeout=18, attempts=1).decode('utf-8', errors='replace')
            result = []
            for block in re.findall(r'<li[^>]+class=["\']arxiv-result["\'][^>]*>(.*?)</li>', page, re.I | re.S):
                match = re.search(r'href=["\'](?:https?://arxiv\.org)?/abs/([^?"\']+)', block, re.I)
                title_match = re.search(r'<p[^>]+class=["\']title\b[^"\']*["\'][^>]*>(.*?)</p>', block, re.I | re.S)
                if not match or not title_match:
                    continue
                aid = arxiv_id(match.group(1))
                if not aid:
                    continue
                submitted = re.search(r'Submitted\s+(\d{1,2}\s+[A-Za-z]+,?\s+\d{4})', clean(block), re.I)
                stamp = ''
                if submitted:
                    for fmt in ('%d %B %Y', '%d %b %Y', '%d %B, %Y', '%d %b, %Y'):
                        try:
                            stamp = datetime.strptime(submitted.group(1), fmt).date().isoformat(); break
                        except ValueError:
                            pass
                abstract_match = re.search(r'<span[^>]+class=["\'][^"\']*abstract-full[^"\']*["\'][^>]*>(.*?)</span>', block, re.I | re.S)
                result.append({'title': clean(title_match.group(1)),
                               'url': 'https://arxiv.org/abs/' + aid, 'source': 'arxiv',
                               'published': stamp, 'venue': '',
                               'abstract': clean(abstract_match.group(1) if abstract_match else '')[:1200]})
            return result

        # The regular batch adapters deliberately have generous retries and an
        # RSS fallback. A model tool call needs a short, single-attempt budget,
        # so use the same public APIs directly here.
        try:
            atom = {'a': 'http://www.w3.org/2005/Atom', 'x': 'http://arxiv.org/schemas/atom'}
            arxiv_query = ('all:"' + query.replace('"', '') + '" AND '
                           f'submittedDate:[{since:%Y%m%d}0000 TO {until:%Y%m%d}2359]')
            params = {'search_query': arxiv_query, 'start': 0,
                      'max_results': source_config['max_per_source'],
                      'sortBy': 'submittedDate', 'sortOrder': 'descending'}
            root = ET.fromstring(request('https://export.arxiv.org/api/query?' + urlencode(params),
                                         timeout=18, attempts=1))
            for entry in root.findall('a:entry', atom):
                raw_id = entry.findtext('a:id', '', atom)
                aid = arxiv_id(raw_id)
                if not aid:
                    continue
                leads.append({'title': clean(entry.findtext('a:title', '', atom)),
                              'url': 'https://arxiv.org/abs/' + aid, 'source': 'arxiv',
                              'published': entry.findtext('a:published', '', atom)[:10],
                              'venue': '',
                              'abstract': clean(entry.findtext('a:summary', '', atom))[:1200]})
        except Exception as exc:
            # The export API can return 406 from some network egresses. The
            # public HTML search is a bounded equivalent and does not require
            # a separate credential.
            try:
                leads.extend(html_arxiv_results(query))
            except Exception as html_exc:
                errors.append('arxiv:' + type(exc).__name__ + '/' + type(html_exc).__name__)
        if not any(p.get('source') == 'arxiv' for p in leads):
            # Natural-language tool queries often include venue/date words that
            # are useful to the model but too restrictive for arXiv's search
            # parser. Retry once with those routing words removed.
            stopwords = {'arxiv', 'site', 'accepted', 'papers', 'paper', 'new',
                         'submission', 'submissions', 'recent', 'latest',
                         'september', 'october', 'november', 'december',
                         'january', 'february', 'march', 'april', 'may',
                         'june', 'july', 'august', '2025', '2026'}
            terms = [w for w in re.findall(r'[A-Za-z][A-Za-z-]*', query)
                     if w.casefold() not in stopwords and len(w) > 2]
            fallback_query = ' '.join(terms) or 'graph neural network'
            try:
                leads.extend(html_arxiv_results(fallback_query))
            except Exception as exc:
                errors.append('arxiv_fallback:' + type(exc).__name__)
        try:
            filters = f'from-pub-date:{conference_window["since"]},until-pub-date:{conference_window["until"]}'
            params = {'query': query, 'filter': filters, 'sort': 'published',
                      'order': 'desc', 'rows': source_config['max_per_source']}
            data = get_json('https://api.crossref.org/works?' + urlencode(params),
                            timeout=18, attempts=1).get('message', {})
            for item in data.get('items', []):
                parts = item.get('published', {}).get('date-parts', [[]])[0]
                stamp = '-'.join(str(x).zfill(4 if i == 0 else 2)
                                 for i, x in enumerate((parts + [1, 1])[:3])) if parts else ''
                landing = ((item.get('resource') or {}).get('primary') or {}).get('URL') or item.get('URL')
                links = item.get('link') or []
                html_link = next((link.get('URL') for link in links
                                  if isinstance(link, dict) and link.get('URL') and
                                  'pdf' not in link.get('content-type', '').casefold()), None)
                if landing and landing.startswith('https://doi.org/') and html_link:
                    landing = html_link
                landing = landing or ('https://doi.org/' + item['DOI'] if item.get('DOI') else '')
                leads.append({'title': clean(' '.join(item.get('title', []))),
                              'url': landing, 'source': 'crossref', 'published': stamp,
                              'venue': clean(' '.join(item.get('container-title', []))),
                              'abstract': clean(item.get('abstract', ''))[:1200]})
        except Exception as exc:
            errors.append('crossref:' + type(exc).__name__)
        for paper_record in leads:
            if not paper_record.get('title'):
                continue
            try:
                url = canonical_url(paper_record.get('url', ''))
            except (TypeError, ValueError):
                continue
            paper_record['url'] = url
            # Keep only the fields the model needs to rank a lead.
            paper_record['abstract'] = paper_record.get('abstract', '')[:1200]
        leads = [paper_record for paper_record in leads if paper_record.get('url')]
        # Preserve source diversity and remove exact duplicate URLs before the
        # model sees the tool result.
        unique, seen = [], set()
        for lead in leads:
            if lead['url'] in seen:
                continue
            seen.add(lead['url']); unique.append(lead)
        # Interleave the two indexes so an arXiv-heavy result page cannot hide
        # the conference leads needed by the outer 1:1 quota.
        buckets = {name: [p for p in unique if p.get('source') == name]
                   for name in ('crossref', 'arxiv')}
        mixed = []
        for index in range(self.options['candidate_limit']):
            for name in ('crossref', 'arxiv'):
                if index < len(buckets[name]):
                    mixed.append(buckets[name][index])
        mixed.extend(p for p in unique if p not in mixed)
        # Tool results are discovery hints, not the evidence used for the
        # final card. Keep them deliberately small so several sequential
        # function calls cannot exceed the provider context window. The
        # verifier below fetches the complete primary page again.
        tool_limit = min(8, max(4, self.options['candidate_limit'] // 2 + 2))
        compact = []
        for lead in mixed[:tool_limit]:
            compact.append({
                'title': lead.get('title', ''),
                'url': lead.get('url', ''),
                'source': lead.get('source', ''),
                'published': lead.get('published', ''),
                'venue': lead.get('venue', ''),
                'abstract': lead.get('abstract', '')[:400],
            })
        return {'query': query, 'results': compact, 'errors': errors}

    @staticmethod
    def _tool_result(actions, tool_leads, usage=None, provider_error=''):
        """Build a completed response from tool evidence already obtained.

        A provider may reject the final formatting turn after the local search
        calls have completed (for example because the accumulated context is
        too large). Those completed calls remain useful leads and should still
        go through independent verification instead of being discarded.
        """
        output = [{'type': 'web_search_call', 'status': 'completed',
                   'action': {'type': 'search', 'query': action['query']}}
                  for action in actions]
        output.append({'type': 'message', 'content': [
            {'type': 'output_text', 'text': '', 'annotations': []}]})
        result = {'status': 'completed', 'output': output,
                  'usage': usage or {}, 'search_mode': 'function_tool',
                  'tool_candidates': WebResearchAgent._dedup_tool_candidates(tool_leads)}
        if provider_error:
            result['provider_error'] = str(provider_error)[:200]
        return result

    def _function_search(self, context, timeout):
        tool = {'type': 'function', 'function': {
            'name': 'web_search',
            'description': ('Search current public scholarly indexes for paper leads. '
                            'The program will independently verify every returned URL.'),
            'parameters': {'type': 'object', 'properties': {
                'query': {'type': 'string', 'description': 'A focused scholarly web query including a topic and, when useful, a venue or source.'}},
                'required': ['query'], 'additionalProperties': False},
        }}
        messages = [
            {'role': 'system', 'content': self.prompt},
            {'role': 'user', 'content': json.dumps(context, ensure_ascii=False)},
        ]
        actions, tool_calls, tool_leads = [], 0, []
        max_calls = self.options['max_tool_calls_per_round']
        last_response = None
        while tool_calls < max_calls:
            payload = {'model': self.model, 'messages': messages, 'tools': [tool],
                       'tool_choice': 'auto',
                       'max_completion_tokens': self.options['max_output_tokens']}
            effort = os.getenv('LLM_REASONING_EFFORT') or self.llm.get('reasoning_effort')
            if effort:
                payload['reasoning_effort'] = effort
            try:
                last_response = get_json(self.chat_url, payload=payload,
                                         headers={'Authorization': 'Bearer ' + self.key},
                                         timeout=timeout, attempts=1)
            except RequestError as exc:
                if actions:
                    return self._tool_result(actions, tool_leads, provider_error=exc)
                raise
            choice = (last_response.get('choices') or [{}])[0]
            message = choice.get('message') or {}
            calls = message.get('tool_calls') or []
            if not calls:
                text = message.get('content') or ''
                output = [{'type': 'web_search_call', 'status': 'completed',
                           'action': {'type': 'search', 'query': a['query']}}
                          for a in actions]
                output.append({'type': 'message', 'content': [
                    {'type': 'output_text', 'text': text, 'annotations': []}]})
                return {'status': 'completed', 'output': output,
                        'usage': last_response.get('usage', {}),
                        'search_mode': 'function_tool',
                        'tool_candidates': self._dedup_tool_candidates(tool_leads)}
            # Preserve the complete assistant tool-call message. Thinking-mode
            # providers require reasoning_content on the next turn when it is
            # present in the response.
            assistant = {'role': 'assistant', 'content': message.get('content') or '',
                         'tool_calls': calls}
            if 'reasoning_content' in message:
                assistant['reasoning_content'] = message['reasoning_content']
            messages.append(assistant)
            for call in calls:
                function = call.get('function') or {}
                call_id = call.get('id', f'call_{tool_calls + 1}')
                # Providers may return more calls than the requested local
                # budget in one assistant message. Every id still needs a
                # corresponding tool message; skipped calls receive an empty
                # bounded result and are never executed.
                if tool_calls >= max_calls:
                    messages.append({'role': 'tool', 'tool_call_id': call_id,
                                     'content': json.dumps({
                                         'query': '', 'results': [],
                                         'errors': ['tool budget exhausted']
                                     }, ensure_ascii=False)})
                    continue
                try:
                    arguments = json.loads(function.get('arguments') or '{}')
                    query = arguments.get('query')
                    if not isinstance(query, str) or not query.strip():
                        raise ValueError('query is required')
                    result = self._local_scholar_search(query, context)
                except Exception as exc:
                    query = str((function.get('arguments') or '')[:180])
                    result = {'query': query, 'results': [], 'errors': [type(exc).__name__]}
                tool_calls += 1
                actions.append({'query': str(query)[:180]})
                tool_leads.extend(result.get('results', []))
                messages.append({'role': 'tool', 'tool_call_id': call_id,
                                 'content': json.dumps(result, ensure_ascii=False)})
        # Ask for a final bounded JSON answer after the local tool budget. This
        # call has no tools, so it cannot silently exceed the per-round budget.
        messages.append({'role': 'user', 'content':
                         '工具调用预算已用完。只根据已返回的工具结果输出候选JSON，不要再调用工具。'})
        payload = {'model': self.model, 'messages': messages,
                   'max_completion_tokens': self.options['max_output_tokens'],
                   'response_format': {'type': 'json_object'}}
        effort = os.getenv('LLM_REASONING_EFFORT') or self.llm.get('reasoning_effort')
        if effort:
            payload['reasoning_effort'] = effort
        try:
            last_response = get_json(self.chat_url, payload=payload,
                                     headers={'Authorization': 'Bearer ' + self.key},
                                     timeout=timeout, attempts=1)
        except RequestError as exc:
            # At least one local search completed, so keep its leads. The
            # outer verifier will decide whether any lead is admissible.
            return self._tool_result(actions, tool_leads, provider_error=exc)
        message = ((last_response.get('choices') or [{}])[0].get('message') or {})
        text = message.get('content') or ''
        output = [{'type': 'web_search_call', 'status': 'completed',
                   'action': {'type': 'search', 'query': a['query']}}
                  for a in actions]
        output.append({'type': 'message', 'content': [
            {'type': 'output_text', 'text': text, 'annotations': []}]})
        return {'status': 'completed', 'output': output,
                'usage': last_response.get('usage', {}),
                'search_mode': 'function_tool',
                'tool_candidates': self._dedup_tool_candidates(tool_leads)}

    @staticmethod
    def _dedup_tool_candidates(leads):
        result, seen = [], set()
        for lead in leads:
            url, title = lead.get('url'), lead.get('title')
            if isinstance(url, str) and isinstance(title, str) and url not in seen:
                seen.add(url)
                result.append({'title': title, 'url': url})
        buckets = {'conference': [], 'arxiv': []}
        for lead in result:
            bucket = 'arxiv' if urlparse(lead['url']).hostname in ('arxiv.org', 'www.arxiv.org') else 'conference'
            buckets[bucket].append(lead)
        mixed = []
        for index in range(max(len(buckets['conference']), len(buckets['arxiv']))):
            for bucket in ('conference', 'arxiv'):
                if index < len(buckets[bucket]):
                    mixed.append(buckets[bucket][index])
        return mixed

    def search(self, context, timeout):
        if self.search_mode == 'function_tool':
            return self._function_search(context, timeout)
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


def source_quotas(limit):
    """Odd result counts reserve the extra slot for a conference paper."""
    return {'conference': (limit + 1) // 2, 'arxiv': limit // 2}


def verified_route(p):
    """Classify from independently verified metadata, never an LLM's label."""
    url = p.get('verification', {}).get('url', '')
    host = urlparse(url).hostname
    if host == 'arxiv.org' and p.get('date_basis') == 'arxiv_first_submission':
        return 'arxiv'
    if host and host != 'arxiv.org' and p.get('date_basis') in ('conference_publication','conference_program_publication','conference_edition') and p.get('venue_label') in VENUES:
        return 'conference'
    return None


def select_balanced(pool, quotas, ready_only=False, archive=()):
    """Assign distinct identities to two quotas, preserving each route's own date.

    Reserve enough dual-route identities for arXiv when possible, then prefer
    newer conferences. Archived aliases help deduplicate but never establish
    an eligible route for this run. Each paper occupies at most one slot.
    """
    usable = [p for p in pool if verified_route(p) and
              p.get('status') in (('ready',) if ready_only else ('pending', 'ready'))]
    groups = []
    for merged in merge_records(list(archive) + pool):
        keys = identity_keys(merged)
        routes = {}
        for p in usable:
            if identity_keys(p) & keys:
                route = verified_route(p)
                if route not in routes or p.get('display_date', p['published']) > routes[route].get('display_date', routes[route]['published']):
                    routes[route] = p
        if routes:
            groups.append(routes)
    conferences = sorted((g for g in groups if 'conference' in g),
                         key=lambda g:g['conference'].get('display_date',g['conference']['published']), reverse=True)
    # Reserve enough dual-route papers to fill arXiv; otherwise favor newer conferences.
    arxiv_only = sum('arxiv' in g and 'conference' not in g for g in groups)
    dual_count = sum('arxiv' in g for g in conferences)
    dual_allowance = max(0, dual_count - max(0, quotas['arxiv'] - arxiv_only))
    conference_only = sum('arxiv' not in g for g in conferences)
    dual_allowance = max(dual_allowance, min(dual_count, max(0, quotas['conference']-conference_only)))
    selected, used, used_dual = [], set(), 0
    for g in conferences:
        if len(selected) >= quotas['conference']:
            break
        if 'arxiv' in g and used_dual >= dual_allowance:
            continue
        selected.append({**g['conference'], 'selection_bucket':'conference'})
        used.add(id(g))
        used_dual += 'arxiv' in g
    arxiv = sorted((g for g in groups if 'arxiv' in g and id(g) not in used),
                   key=lambda g:g['arxiv'].get('display_date',g['arxiv']['published']), reverse=True)
    selected.extend({**g['arxiv'], 'selection_bucket':'arxiv'} for g in arxiv[:quotas['arxiv']])
    return sorted(selected, key=lambda p:p.get('display_date',p['published']), reverse=True)


def quota_progress(papers, quotas):
    counts = Counter(p['selection_bucket'] for p in papers)
    return {k:{'requested':v, 'returned':counts[k], 'shortfall':max(0,v-counts[k])} for k,v in quotas.items()}


def search(root, config, args):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if args.no_llm:
        raise ValueError('search requires a web-search-capable LLM; use run --no-llm for legacy metadata collection')
    limit = getattr(args, 'limit', 5)
    if limit > 20 and not config.get('_bulk_child'):
        from .bulk import bulk_search
        return bulk_search(root, config, args)
    if not 1 <= limit <= 20:
        raise ValueError('search --limit must be 1..20')
    quotas = config.get('_source_quotas') or source_quotas(limit)
    if sum(quotas.values()) != limit or any(type(v) is not int or v < 0 for v in quotas.values()):
        raise ValueError('Source quotas must be nonnegative integers adding to limit')
    options = dict(max_rounds=3, max_tool_calls_per_round=12, max_output_tokens=6000,
                   candidate_limit=10, timeout=180, max_seconds=600, max_summary_papers=10)
    options.update(config.get('search_agent', {}))
    validate_options(options)
    today = date.fromisoformat(args.until) if args.until else datetime.now(timezone.utc).date()
    windows = source_windows(config, args, today)
    # Compatibility envelope only. Admission always uses the specific route.
    since = min(date.fromisoformat(w['since']) for w in windows.values())
    request = (root/'prompts/search.request.txt').read_text(encoding='utf-8').strip()
    if not request:
        raise ValueError('Fixed search request is empty')
    agent = WebResearchAgent(config['llm'], options, (root/'prompts/search.agent.txt').read_text(encoding='utf-8'))
    summary_prompt = (root/'prompts/search.summary.zh.txt').read_text(encoding='utf-8')
    summary_prompt += '\n研究需求（仅用于主题相关性判断）：\n' + request
    summarizer = Summarizer({**config['llm'], 'require_fulltext':True, 'evidence_mode':'segments'}, summary_prompt, extra_validator=validate_topics)
    start = time.monotonic()
    deadline = start + options['max_seconds']
    report = {'mode':agent.search_mode, 'started_at':datetime.now(timezone.utc).isoformat(),
              'window':{'since':str(since), 'until':str(today)}, 'source_windows':windows, 'llm_enabled':True,
              'requested':limit, 'active_topics':list(TOPICS), 'source_quotas':quotas, 'quota_progress':quota_progress([],quotas),
              'rounds':[], 'sources':{}, 'rejections':[],
              'request_hash':hashlib.sha256(request.encode()).hexdigest(), 'llm_processed':0,
              'coverage':'Best effort within time/tool budgets; not an exhaustive newest-paper ranking.'}
    with (nullcontext() if config.get('_lock_held') else lock(root/'data/pipeline.lock')):
        archive = read_json(root/'data/papers.json', {'schema_version':1, 'papers':[]})['papers']
        initial_archive_keys = {k for p in archive for k in identity_keys(p)}
        accepted, pool, seen, feedback = [], [], set(), list(config.get('_prior_feedback',[]))
        verification_attempts = Counter()
        summary_budget = max(limit, options['max_summary_papers'])
        for round_number in range(1, options['max_rounds']+1):
            if time.monotonic() >= deadline:
                break
            progress = quota_progress(accepted, quotas)
            print(f'Web research round {round_number}/{options["max_rounds"]}: ' +
                  ' | '.join(f'{k} {v["returned"]}/{v["requested"]}' for k,v in progress.items()), flush=True)
            context = {'research_request':request, 'utc_today':str(today),
                       'date_window':report['window'], 'source_windows':windows, 'active_topics':list(TOPICS), 'requested_count':limit,
                       'candidate_limit':options['candidate_limit'], 'primary_source_domains':DOMAINS,
                       'conference_aliases':VENUES, 'conference_directories':DIRECTORY_SOURCES,
                       'search_scope':config.get('_search_scope', {}),
                       'exclude_titles':config.get('_exclude_titles', []),
                       'source_quotas':quotas, 'quota_progress':progress,
                       'search_focus':[k for k,v in progress.items() if v['shortfall']],
                       'accepted':[{'title':p['title'], 'url':p['verification']['url'], 'selection_bucket':p['selection_bucket']} for p in accepted],
                       'feedback':feedback[-30:], 'instruction':'Fill each source quota independently. Prioritize deficient buckets, newest within each bucket. Never substitute arXiv for conference slots. Repeat a rejected URL only when feedback.retry_same_url is true, at most once, with a corrected title or after a transient network failure. A NEW conference link for a known arXiv paper can establish another route, but the paper still counts only once.'}
            record = {'round':round_number, 'quota_before':progress}
            try:
                response = agent.search(context, min(options['timeout'], max(1, deadline-time.monotonic())))
                text, actions, citations = trace_response(response)
                record.update(status=response.get('status'), actions=actions, citations=citations,
                              usage={k:v for k,v in response.get('usage',{}).items() if k in ('input_tokens','output_tokens','total_tokens')})
                if response.get('provider_error'):
                    record['provider_error'] = str(response['provider_error'])[:200]
                if response.get('status') != 'completed':
                    raise ValueError('Responses output incomplete; no candidates admitted')
                if not any(a.get('status') == 'completed' for a in actions):
                    raise ValueError('No completed web_search call; answer is not verified live search')
                try:
                    candidates, notes = parse_candidates(text, options['candidate_limit'])
                except (ValueError, TypeError):
                    candidates = cited_candidates(citations, options['candidate_limit'])
                    if not candidates and response.get('tool_candidates'):
                        candidates = response['tool_candidates'][:options['candidate_limit']]
                        notes = 'Recovered candidates from completed local scholarly tool calls; all require primary-source verification.'
                        record['format_recovery'] = 'tool_results'
                    elif candidates:
                        notes = 'Recovered candidates from response citations; all require primary-source verification.'
                        record['format_recovery'] = 'url_citations'
                    if not candidates:
                        raise ValueError('No valid candidates JSON or primary-source citations') from None
                if not candidates and response.get('tool_candidates'):
                    candidates = response['tool_candidates'][:options['candidate_limit']]
                    notes = 'Model returned no final candidates; recovered leads from completed local scholarly tool calls for independent verification.'
                    record['format_recovery'] = 'tool_results'
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
                    if url in seen or verification_attempts[url] >= 2:
                        continue
                    verification_attempts[url] += 1
                    seen.add(url)
                    bucket = 'arxiv' if urlparse(url).hostname == 'arxiv.org' else 'conference'
                    route_since = date.fromisoformat(windows[bucket]['since'])
                    p = verify_candidate({**c,'_conference_year':config.get('_search_scope',{}).get('year')}, route_since, today, timeout=min(25, max(1, deadline-time.monotonic())))
                    scope = config.get('_search_scope', {})
                    if scope.get('bucket') and bucket != scope['bucket']:
                        raise VerificationError('Candidate belongs to another source bucket than this focused batch')
                    if scope.get('venue') and p.get('venue_label') != scope['venue']:
                        raise VerificationError('Candidate belongs to another conference than this focused batch')
                    if bucket == 'conference' and scope.get('year') and p.get('conference_year') != scope['year']:
                        raise VerificationError('Conference edition does not match focused year')
                    if config.get('_exclude_titles') and clean(p['title']).casefold() in {clean(t).casefold() for t in config['_exclude_titles']}:
                        continue
                    if c.get('fulltext_url'):
                        alternate = verify_candidate({'title':p['title'], 'url':c['fulltext_url']}, date(1991,1,1), today, timeout=20)
                        if alternate.get('arxiv_id'):
                            p['arxiv_id'] = alternate['arxiv_id']
                            p['pdf_url'] = alternate['pdf_url']
                            p['fulltext_alternate_verification'] = alternate['verification']
                    if c.get('directory_url'):
                        if p.get('date_basis') == 'arxiv_first_submission':
                            p['conference_evidence'] = verify_directory_match(p['title'], c['directory_url'], timeout=min(15, max(1, deadline-time.monotonic())))
                        # A verified publisher/DOI conference record already
                        # proves this route. An extra discovery-directory hint
                        # must not turn it into an arXiv-only candidate.
                    verified.append(p)
                except Exception as exc:
                    reason = str(exc)[:200] if isinstance(exc, (VerificationError,RequestError)) else type(exc).__name__
                    item = {'url':c['url'], 'title':c['title'][:300], 'reason':reason,
                            **recovery_feedback('metadata', reason)}
                    if item['retry_same_url']:
                        retry_url = canonical_url(c['url'])
                        item['retry_same_url'] = verification_attempts[retry_url] < 2
                        if item['retry_same_url']:
                            seen.discard(retry_url)
                    feedback.append(item)
                    report['rejections'].append(item)
            # Keep independently verified routes until assignment; a merged venue label
            # must never turn an arXiv-only verification into a conference slot.
            pool.extend(verified)
            attempted = set()
            while time.monotonic() < deadline and not config.get('_discovery_only'):
                selected = select_balanced(pool, quotas, archive=archive)
                p = next((p for p in selected if p['status'] != 'ready' and
                          p['verification']['url'] not in attempted), None)
                if p is None:
                    break
                attempted.add(p['verification']['url'])
                print(f'Processing {p["selection_bucket"]}: {p["venue_label"]} | {p["title"]}',flush=True)
                previous = next((a for a in archive if identity_keys(p) & identity_keys(a)
                                 and a.get('title') == p['title'] and a.get('abstract') == p['abstract']
                                 and a.get('full_text') and a.get('fulltext_source', {}).get('scope') == 'full_text'), None)
                if previous:
                    p.update(full_text=previous['full_text'], fulltext_source=previous['fulltext_source'])
                cached = next((a for a in archive + pool if identity_keys(p) & identity_keys(a)
                               and content_hash(a) == content_hash(p) and summarizer.cached(a)
                               and a.get('topics') and a.get('topic_evidence')), None)
                if cached:
                    for field in ('keywords','method','confidence','evidence','evidence_locations','topic_evidence_locations','summary_input_hash','prompt_hash','llm_model','llm_reasoning_effort','summarized_at','topics','topic_evidence','status'):
                        if field in cached:
                            p[field] = cached[field]
                elif report['llm_processed'] < summary_budget:
                    summarizer.config = {**config['llm'], 'require_fulltext':True, 'evidence_mode':'segments',
                        'timeout':min(config['llm']['timeout'], max(1, deadline-time.monotonic())),
                        'attempts':min(2, config['llm']['attempts'])}
                    try:
                        if config.get('_bulk_child'):
                            p['_allow_arxiv_lookup'] = True
                        load_methods(p, timeout=min(45, max(1, deadline-time.monotonic())))
                        coerce_legacy_fulltext(p)
                        summarizer.summarize(p)
                    except VerificationError as exc:
                        p.update(status='missing_fulltext', keywords=[], method='', error=str(exc)[:160])
                    finally:
                        p.pop('_allow_arxiv_lookup',None)
                    report['llm_processed'] += 1
                else:
                    break
                # Transfer summary status back to this verified route, without copying
                # the per-run bucket assignment into the persistent archive.
                for original in pool:
                    if original['verification']['url'] == p['verification']['url']:
                        original.update({k:v for k,v in p.items() if k != 'selection_bucket'})
                if p['status'] == 'ready' and p.get('topics'):
                    print(f'Verified {p["selection_bucket"]}: {p["published"]} | {p["venue_label"]} | {p["title"]}', flush=True)
                else:
                    stage = 'fulltext' if p['status'] == 'missing_fulltext' else 'summary'
                    item = {'url':p['verification']['url'], 'title':p['title'],
                            'reason':'Summary/topic validation: ' + p['status'],
                            'detail':p.get('error', ''),
                            'validation_errors':p.get('validation_errors', []),
                            **recovery_feedback(stage, p.get('error', ''))}
                    feedback.append(item)
                    report['rejections'].append(item)
                accepted = select_balanced(pool, quotas, ready_only=True, archive=archive)
                durable = [{k:v for k,v in p.items() if k != 'selection_bucket'} for p in accepted]
                if durable:
                    archive = merge_records(archive + durable)
                    write_json(root/'data/papers.json', {'schema_version':1, 'papers':archive})
            accepted = select_balanced(pool, quotas, ready_only=True, archive=archive)
            report['quota_progress'] = quota_progress(accepted, quotas)
            record['quota_after'] = report['quota_progress']
            write_json(root/'data/last_run.json', report)
            if all(v['shortfall'] == 0 for v in report['quota_progress'].values()) or report['llm_processed'] >= summary_budget:
                break
            feedback.append({'reason':'Source quotas not filled; do not backfill with another source.',
                             'quota_progress':report['quota_progress'],
                             'source_windows':windows,
                             'action':'Find missing conference/arXiv routes in their own source_windows and eligibility scope; use next_action on each rejection.'})
        durable = [{k:v for k,v in p.items() if k != 'selection_bucket'} for p in accepted]
        papers = merge_records(archive + durable) if accepted else archive
        results = []
        for p in accepted:
            persisted = next((a for a in papers if identity_keys(a) & identity_keys(p)), None)
            if persisted:
                # Preserve archive IDs but keep this run's verified date/text, even on a historic --until.
                results.append({**p, 'id':persisted['id']})
        results.sort(key=lambda p:p.get('display_date', p['published']), reverse=True)
        report.update(finished_at=datetime.now(timezone.utc).isoformat(), returned=len(results),
                      quota_progress=quota_progress(results, quotas),
                      total=len(papers), statuses=dict(Counter(p['status'] for p in papers)),
                      result_ids=[p['id'] for p in results],
                      deduplicated=sum(bool(identity_keys(p) & initial_archive_keys) for p in accepted),
                      elapsed_seconds=round(time.monotonic()-start,2), shortfall=max(0, limit-len(results)))
        ok = any(any(a.get('status')=='completed' for a in r.get('actions',[])) for r in report['rounds'])
        report['sources']['web_search'] = {'ok':ok, 'mode':agent.search_mode, 'verified':len(results), 'truncated':len(results)<limit}
        if not ok:
            report['error'] = 'No completed live web search; archive preserved'
        report['stop_reason'] = ('target_reached' if len(results)>=limit else 'time_budget' if time.monotonic()>=deadline else 'summary_budget' if report['llm_processed']>=summary_budget else 'round_budget')
        if accepted:
            write_json(root/'data/papers.json', {'schema_version':1, 'papers':papers})
        write_json(root/'data/last_run.json', report)
        write_json(root/'data/search_results.json', {'report':report, 'papers':results})
        export_site(papers, report, root/'site')
        print(json.dumps({'returned':len(results), 'requested':limit, 'stop_reason':report['stop_reason'],
                          'quota_progress':report['quota_progress'],
                          'results':[{'title':p['title'], 'selection_bucket':p['selection_bucket'], 'date':p.get('display_date',p['published']), 'venue':p.get('venue_label'), 'topics':p.get('topics'), 'keywords':p['keywords'], 'method':p['method'], 'url':p.get('pdf_url') or p['verification']['url']} for p in results]}, ensure_ascii=False, indent=2), flush=True)
        return 0 if len(results)>=limit else 4 if ok else 2
