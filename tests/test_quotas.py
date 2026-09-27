import json
import os
import shutil
import tempfile
import unittest
from argparse import Namespace
from collections import Counter
from itertools import product
from pathlib import Path
from unittest.mock import patch

from gnn_digest.agent import search, source_quotas, select_balanced, verified_route
from gnn_digest.cli import ROOT
from gnn_digest.models import identity_keys, merge_records, paper
from gnn_digest.storage import read_json, write_json
from test_agent import ABSTRACT, answer, response, mock_methods


def record(name, route, day=25, status='ready'):
    url = (f'https://arxiv.org/abs/2609.{name:05d}' if route == 'arxiv'
           else f'https://aclanthology.org/2026.emnlp-long.{name}/')
    p = paper(source=route, source_id=str(name), title=f'Graph Neural Network Method {name}',
              abstract=ABSTRACT, published=f'2026-09-{day:02d}', url=url)
    p.update(status=status, verification={'url':url}, display_date=p['published'],
             venue_label='arXiv' if route == 'arxiv' else 'EMNLP',
             date_basis='arxiv_first_submission' if route == 'arxiv' else 'conference_publication')
    return p


class QuotaSelectionTests(unittest.TestCase):
    def test_counts_and_odd_conference_extra(self):
        for n in range(1, 21):
            q = source_quotas(n)
            self.assertEqual(sum(q.values()), n)
            self.assertEqual(q['conference']-q['arxiv'], n % 2)

    def test_ten_results_five_each_newest_within_bucket(self):
        pool = [record(i, route, i) for route in ('conference', 'arxiv') for i in range(1, 11)]
        # Distinct titles for each source in this test.
        for p in pool:
            p['title'] += verified_route(p)
        selected = select_balanced(pool, source_quotas(10))
        self.assertEqual(Counter(p['selection_bucket'] for p in selected), {'conference':5,'arxiv':5})
        self.assertEqual([p['display_date'] for p in selected], sorted([p['display_date'] for p in selected], reverse=True))
        self.assertTrue(all(p['published'] >= '2026-09-06' for p in selected))

    def test_neither_bucket_backfills_the_other(self):
        for route in ('conference','arxiv'):
            selected = select_balanced([record(i, route) for i in range(12)], source_quotas(10))
            self.assertEqual(len(selected), 5)
            self.assertEqual({p['selection_bucket'] for p in selected}, {route})

    def test_dual_routes_reassigned_to_fill_both_quotas(self):
        dual = [record(1, 'conference', 24), record(1, 'arxiv', 25)]
        for extra_route in ('conference', 'arxiv'):
            selected = select_balanced(dual + [record(2, extra_route, 23)], source_quotas(2))
            self.assertEqual(Counter(p['selection_bucket'] for p in selected), {'conference':1,'arxiv':1})
            self.assertFalse(identity_keys(selected[0]) & identity_keys(selected[1]))
            assigned = next(p for p in selected if p['title'].endswith('1'))
            self.assertEqual(assigned['selection_bucket'], 'arxiv' if extra_route == 'conference' else 'conference')
            self.assertEqual(assigned['display_date'], '2026-09-25' if extra_route == 'conference' else '2026-09-24')

    def test_archive_alias_bridge_deduplicates_without_lending_eligibility(self):
        c, a = record(1, 'conference'), record(2, 'arxiv')
        bridge = {**record(3,'conference'), 'identity_aliases':sorted(identity_keys(c) | identity_keys(a))}
        selected = select_balanced([c,a], source_quotas(2), archive=[bridge])
        self.assertEqual(len(selected), 1)
        selected = select_balanced([a], source_quotas(2), archive=[bridge])
        self.assertEqual([p['selection_bucket'] for p in selected], ['arxiv'])

    def test_verification_not_model_label_controls_route(self):
        p = {**record(1,'arxiv'), 'venue_label':'EMNLP', 'selection_bucket':'conference'}
        self.assertEqual(verified_route(p), 'arxiv')
        self.assertEqual(select_balanced([p],source_quotas(1)), [])
        p['date_basis'] = 'conference_publication'
        self.assertIsNone(verified_route(p))

    def test_failed_routes_do_not_hide_ready_alternative(self):
        pool = [record(1,'conference',status='failed'), record(1,'arxiv'), record(2,'conference',status='pending')]
        self.assertEqual(len(select_balanced(pool,source_quotas(2),ready_only=True)),1)
        self.assertEqual(len(select_balanced(pool,source_quotas(2))),2)

    def test_small_pools_maximize_slots_without_duplicates(self):
        for c, a, d, qc, qa in product(range(4), range(4), range(4), range(1,4), range(1,4)):
            pool = ([record(i,'conference') for i in range(c)] +
                    [record(10+i,'arxiv') for i in range(a)] +
                    [record(20+i,r) for i in range(d) for r in ('conference','arxiv')])
            selected = select_balanced(pool, {'conference':qc,'arxiv':qa})
            counts = Counter(p['selection_bucket'] for p in selected)
            self.assertLessEqual(counts['conference'], qc)
            self.assertLessEqual(counts['arxiv'], qa)
            self.assertEqual(len(selected), min(c+a+d,qc+qa,c+d+qa,a+d+qc))
            self.assertEqual(len(merge_records(selected)),len(selected))


@patch.dict(os.environ, {'LLM_BASE_URL':'https://example.test/v1','LLM_API_KEY':'secret-probe','LLM_MODEL':'test'})
class QuotaSearchTests(unittest.TestCase):
    def execute(self, root, rounds, limit, archive=()):
        shutil.copytree(ROOT/'prompts',root/'prompts')
        config = read_json(ROOT/'config.json',{})
        config['search_agent'].update(max_rounds=len(rounds), max_seconds=60)
        write_json(root/'data/papers.json',{'schema_version':1,'papers':list(archive)})
        args = Namespace(no_llm=False,limit=limit,days=14,until='2026-09-26')
        by_url = {p['verification']['url']:p for ps in rounds for p in ps}
        responses = [response([{'title':p['title'],'url':p['verification']['url']} for p in ps]) for ps in rounds]
        with patch('gnn_digest.agent.WebResearchAgent.search',side_effect=responses) as agent, \
             patch('gnn_digest.agent.verify_candidate',side_effect=lambda c,*a,**kw:dict(by_url[c['url']])), \
             patch('gnn_digest.agent.load_methods',side_effect=mock_methods), \
             patch('gnn_digest.llm.get_json',return_value={'choices':[{'message':{'content':json.dumps(answer())}}]}) as summary:
            code = search(root,config,args)
        return code, read_json(root/'data/search_results.json',{}), agent, summary

    def test_arxiv_flood_then_conference_feedback_fills_ten(self):
        with tempfile.TemporaryDirectory() as tmp:
            rounds = [[record(i,'arxiv',status='pending') for i in range(10)],
                      [record(20+i,'conference',status='pending') for i in range(5)]]
            code, result, agent, summary = self.execute(Path(tmp),rounds,10)
            self.assertEqual(code,0)
            self.assertEqual(summary.call_count,10)
            self.assertEqual(result['report']['source_quotas'],{'conference':5,'arxiv':5})
            self.assertEqual(Counter(p['selection_bucket'] for p in result['papers']),{'conference':5,'arxiv':5})
            context = agent.call_args_list[1].args[0]
            self.assertEqual(context['search_focus'],['conference'])
            self.assertEqual(context['quota_progress']['conference']['shortfall'],5)
            saved=read_json(Path(tmp)/'data/papers.json',{})['papers']
            self.assertTrue(all('selection_bucket' not in p for p in saved))

    def test_arxiv_only_returns_partial_and_records_conference_shortage(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, result, _, summary = self.execute(Path(tmp),[[record(i,'arxiv',status='pending') for i in range(10)]],10)
            self.assertEqual(code,4)
            self.assertEqual(len(result['papers']),5)
            self.assertEqual(summary.call_count,5)
            self.assertEqual(result['report']['quota_progress']['conference'],{'requested':5,'returned':0,'shortfall':5})

    def test_odd_three_and_cross_source_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = [record(1,'conference',status='pending'),record(1,'arxiv',status='pending'),
                    record(2,'conference',status='pending'),record(3,'arxiv',status='pending')]
            code, result, _, summary = self.execute(Path(tmp),[pool],3)
            self.assertEqual(code,0)
            self.assertEqual(Counter(p['selection_bucket'] for p in result['papers']),{'conference':2,'arxiv':1})
            self.assertEqual(len(set(p['id'] for p in result['papers'])),3)
            self.assertEqual(summary.call_count,3)

    def test_archive_alias_bridge_cannot_produce_duplicate_result_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, a = record(1,'conference',status='pending'), record(2,'arxiv',status='pending')
            bridge = {**record(3,'conference',status='pending'),
                      'identity_aliases':sorted(identity_keys(c) | identity_keys(a))}
            code, result, _, _ = self.execute(Path(tmp),[[c,a]],2,archive=[bridge])
            self.assertEqual(code,4)
            self.assertEqual(len(result['papers']),1)
            self.assertEqual(result['papers'][0]['id'],bridge['id'])
            self.assertEqual(result['report']['deduplicated'],1)


if __name__ == '__main__':
    unittest.main()
