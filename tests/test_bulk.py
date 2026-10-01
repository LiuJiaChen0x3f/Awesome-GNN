import tempfile
import json
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from gnn_digest.agent import source_windows
from gnn_digest.bulk import bulk_targets, conference_schedule, bulk_search
from gnn_digest.verification import publication_date, conference_edition, VerificationError, VENUES, verify_candidate, verify_crossref, vldb_pdf_index, venue_abbreviation
from gnn_digest.storage import write_json, read_json
from gnn_digest.fulltext import find_arxiv_fulltext
from gnn_digest.models import clean
from test_quotas import record


class BulkTests(unittest.TestCase):
    def test_www_on_web_alias_excludes_companion(self):
        self.assertEqual(venue_abbreviation('Proceedings of the ACM on Web Conference 2025'),'WWW')
        self.assertEqual(venue_abbreviation('Companion Proceedings of the ACM on Web Conference 2025'),'')

    def test_pdf_surrogate_pairs_are_preserved_as_valid_unicode(self):
        self.assertEqual(clean('\ud835\udc9c'),'\U0001d49c')
        self.assertEqual(clean('graph\ud835 text'),'graph\ufffd text')
        clean('graph\ud835 text').encode('utf-8')

    def test_vldb_structured_index_uses_exact_title_and_original_pdf(self):
        vldb_pdf_index.cache_clear()
        data={'props':{'papers':[{'title':'Unpublished','pdf':''},{'title':'Graph Shift','pdf':'https://www.vldb.org/pvldb/vol19/p1-test.pdf'}]}}
        raw='<script id="__NEXT_DATA__" type="application/json">'+json.dumps(data)+'</script>'
        with patch('gnn_digest.verification.fetch_page',return_value=raw):
            self.assertEqual(vldb_pdf_index('19')['graphshift'],'https://www.vldb.org/pvldb/vol19/p1-test.pdf')
        vldb_pdf_index.cache_clear()

    def test_arxiv_shortfall_only_transfers_to_conference(self):
        self.assertEqual(bulk_targets(100),{'conference':80,'arxiv':20})
        self.assertEqual(bulk_targets(100,0),{'conference':100,'arxiv':0})
        self.assertEqual(bulk_targets(100,7),{'conference':93,'arxiv':7})

    def test_scope_covers_every_allowed_venue_and_both_editions(self):
        scopes=conference_schedule([2026,2025])
        self.assertEqual({s['venue'] for s in scopes},set(VENUES))
        self.assertEqual(len(scopes),2*len(VENUES)-1)
        self.assertNotIn({'bucket':'conference','venue':'ICCV','year':2026},scopes)

    def test_fixed_start_dates_and_cli_lookback_override(self):
        config={'search_windows':{'conference_since':'2025-01-01','arxiv_since':'2026-01-01'}}
        w=source_windows(config,Namespace(days=None),date(2026,9,29))
        self.assertEqual(w['arxiv']['since'],'2026-01-01')
        self.assertEqual(w['conference']['since'],'2025-01-01')
        w=source_windows(config,Namespace(days=7),date(2026,9,29))
        self.assertEqual(w['conference']['since'],'2026-09-23')
        rolling = source_windows({'search_windows':{'conference_since':'2025-01-01',
                                                    'arxiv_months':2}}, Namespace(days=None), date(2026,9,29))
        self.assertEqual(rolling['arxiv']['since'], '2026-07-29')

    def test_partial_dates_do_not_invent_months_or_days(self):
        for raw, precision in [('2025','year'),('2025/07','month'),('2026/02/01','day')]:
            value,p=publication_date(raw,date(2025,1,1),date(2026,9,29))
            self.assertEqual(value,raw.replace('/','-')); self.assertEqual(p,precision)
        with self.assertRaises(VerificationError):
            publication_date('2026/09',date(2026,9,16),date(2026,9,29))
        with self.assertRaises(VerificationError):
            publication_date('2027',date(2025,1,1),date(2026,9,29))
        self.assertEqual(publication_date('2026/7',date(2025,1,1),date(2026,9,29)),('2026-07','month'))
        self.assertEqual(conference_edition('https://proceedings.neurips.cc/paper_files/paper/2025/hash/a-Abstract.html','NeurIPS','2026-08-14'),2025)
        self.assertEqual(conference_edition('https://openaccess.thecvf.com/content/CVPR2025/html/a.html','CVPR','2025'),2025)

    def test_sweep_preserves_results_deduplicates_and_checkpoints_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            config={'search_agent':{},'bulk_search':{'arxiv_rounds':1,'conference_passes':1},
                    'search_windows':{'conference_since':'2025-01-01','arxiv_since':'2026-01-01'}}
            calls=[]
            def batch(root, child, args):
                scope=child['_search_scope']; calls.append(scope)
                papers=[]
                if scope['bucket']=='conference':
                    p=record(len(calls),'conference'); p['id']='stable-archive-id'; p['selection_bucket']='conference'; papers=[p]
                write_json(root/'data/papers.json',{'papers':papers,'schema_version':1})
                write_json(root/'data/search_results.json',{'papers':papers,'report':{
                    'sources':{'web_search':{'ok':True}},'rounds':[],'llm_processed':len(papers)}})
                return 4
            with patch('gnn_digest.agent.search',side_effect=batch):
                code=bulk_search(root,config,Namespace(limit=100,until='2026-09-29',days=None))
            result=read_json(root/'data/last_run.json',{})
            self.assertEqual(code,4)
            self.assertTrue(result['llm_enabled'])
            self.assertFalse(result['in_progress'])
            self.assertEqual(result['source_quotas'],{'conference':100,'arxiv':0})
            self.assertEqual(result['returned'],1)
            self.assertEqual(result['unvisited_conference_scopes'],[])
            self.assertFalse((root/'data/pipeline.lock').exists())
            self.assertEqual(len(calls),1+len(conference_schedule([2026,2025])))
            with patch('gnn_digest.agent.search') as again:
                self.assertEqual(bulk_search(root,config,Namespace(limit=100,until='2026-09-29',days=None,resume=True)),4)
                again.assert_not_called()
            config['bulk_search']['conference_passes']=2
            with patch('gnn_digest.agent.search',side_effect=batch) as fill_pass:
                self.assertEqual(bulk_search(root,config,Namespace(limit=100,until='2026-09-29',days=None,resume=True)),4)
                self.assertEqual(fill_pass.call_count,len(conference_schedule([2026,2025])))
                self.assertTrue(all(c.args[1]['_search_scope']['pass']==2 for c in fill_pass.call_args_list))

    def test_aaai_and_neurips_main_track_metadata_adapters(self):
        c={'title':'Graph Shift','url':'https://ojs.aaai.org/index.php/AAAI/article/view/123'}
        html='<meta name="citation_title" content="Graph Shift"><meta name="citation_journal_title" content="Proceedings of the AAAI Conference on Artificial Intelligence"><meta name="citation_date" content="2025/04/11"><p>AAAI-25 Technical Tracks</p>'
        with patch('gnn_digest.verification.fetch_page',return_value=html):
            p=verify_candidate(c,date(2025,1,1),date(2026,9,29))
            self.assertEqual(p['venue_label'],'AAAI')
        c['url']='https://proceedings.neurips.cc/paper_files/paper/2025/hash/abc-Abstract-Conference.html'
        html=html.replace('Proceedings of the AAAI Conference on Artificial Intelligence','Advances in Neural Information Processing Systems')
        with patch('gnn_digest.verification.fetch_page',return_value=html):
            self.assertEqual(verify_candidate(c,date(2025,1,1),date(2026,9,29))['venue_label'],'NeurIPS')
            c['url']=c['url'].replace('-Conference','-Creative_AI_Track')
            with self.assertRaises(VerificationError): verify_candidate(c,date(2025,1,1),date(2026,9,29))
        c['url']=c['url'].replace('-Creative_AI_Track','-Datasets_and_Benchmarks_Track')
        with patch('gnn_digest.verification.fetch_page',return_value=html):
            with self.assertRaises(VerificationError): verify_candidate(c,date(2025,1,1),date(2026,9,29))
        with patch('gnn_digest.verification.fetch_page',return_value=html+'<p>Datasets and Benchmarks Track</p>'):
            p=verify_candidate(c,date(2025,1,1),date(2026,9,29))
            self.assertEqual(p['verification']['track'],'Datasets and Benchmarks')

    def test_crossref_requires_matching_title_proceedings_type_and_main_venue(self):
        c={'title':'Graph Shift','url':'https://dl.acm.org/doi/10.1145/123.456'}
        value={'type':'proceedings-article','title':['Graph Shift'],'container-title':['Proceedings of the ACM Web Conference 2025'],'published':{'date-parts':[[2025,4,28]]}}
        with patch('gnn_digest.http.get_json',return_value={'message':value}):
            self.assertEqual(verify_crossref(c,date(2025,1,1),date(2026,9,29),10)['venue_label'],'WWW')
            value['type']='journal-article'
            with self.assertRaises(VerificationError): verify_crossref(c,date(2025,1,1),date(2026,9,29),10)
            value['type']='proceedings-article'; value['container-title']=['Companion Proceedings of the ACM Web Conference 2025']
            with self.assertRaises(VerificationError): verify_crossref(c,date(2025,1,1),date(2026,9,29),10)

    def test_icml_uses_official_structured_record_without_requiring_openreview_api(self):
        record={'@type':'CreativeWork','name':'Graph Shift','creditText':'ICML 2026',
                'datePublished':'2026-05-05','author':[{'name':'A Researcher'}]}
        c={'title':'Graph Shift','url':'https://icml.cc/virtual/2026/poster/66227'}
        def page():
            return '<script type="application/ld+json">'+json.dumps(record)+'</script><a href="https://openreview.net/forum?id=abc">Paper</a>'
        with patch('gnn_digest.verification.fetch_page',side_effect=lambda *a,**k:page()):
            p=verify_candidate(c,date(2025,1,1),date(2026,9,29))
            self.assertEqual(p['published'],'2026-05-05')
            self.assertEqual(p['date_basis'],'conference_program_publication')
            self.assertEqual(p['conference_year'],2026)
            record['creditText']='ICML Workshop 2026'
            with self.assertRaises(VerificationError):verify_candidate(c,date(2025,1,1),date(2026,9,29))

    def test_fulltext_lookup_requires_exact_identity_then_independent_page_verification(self):
        xml=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Different Graph</title><id>http://arxiv.org/abs/2601.12345v2</id></entry></feed>'
        with patch('gnn_digest.http.request',return_value=xml),patch('gnn_digest.verification.verify_candidate') as verify:
            self.assertIsNone(find_arxiv_fulltext('Graph Shift'))
            verify.assert_not_called()
        with patch('gnn_digest.http.request',return_value=xml.replace(b'Different Graph',b'Graph Shift')),patch('gnn_digest.verification.verify_candidate',return_value={'arxiv_id':'2601.12345'}) as verify:
            self.assertEqual(find_arxiv_fulltext('Graph Shift')['arxiv_id'],'2601.12345')
            self.assertEqual(verify.call_args.args[0]['url'],'https://arxiv.org/abs/2601.12345')

    def test_journal_style_proceedings_need_exact_official_program_membership(self):
        c={'title':'Graph Shift Representation Learning','url':'https://doi.org/10.14778/123.456','_conference_year':2026}
        value={'type':'journal-article','title':[c['title']],'container-title':['Proceedings of the VLDB Endowment'],
               'published':{'date-parts':[[2026,4]]},'link':[{'URL':'https://www.vldb.org/pvldb/vol19/test.pdf'}]}
        with patch('gnn_digest.http.get_json',return_value={'message':value}),patch('gnn_digest.verification.program_text',return_value='Official Program: '+c['title']):
            p=verify_crossref(c,date(2025,1,1),date(2026,9,29),10)
            self.assertEqual(p['venue_label'],'VLDB')
            self.assertEqual(p['conference_year'],2026)
            self.assertEqual(p['publication_type'],'conference-associated-journal')
            self.assertEqual(p['pdf_url'],'https://www.vldb.org/pvldb/vol19/test.pdf')
        with patch('gnn_digest.http.get_json',return_value={'message':value}),patch('gnn_digest.verification.program_text',return_value='Unrelated Program'):
            with self.assertRaises(VerificationError):verify_crossref(c,date(2025,1,1),date(2026,9,29),10)


if __name__=='__main__': unittest.main()
