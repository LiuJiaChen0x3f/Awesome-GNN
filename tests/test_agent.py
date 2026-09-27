import json
import os
import shutil
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from gnn_digest.agent import search, WebResearchAgent, endpoint, validate_topics, cited_candidates, trace_response
from gnn_digest.cli import ROOT, run
from gnn_digest.models import content_hash, merge_records
from gnn_digest.storage import read_json, write_json
from gnn_digest.verification import verify_candidate, VerificationError, safe_scholarly_url, venue_abbreviation

ABSTRACT = 'We propose a graph neural network with attention-based message passing for molecular property prediction.'
METHOD_TEXT = '3 Method\nOur graph neural network uses attention-based message passing for molecular property prediction. We encode atoms as nodes and bonds as edges, aggregate neighbor messages with attention weights, and train the representation for property prediction.'


def mock_methods(p, **kwargs):
    p['method_text'] = METHOD_TEXT
    p['fulltext_source'] = {'url':'https://arxiv.org/pdf/2609.00001', 'format':'pdf'}

def html(title='A Graph Neural Network', submitted='25 Sep 2026', extra=''):
    return f'''<html><head><meta name="citation_title" content="{title}"/>
    <meta name="citation_author" content="Researcher"/>{extra}</head><body>
    [Submitted on {submitted}, last revised 26 Sep 2026]
    <blockquote class="abstract"><span>Abstract:</span> {ABSTRACT}</blockquote></body></html>'''

def candidate(i=1):
    return {'title':'A Graph Neural Network', 'url':f'https://arxiv.org/abs/2609.{i:05d}'}


def conference_candidate():
    return {'title':'A Graph Neural Network', 'url':'https://aclanthology.org/2026.emnlp-long.1/'}


def conference_html():
    return html(extra='<meta name="citation_conference_title" content="Proceedings of Empirical Methods in Natural Language Processing"><meta name="citation_publication_date" content="2026/09/25">')

def response(items, actions=True, status='completed'):
    return {'status':status,'output':([{'type':'web_search_call','status':'completed','action':{'type':'search','queries':['graph papers']}}] if actions else []) + [{'type':'message','content':[{'type':'output_text','text':json.dumps({'candidates':items,'notes':''}), 'annotations':[]}]}]}

def answer():
    return {'relevant':True,'topics':['GNN'],'topic_evidence':{'GNN':'We propose a graph neural network'},'keywords':['GNN','注意力','消息传递','分子图','属性预测'], 'method':'通过注意力加权消息传递学习分子图表示，预测分子属性。','confidence':'high','evidence':['We encode atoms as nodes and bonds as edges']}


class VerificationTests(unittest.TestCase):
    def test_citation_recovery_and_final_message_selection(self):
        items=cited_candidates([{'url':'https://arxiv.org/abs/2609.00001','title':'[2609.00001] A Graph Neural Network'}, {'url':'https://arxiv.org/abs/2609.00001?ref=x','title':'duplicate'}, {'url':'https://evil.test/paper','title':'Bad'}],10)
        self.assertEqual(items,[candidate()])
        r=response([candidate()])
        r['output'].insert(0,{'type':'message','content':[{'type':'output_text','text':'Searching now.'}]})
        self.assertEqual(json.loads(trace_response(r)[0])['candidates'],[candidate()])

    def test_v1_date_and_abstract_are_from_source_not_model(self):
        with patch('gnn_digest.verification.fetch_page',return_value=html()):
            p=verify_candidate({**candidate(),'date':'2026-09-26','abstract':'fake'},date(2026,9,20),date(2026,9,26))
        self.assertEqual(p['published'],'2026-09-25')
        self.assertEqual(p['abstract'],ABSTRACT)
        self.assertEqual(p['venue_label'],'arXiv')
        self.assertTrue(p['pdf_url'].endswith('/2609.00001'))

    def test_citation_publisher_suffix_removed_only_on_matching_domain(self):
        citations = [
            {'url':'https://aclanthology.org/2026.acl-long.1/', 'title':'A Graph Neural Network - ACL Anthology'},
            {'url':'https://www.ijcai.org/proceedings/2026/62', 'title':'A Graph Neural Network | IJCAI'},
            {'url':'https://arxiv.org/abs/2609.00001', 'title':'A Graph Neural Network | IJCAI'},
        ]
        result = cited_candidates(citations, 10)
        self.assertEqual([p['title'] for p in result], ['A Graph Neural Network','A Graph Neural Network','A Graph Neural Network | IJCAI'])
        with patch('gnn_digest.verification.fetch_page',return_value=conference_html()):
            verified = verify_candidate(result[0],date(2026,9,20),date(2026,9,26))
        self.assertEqual(verified['date_basis'],'conference_publication')

    def test_old_revision_and_wrong_title_rejected(self):
        with patch('gnn_digest.verification.fetch_page',return_value=html(submitted='1 Jan 2025')):
            with self.assertRaises(VerificationError):
                verify_candidate(candidate(),date(2026,9,20),date(2026,9,26))
        with patch('gnn_digest.verification.fetch_page',return_value=html(title='A Different Paper')):
            with self.assertRaises(VerificationError):
                verify_candidate(candidate(),date(2026,9,20),date(2026,9,26))

    def test_untrusted_urls_rejected_before_fetch(self):
        for u in ('http://arxiv.org/abs/2609.1','https://localhost/x','https://127.0.0.1/x','https://arxiv.org.evil.test/x','https://name:pass@arxiv.org/abs/2609.00001'):
            with self.subTest(url=u), self.assertRaises(VerificationError):
                safe_scholarly_url(u)

    def test_conference_main_track_and_date_precision(self):
        c={'title':'A Graph Neural Network','url':'https://aclanthology.org/2026.emnlp-long.1/'}
        meta='<meta name="citation_conference_title" content="Proceedings of Empirical Methods in Natural Language Processing"><meta name="citation_publication_date" content="2026/09/25">'
        with patch('gnn_digest.verification.fetch_page',return_value=html(extra=meta)):
            p=verify_candidate(c,date(2026,9,20),date(2026,9,26))
            self.assertEqual(p['venue_label'],'EMNLP')
            with self.assertRaises(VerificationError):
                verify_candidate({**c,'url':'https://aclanthology.org/2026.findings-emnlp.1/'},date(2026,9,20),date(2026,9,26))
        with patch('gnn_digest.verification.fetch_page',return_value=html(extra=meta.replace('2026/09/25','2026/09'))):
            with self.assertRaises(VerificationError):
                verify_candidate(c,date(2026,9,20),date(2026,9,26))
        self.assertEqual(venue_abbreviation('Findings of EMNLP'),'')
        self.assertEqual(venue_abbreviation('ICML Workshop'),'')

    def test_ijcai_body_abstract_and_main_track(self):
        c={'title':'A Graph Neural Network','url':'https://www.ijcai.org/proceedings/2026/310'}
        meta='<meta name="citation_title" content="A Graph Neural Network"><meta name="citation_conference_title" content="International Joint Conference on Artificial Intelligence"><meta name="citation_online_date" content="2026/09/16">'
        body='<div>Main Track. Pages 1-9.</div><div class="col-md-12">'+ABSTRACT+'</div>'
        with patch('gnn_digest.verification.fetch_page',return_value='<html><head>'+meta+'</head><body>'+body+'</body></html>'):
            p=verify_candidate(c,date(2026,9,14),date(2026,9,27))
        self.assertEqual(p['abstract'],ABSTRACT)
        self.assertEqual(p['venue_label'],'IJCAI')
        with patch('gnn_digest.verification.fetch_page',return_value='<html><head>'+meta+'</head><body>'+body.replace('Main Track','AI4Tech')+'</body></html>'):
            with self.assertRaises(VerificationError):
                verify_candidate(c,date(2026,9,14),date(2026,9,27))

    def test_topics_require_evidence_and_no_five_topic_requirement(self):
        self.assertEqual(validate_topics(answer(),ABSTRACT)['topics'],['GNN'])
        for changes in ({'topics':['OTHER']},{'topic_evidence':{'GNN':'This is a made up statement'}},{'topics':['GNN','GNN']}):
            with self.assertRaises(ValueError):
                validate_topics({**answer(),**changes},ABSTRACT)

    def test_updated_abstract_same_publication_date_supersedes_cache(self):
        with patch('gnn_digest.verification.fetch_page',return_value=html()):
            old=verify_candidate(candidate(),date(2026,9,20),date(2026,9,26))
        old.update(status='ready',summary_input_hash=content_hash(old),method='旧摘要',keywords=['旧'])
        new={**old,'abstract':ABSTRACT+' We add an ablation study.', 'status':'pending','keywords':[],'method':''}
        new.pop('summary_input_hash')
        merged=merge_records([old,new])[0]
        self.assertEqual(merged['abstract'],new['abstract'])
        self.assertEqual(merged['status'],'pending')


@patch.dict(os.environ,{'LLM_BASE_URL':'https://example.test/v1','LLM_API_KEY':'secret-probe','LLM_MODEL':'test','LLM_REASONING_EFFORT':'medium'})
class AgentTests(unittest.TestCase):
    def setup_root(self, tmp):
        root=Path(tmp)
        shutil.copytree(ROOT/'prompts',root/'prompts')
        config=read_json(ROOT/'config.json',{})
        config['search_agent'].update(max_rounds=2, max_seconds=60)
        write_json(root/'config.json',config)
        return root, config, Namespace(command='search',root=str(root), config=None,no_llm=False,limit=1,days=14,until='2026-09-26')

    def test_responses_request_uses_real_tools_not_query_plan(self):
        options={'max_tool_calls_per_round':4,'max_output_tokens':2000}
        agent=WebResearchAgent({'reasoning_effort':'medium'}, options, 'instructions')
        with patch('gnn_digest.agent.get_json',return_value=response([])) as req:
            agent.search({'research_request':'find papers'},30)
        self.assertEqual(req.call_args.args[0],'https://example.test/v1/responses')
        payload=req.call_args.kwargs['payload']
        self.assertEqual(payload['tools'],[{'type':'web_search'}])
        self.assertEqual(payload['tool_choice'],'required')
        self.assertFalse(payload['store'])
        self.assertNotIn('response_format',payload)
        self.assertEqual(endpoint('https://example.test/v1/chat/completions','/responses'),'https://example.test/v1/responses')

    @patch.dict(os.environ, {'LLM_BASE_URL':'https://api.deepseek.com/v1', 'LLM_API_KEY':'secret-probe',
                             'LLM_MODEL':'deepseek-flash', 'LLM_REASONING_EFFORT':'low'})
    def test_function_tool_replies_to_calls_skipped_by_budget(self):
        calls = [
            {'id':f'call_{i}', 'type':'function',
             'function':{'name':'web_search', 'arguments':json.dumps({'query':f'graph paper {i}'})}}
            for i in range(3)
        ]
        first = {'choices':[{'message':{'role':'assistant', 'content':'',
                                        'reasoning_content':'search', 'tool_calls':calls}}]}
        final = {'choices':[{'message':{'role':'assistant', 'content':json.dumps({'candidates':[], 'notes':''})}}]}
        options={'max_tool_calls_per_round':1, 'max_output_tokens':2000}
        agent=WebResearchAgent({'reasoning_effort':'low'}, options, 'instructions')
        with patch.object(agent, '_local_scholar_search', return_value={'query':'graph paper 0', 'results':[], 'errors':[]}), \
             patch('gnn_digest.agent.get_json', side_effect=[first, final]) as req:
            result=agent.search({'research_request':'find papers'},30)
        self.assertEqual(result['status'], 'completed')
        second_payload=req.call_args_list[1].kwargs['payload']
        tool_messages=[m for m in second_payload['messages'] if m.get('role') == 'tool']
        self.assertEqual([m['tool_call_id'] for m in tool_messages], ['call_0','call_1','call_2'])
        self.assertEqual(len(result['tool_candidates']), 0)

    def test_rejected_candidate_feedback_then_success_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, config, args=self.setup_root(tmp)
            bad={**candidate(2),'url':'https://evil.test/paper'}
            with patch('gnn_digest.agent.WebResearchAgent.search',side_effect=[response([bad]),response([conference_candidate()])]) as agent, patch('gnn_digest.verification.fetch_page',return_value=conference_html()), patch('gnn_digest.agent.load_methods',side_effect=mock_methods), patch('gnn_digest.llm.get_json',return_value={'choices':[{'message':{'content':json.dumps(answer())}}]}):
                self.assertEqual(run(args),0)
            self.assertTrue(agent.call_args_list[1].args[0]['feedback'])
            report=read_json(root/'data/last_run.json',{})
            self.assertEqual(report['returned'],1)
            self.assertEqual(len(report['rounds']),2)
            self.assertEqual(len(report['rejections']),1)
            with patch('gnn_digest.agent.WebResearchAgent.search',return_value=response([conference_candidate()])), patch('gnn_digest.verification.fetch_page',return_value=conference_html()), patch('gnn_digest.agent.load_methods',side_effect=mock_methods), patch('gnn_digest.llm.get_json') as summary:
                self.assertEqual(run(args),0)
                summary.assert_not_called()
            saved=read_json(root/'data/papers.json',{})['papers']
            self.assertEqual(len(saved),1)
            self.assertEqual(saved[0]['topics'],['GNN'])
            self.assertNotIn('secret-probe',(root/'data/last_run.json').read_text())

    def test_no_actual_search_or_incomplete_response_preserves_archive(self):
        for r in [response([candidate()],actions=False),response([candidate()],status='incomplete')]:
            with self.subTest(response=r),tempfile.TemporaryDirectory() as tmp:
                root, config, args=self.setup_root(tmp)
                write_json(root/'data/papers.json',{'schema_version':1,'papers':[]})
                before=(root/'data/papers.json').read_bytes()
                with patch('gnn_digest.agent.WebResearchAgent.search',return_value=r),patch('gnn_digest.verification.fetch_page') as fetch:
                    code=search(root,config,args)
                self.assertIn(code,(2,4))
                fetch.assert_not_called()
                self.assertEqual(before,(root/'data/papers.json').read_bytes())

    def test_irrelevant_summary_not_published_as_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, config, args=self.setup_root(tmp)
            a={'relevant':False,'topics':[],'topic_evidence':{},'keywords':[],'method':'','confidence':'low','evidence':[]}
            with patch('gnn_digest.agent.WebResearchAgent.search',return_value=response([conference_candidate()])),patch('gnn_digest.verification.fetch_page',return_value=conference_html()),patch('gnn_digest.agent.load_methods',side_effect=mock_methods),patch('gnn_digest.llm.get_json',return_value={'choices':[{'message':{'content':json.dumps(a)}}]}):
                self.assertEqual(search(root,config,args),4)
            self.assertEqual(read_json(root/'data/search_results.json',{})['papers'],[])

    def test_merge_preserves_archive_id_but_refreshes_verified_summary(self):
        with patch('gnn_digest.verification.fetch_page',return_value=html()):
            new=verify_candidate(candidate(),date(2026,9,20),date(2026,9,26))
        old={**new,'id':'historic-id','status':'pending','keywords':[],'method':''}
        old.pop('verification')
        new.update(answer(),status='ready',summary_input_hash=content_hash(new))
        merged=merge_records([old,new])
        self.assertEqual(len(merged),1)
        self.assertEqual(merged[0]['id'],'historic-id')
        self.assertEqual(merged[0]['status'],'ready')
        self.assertEqual(merged[0]['topics'],['GNN'])


if __name__=='__main__':
    unittest.main()
