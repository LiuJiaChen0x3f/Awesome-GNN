from summary_fixtures import VALID_METHOD
import copy
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from gnn_digest.cli import run, ROOT
from gnn_digest.llm import Summarizer, validate_summary
from gnn_digest.models import paper, merge_records, content_hash, within_window
from gnn_digest.sources import reconstruct_abstract
from gnn_digest.storage import read_json, write_json, export_site

ABSTRACT = 'We propose a graph neural network with attention-based message passing for molecular property prediction.'


def sample(**kwargs):
    defaults = dict(source='arxiv', source_id='2609.12345', title='A Graph Neural Network', abstract=ABSTRACT, published='2026-09-25', arxiv='2609.12345v2', url='https://arxiv.org/abs/2609.12345')
    defaults.update(kwargs)
    return paper(**defaults)


def answer():
    return {'relevant': True, 'keywords': ['图神经网络', '注意力机制', '消息传递', '分子图', '属性预测'], 'method': VALID_METHOD, 'confidence': 'high', 'evidence': ['attention-based message passing for molecular property prediction']}


class DedupTests(unittest.TestCase):
    def test_versions_and_repeated_run(self):
        a=sample(); b=sample(source_id='2609.12345v3', arxiv='2609.12345v3')
        merged=merge_records([a,b])
        self.assertEqual(len(merged),1)
        self.assertEqual(merge_records(merged+[a,b]),merged)

    def test_doi_title_and_transitive_bridge(self):
        a=sample(title='Graph: Learning!',doi='https://doi.org/10.1234/ABC')
        b=sample(source='crossref',source_id='different',arxiv='',title='graph learning',doi='10.1234/abc')
        c=sample(source='openalex',source_id='w1',arxiv='',title='Another title',doi='10.9999/x')
        bridge=sample(source='crossref',source_id='bridge',arxiv='',title='Another title',doi='10.1234/abc')
        merged=merge_records([a,b,c,bridge])
        self.assertEqual(len(merged),1)
        self.assertEqual(len(merged[0]['sources']),4)

    def test_different_titles_stay_separate(self):
        self.assertEqual(len(merge_records([sample(arxiv=''),sample(source_id='b', arxiv='', title='Another Graph Neural Network')])),2)

    def test_cache_survives_source_merge(self):
        a=sample();a.update(status='ready',summary_input_hash=content_hash(a),keywords=answer()['keywords'],method=answer()['method'])
        b=sample(source='crossref',source_id='x',arxiv='')
        self.assertEqual(merge_records([a,b])[0]['status'],'ready')

    def test_changed_abstract_invalidates_cache(self):
        a=sample();a.update(status='ready',summary_input_hash=content_hash(a))
        b=sample(abstract=ABSTRACT+' Additional approach details are presented.')
        self.assertEqual(merge_records([a,b])[0]['status'],'pending')

    def test_window_rejects_future_and_missing_dates(self):
        self.assertTrue(within_window(sample(),date(2026,9,20),date(2026,9,26)))
        self.assertFalse(within_window(sample(published='2026-10-01'),date(2026,9,20),date(2026,9,26)))
        self.assertFalse(within_window(sample(published=''),date(2026,9,20),date(2026,9,26)))

    def test_identity_alias_survives_across_runs(self):
        a=sample(title='Old Graph Title',doi='10.1111/a',arxiv='')
        b=sample(source='crossref',source_id='b',title='Old Graph Title',doi='10.2222/b',arxiv='')
        first=merge_records([a,b])
        c=sample(source='openalex',source_id='c',title='Changed Graph Title',doi='10.2222/b',arxiv='')
        self.assertEqual(len(merge_records(first+[c])),1)

    def test_newer_shorter_abstract_wins(self):
        a=sample(abstract=ABSTRACT+' Old inaccurate extra detail.')
        b=sample(abstract=ABSTRACT,updated='2026-09-26')
        self.assertEqual(merge_records([a,b])[0]['abstract'],ABSTRACT)


class LLMTests(unittest.TestCase):
    def test_good_response(self):
        self.assertEqual(validate_summary(answer(),ABSTRACT)['keywords'],answer()['keywords'])

    def test_bad_output(self):
        for change in [{'keywords':['a']*5},{'method':'长'*201},{'method':'English only'},{'evidence':['This is not in the abstract']},{'relevant':'true'},{'confidence':'low'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_summary({**answer(),**change},ABSTRACT)
        self.assertEqual(validate_summary({**answer(),'keywords':['GNN','注意力','消息传递','分子图']}, ABSTRACT)['keywords'],
                         ['GNN','注意力','消息传递','分子图'])

    @patch.dict(os.environ,{'LLM_BASE_URL':'https://example.test/v1','LLM_API_KEY':'secret','LLM_MODEL':'test'})
    def test_repair_and_cache(self):
        engine=Summarizer({'attempts':2,'temperature':0.1,'max_tokens':900,'timeout':1},'prompt')
        p=sample()
        responses=[{'choices':[{'message':{'content':'not-json'}}]}, {'choices':[{'message':{'content':json.dumps(answer())}}]}]
        with patch('gnn_digest.llm.get_json',side_effect=responses) as mocked:
            engine.summarize(p)
            self.assertEqual(mocked.call_count,2)
        self.assertEqual(p['status'],'ready');self.assertTrue(engine.cached(p))

    @patch.dict(os.environ,{'LLM_BASE_URL':'https://example.test/v1','LLM_API_KEY':'secret','LLM_MODEL':'test'})
    def test_failure_no_invented_summary(self):
        engine=Summarizer({'attempts':2,'temperature':0.1,'max_tokens':900,'timeout':1},'prompt')
        p=sample()
        with patch('gnn_digest.llm.get_json',side_effect=TimeoutError('secret')):
            engine.summarize(p)
        self.assertEqual(p['status'],'failed');self.assertEqual(p['keywords'],[]);self.assertNotIn('secret',json.dumps(p))

    @patch.dict(os.environ,{'LLM_BASE_URL':'https://example.test/v1','LLM_API_KEY':'secret','LLM_MODEL':'test','LLM_REASONING_EFFORT':'medium'})
    def test_reasoning_change_invalidates_cache(self):
        engine=Summarizer({'attempts':1,'temperature':None,'max_tokens':4096,'timeout':1},'prompt')
        p=sample()
        with patch('gnn_digest.llm.get_json',return_value={'choices':[{'message':{'content':json.dumps(answer())}}]}):
            engine.summarize(p)
        self.assertTrue(engine.cached(p))
        engine.reasoning_effort='high'
        self.assertFalse(engine.cached(p))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        methods = patch('gnn_digest.cli.load_methods', side_effect=lambda p, **kw: p.update(method_text=ABSTRACT, fulltext_source={'url':'https://arxiv.org/pdf/2609.12345','format':'pdf'}))
        methods.start()
        self.addCleanup(methods.stop)

    def setup_root(self, temporary):
        root=Path(temporary);(root/'prompts').mkdir()
        (root/'prompts/summarize.zh.txt').write_text('prompt')
        config=json.loads((ROOT/'config.json').read_text());config['sources']={'arxiv':True,'crossref':True}
        write_json(root/'config.json',config)
        return root

    def args(self,root,command='run'):
        return Namespace(root=str(root),config=None,command=command,no_llm=True,until='2026-09-26',days=None)

    def test_partial_source_failure_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp)
            with patch.dict('gnn_digest.cli.FETCHERS',{'arxiv':lambda *a:([sample()],{'mode':'api'}),'crossref':lambda *a:(_ for _ in ()).throw(TimeoutError())}):
                self.assertEqual(run(self.args(root)),0)
                self.assertEqual(run(self.args(root)),0)
            saved=read_json(root/'data/papers.json',{})
            self.assertEqual(len(saved['papers']),1)
            public=read_json(root/'site/data/papers.json',{})
            self.assertNotIn('abstract',public['papers'][0])
            self.assertFalse(public['report']['sources']['crossref']['ok'])

    def test_static_export_includes_new_archive_paper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            p=sample(title='New Rendered Graph Paper')
            p.update(status='ready', keywords=['GNN'], method='通过消息传递学习图表示。')
            p['full_text']='private full text must stay out of the static index'
            p['fulltext_source']={'scope':'full_text','url':'https://arxiv.org/pdf/2609.12345','format':'pdf'}
            export_site([p], {'finished_at':'2026-09-27T00:00:00+00:00'}, root/'site')
            public=read_json(root/'site/data/papers.json',{})
            self.assertEqual([item['title'] for item in public['papers']], ['New Rendered Graph Paper'])
            self.assertEqual(public['papers'][0]['status'], 'ready')
            self.assertNotIn('full_text', public['papers'][0])
            self.assertEqual(public['generated_at'], '2026-09-27T00:00:00+00:00')

    def test_queries_are_forwarded_to_source_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp)
            captured=[]
            def fetch(config, *args):
                captured.append(config['queries'])
                return [sample()], {'mode':'test'}
            with patch.dict('gnn_digest.cli.FETCHERS', {'arxiv': fetch, 'crossref': lambda *a: ([], {'mode':'test'})}):
                self.assertEqual(run(self.args(root)), 0)
            self.assertEqual(captured, [read_json(root/'config.json', {})['queries']])

    def test_all_sources_failed_preserves_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp)
            write_json(root/'data/papers.json',{'schema_version':1,'papers':[sample()]})
            before=(root/'data/papers.json').read_bytes()
            fail=lambda *a:(_ for _ in ()).throw(TimeoutError())
            with patch.dict('gnn_digest.cli.FETCHERS',{'arxiv':fail,'crossref':fail}):
                self.assertEqual(run(self.args(root)),2)
            self.assertEqual((root/'data/papers.json').read_bytes(),before)

    def test_reconstruct_abstract(self):
        self.assertEqual(reconstruct_abstract({'graph':[1],'A':[0],'network':[2]}),'A graph network')

    @patch.dict(os.environ,{'LLM_BASE_URL':'https://example.test/v1','LLM_API_KEY':'secret','LLM_MODEL':'test'})
    def test_concurrent_results_checkpointed_and_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp)
            config=read_json(root/'config.json',{})
            config.update(max_llm_papers=2,llm_concurrency=2)
            write_json(root/'config.json',config)
            papers=[sample(source_id=str(i),arxiv='',title=f'Graph Network {i}') for i in range(4)]
            write_json(root/'data/papers.json',{'schema_version':1,'papers':papers})
            args=self.args(root,'summarize');args.no_llm=False
            with patch('gnn_digest.llm.get_json',return_value={'choices':[{'message':{'content':json.dumps(answer())}}]}) as mocked:
                self.assertEqual(run(args),0)
                self.assertEqual(mocked.call_count,2)
            saved=read_json(root/'data/papers.json',{})['papers']
            self.assertEqual(sum(p['status']=='ready' for p in saved),2)
            self.assertEqual(sum(p['status']=='pending' for p in saved),2)

    def test_local_http_llm_pipeline_and_cache(self):
        captured=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured.append((self.path,self.headers.get('Authorization'),json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                result={'choices':[{'message':{'content':json.dumps(answer())}}]}
                data=json.dumps(result).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def log_message(self,*args):
                pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'LLM_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1','LLM_API_KEY':'local-test-token','LLM_MODEL':'test-model'}):
                root=self.setup_root(tmp)
                write_json(root/'data/papers.json',{'schema_version':1,'papers':[sample()]})
                args=self.args(root,'summarize');args.no_llm=False
                self.assertEqual(run(args),0)
                self.assertEqual(run(args),0)
                public=read_json(root/'site/data/papers.json',{})
                self.assertEqual(public['papers'][0]['status'],'ready')
                self.assertEqual(len(public['papers'][0]['keywords']),5)
                self.assertLessEqual(len(public['papers'][0]['method']),200)
                self.assertEqual(len(captured),1)
                self.assertEqual(captured[0][0],'/v1/chat/completions')
                self.assertEqual(captured[0][1],'Bearer local-test-token')
                self.assertEqual(captured[0][2]['reasoning_effort'],'low')
                self.assertIn('max_completion_tokens',captured[0][2])
                self.assertNotIn('temperature',captured[0][2])
                self.assertNotIn('local-test-token',json.dumps(public))
        finally:
            server.shutdown();server.server_close();worker.join()


if __name__=='__main__':
    unittest.main()
