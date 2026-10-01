import json
import os
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from gnn_digest.agent import search, source_windows, validate_topics, recovery_feedback
from gnn_digest.evidence import EvidenceError, locate_evidence, validate_evidence_list, fulltext_segments, resolve_evidence_ids
from gnn_digest.llm import Summarizer, validate_summary
from gnn_digest.storage import read_json
import test_agent as fixtures
from test_agent import answer, candidate, conference_candidate, conference_html, html, response, mock_methods


class EvidenceTests(unittest.TestCase):
    def test_segments_cover_entire_source_without_truncation(self):
        source = ('Background. We encode atoms as nodes.\n' * 50) + '结论。'
        segments = fulltext_segments(source)
        self.assertEqual(''.join(s['text'] for s in segments),source)
        self.assertTrue(all(len(s['text']) <= 180 for s in segments))
        self.assertTrue(all(s['text'] == source[s['start']:s['end']] for s in segments))

    def test_model_ids_resolve_to_source_and_fabricated_ids_fail(self):
        source = 'We study text-attributed graphs with message passing.'
        segments = fulltext_segments(source)
        value = {**answer(),'evidence_ids':['S0001'],'topic_evidence_ids':{'TAG':'S0001'}}
        result = validate_topics(validate_summary(resolve_evidence_ids(value,segments),source),source)
        self.assertEqual(result['evidence'],[source])
        with self.assertRaises(EvidenceError):
            resolve_evidence_ids({**value,'evidence_ids':['S9999']},segments)

    @patch.dict(os.environ, {'LLM_BASE_URL':'https://example.test/v1','LLM_API_KEY':'test-secret','LLM_MODEL':'test'})
    def test_segment_mode_sends_whole_text_and_saves_original_spans(self):
        source = 'We study text-attributed graphs with attention-based message passing.'
        value = {**answer(),'evidence_ids':['S0001'],'topic_evidence_ids':{'TAG':'S0001'}}
        p = {'title':'Graph method','abstract':'','full_text':source,'fulltext_source':{'scope':'full_text'}}
        s = Summarizer({'attempts':1,'timeout':5,'max_tokens':1500,'require_fulltext':True,'evidence_mode':'segments'},'test',validate_topics)
        with patch('gnn_digest.llm.get_json',return_value={'choices':[{'message':{'content':json.dumps(value)}}]}) as req:
            s.summarize(p)
        sent = json.loads(req.call_args.kwargs['payload']['messages'][1]['content'])
        self.assertEqual(''.join(x['text'] for x in sent['full_text_segments']),source)
        self.assertEqual(p['status'],'ready')
        self.assertEqual(p['evidence'],[source])

    def test_whitespace_only_repair_retains_exact_original_and_offsets(self):
        source = 'Intro. We encode atoms\n  as nodes and\tbonds as edges. End.'
        quote = 'We encode atoms as nodes and bonds as edges.'
        span, location = locate_evidence(quote, source, 'evidence[0]')
        self.assertEqual(span, source[location['start']:location['end']])
        self.assertIn('\n', span)
        self.assertEqual(' '.join(span.split()), quote)

    def test_rewrites_ellipsis_case_and_punctuation_are_not_normalized(self):
        source = 'We encode atoms as nodes and bonds as edges.'
        for quote in ['We encode atoms as nodes & bonds as edges.',
                      'We encode atoms ... bonds as edges.',
                      'we encode atoms as nodes and bonds as edges.',
                      'We encode atoms as nodes and bonds as edges!']:
            with self.subTest(quote=quote), self.assertRaises(EvidenceError) as error:
                locate_evidence(quote, source, 'evidence[0]')
            self.assertEqual(error.exception.code, 'evidence_not_found')

    def test_diagnostic_codes_distinguish_count_type_length_and_missing(self):
        for value, code in [(None,'evidence_type'), ([], 'evidence_count'),
                            ([123], 'evidence_type'), (['short'],'evidence_length'),
                            (['A made up long sentence.'], 'evidence_not_found')]:
            with self.subTest(code=code), self.assertRaises(EvidenceError) as error:
                validate_evidence_list(value, 'A real source sentence about graphs.')
            self.assertEqual(error.exception.code, code)

    def test_topics_apply_same_matching_and_keep_coordinates(self):
        value = answer()
        source = 'We study text-attributed\n graphs with message passing.'
        result = validate_topics(value, source)
        span = result['topic_evidence']['TAG']
        loc = result['topic_evidence_locations']['TAG']
        self.assertEqual(span, source[loc['start']:loc['end']])

    def test_irrelevant_result_still_requires_evidence_array(self):
        with self.assertRaises(EvidenceError):
            validate_summary({'relevant':False,'confidence':'low','keywords':[],'method':'','evidence':None},'')

    @patch.dict(os.environ, {'LLM_BASE_URL':'https://example.test/v1', 'LLM_API_KEY':'test-secret', 'LLM_MODEL':'test'})
    def test_targeted_retry_fixes_evidence_without_retrieving_paper(self):
        source = 'We study text-attributed graphs. We encode atoms\n as nodes and bonds as edges.'
        bad = {**answer(), 'evidence':['A fabricated sentence about graphs.']}
        good = {**answer(), 'evidence':['We encode atoms as nodes and bonds as edges.']}
        summarizer = Summarizer({'attempts':2,'timeout':5,'max_tokens':1500,'require_fulltext':True}, 'test', validate_topics)
        p = {'title':'Graph method','abstract':'','full_text':source,'fulltext_source':{'scope':'full_text'}}
        responses = [{'choices':[{'message':{'content':json.dumps(v)}}]} for v in (bad,good)]
        with patch('gnn_digest.llm.get_json', side_effect=responses) as req, patch('gnn_digest.llm.time.sleep'):
            summarizer.summarize(p)
        self.assertEqual(p['status'], 'ready')
        self.assertEqual(p['validation_errors'][0]['code'], 'evidence_not_found')
        self.assertIn('evidence[0]', req.call_args.kwargs['payload']['messages'][-1]['content'])
        self.assertIn(p['evidence'][0], source)
        self.assertEqual(req.call_count, 2)


class WindowTests(unittest.TestCase):
    def test_defaults_boundaries_and_explicit_overrides(self):
        args = Namespace(days=None)
        today = date(2026,9,29)
        windows = source_windows({}, args, today)
        self.assertEqual(windows['conference']['since'], '2026-07-02')
        self.assertEqual(windows['arxiv']['since'], '2026-07-29')
        self.assertEqual(source_windows({}, Namespace(days=None), date(2026, 4, 30))['arxiv']['since'], '2026-02-28')
        self.assertEqual(source_windows({}, Namespace(days=None), date(2026, 3, 31))['arxiv']['since'], '2026-01-31')
        self.assertEqual(source_windows({'search_windows':{'arxiv_months':2}},
                                        Namespace(days=None, arxiv_since='2026-08-01'), today)['arxiv']['since'],
                         '2026-08-01')
        args.days, args.conference_days = 30, 60
        windows = source_windows({}, args, today)
        self.assertEqual(windows['conference']['days'],60)
        self.assertEqual(windows['arxiv']['days'],30)
        for invalid in (0,-1,True,'14',3661):
            with self.subTest(days=invalid), self.assertRaises(ValueError):
                source_windows({}, Namespace(days=invalid), today)

    @patch.dict(os.environ, {'LLM_BASE_URL':'https://example.test/v1','LLM_API_KEY':'test-secret','LLM_MODEL':'test'})
    def test_older_conference_allowed_but_older_arxiv_rejected_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, config, args = fixtures.AgentTests().setup_root(tmp)
            args.days, args.until, args.limit = None, '2026-09-29', 2
            config['search_windows'] = {'conference_days':90, 'arxiv_days':14}
            old_a = {**candidate(1), 'title':'Old Graph Neural Network'}
            new_a = {**candidate(2), 'title':'New Graph Neural Network'}
            c = conference_candidate()
            def page(url, **kwargs):
                if 'aclanthology' in url:
                    return conference_html().replace('2026/09/25','2026/08/01')
                if url == old_a['url']:
                    return html(title=old_a['title'],submitted='1 Aug 2026')
                return html(title=new_a['title'])
            with patch('gnn_digest.agent.WebResearchAgent.search', side_effect=[response([c,old_a]),response([new_a])]) as agent, \
                 patch('gnn_digest.verification.fetch_page',side_effect=page), \
                 patch('gnn_digest.agent.load_methods',side_effect=mock_methods), \
                 patch('gnn_digest.llm.get_json',return_value={'choices':[{'message':{'content':json.dumps(answer())}}]}):
                self.assertEqual(search(root, config, args),0)
            report = read_json(root/'data/last_run.json',{})
            self.assertEqual(report['quota_progress']['conference']['returned'],1)
            self.assertEqual(report['quota_progress']['arxiv']['returned'],1)
            self.assertEqual(report['rejections'][0]['code'],'outside_window')
            self.assertEqual(agent.call_args_list[1].args[0]['search_focus'],['arxiv'])
            self.assertEqual(report['source_windows']['arxiv']['since'],'2026-09-16')
            public = read_json(root/'site/data/papers.json',{})['papers']
            self.assertEqual(len(public),2)
            self.assertTrue(all('full_text' not in p and 'evidence_locations' not in p for p in public))

    def test_recovery_actions_are_stage_specific(self):
        self.assertEqual(recovery_feedback('metadata','Publication date missing')['code'],'missing_date')
        self.assertEqual(recovery_feedback('metadata','SSLError')['code'],'source_unreachable')
        self.assertEqual(recovery_feedback('fulltext','Full text unavailable')['code'],'missing_fulltext')
        self.assertEqual(recovery_feedback('fulltext','Full text exceeds 120000 character limit, HTTPError')['code'],'fulltext_too_large')

    @patch.dict(os.environ, {'LLM_BASE_URL':'https://example.test/v1','LLM_API_KEY':'test-secret','LLM_MODEL':'test'})
    def test_corrected_title_at_same_url_can_be_reverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, config, args = fixtures.AgentTests().setup_root(tmp)
            c = conference_candidate()
            with patch('gnn_digest.agent.WebResearchAgent.search',side_effect=[response([{**c,'title':'Wrong title'}]),response([c])]) as agent, \
                 patch('gnn_digest.verification.fetch_page',return_value=conference_html()) as fetch, \
                 patch('gnn_digest.agent.load_methods',side_effect=mock_methods), \
                 patch('gnn_digest.llm.get_json',return_value={'choices':[{'message':{'content':json.dumps(answer())}}]}):
                self.assertEqual(search(root,config,args),0)
            self.assertEqual(fetch.call_count,2)
            feedback = agent.call_args_list[1].args[0]['feedback'][0]
            self.assertTrue(feedback['retry_same_url'])

    @patch.dict(os.environ, {'LLM_BASE_URL':'https://example.test/v1','LLM_API_KEY':'test-secret','LLM_MODEL':'test'})
    def test_network_retry_never_exceeds_two_fetches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, config, args = fixtures.AgentTests().setup_root(tmp)
            config['search_agent']['max_rounds'] = 3
            with patch('gnn_digest.agent.WebResearchAgent.search',return_value=response([conference_candidate()])), \
                 patch('gnn_digest.verification.fetch_page',side_effect=TimeoutError) as fetch:
                self.assertEqual(search(root,config,args),4)
            self.assertEqual(fetch.call_count,2)


if __name__ == '__main__':
    unittest.main()
