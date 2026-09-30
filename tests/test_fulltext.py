import unittest
from unittest.mock import patch

from gnn_digest.fulltext import Sections, method_sections, load_methods
from gnn_digest.llm import validate_summary
from gnn_digest.models import content_hash
from gnn_digest.verification import VerificationError, verify_directory_match


class FulltextTests(unittest.TestCase):
    def test_html_method_boundaries_exclude_navigation_and_experiments(self):
        parser = Sections()
        parser.feed('<nav>methods listed below</nav><h2>3 Methodology</h2><p>' +
                    'We construct graph representations and aggregate neighbor messages. ' * 12 +
                    '</p><h2>4 Experiments</h2><p>Results should not enter methods.</p>')
        methods = method_sections(''.join(parser.parts))
        self.assertIn('aggregate neighbor', methods)
        self.assertNotIn('Results should', methods)
        self.assertNotIn('listed below', methods)

    def test_abstract_or_footer_mentions_do_not_become_method_section(self):
        with self.assertRaises(VerificationError):
            method_sections('Abstract\nWe propose methods for graphs.\nmethods listed below:\n' + 'text ' * 200)

    def test_named_model_section_is_recognized(self):
        methods = method_sections('## 4 Graph Dynamics Model\n' + 'We train graph representations. ' * 25 + '\n## 6 Experiments\nresults')
        self.assertIn('Graph Dynamics Model', methods)
        self.assertNotIn('results', methods)

    def test_problem_formulation_and_method_section(self):
        methods = method_sections('3 Problem formulation and method\n' + 'We estimate graph connectivity. ' * 25 + '\n4 Experiments\nresults')
        self.assertIn('graph connectivity', methods)
        self.assertNotIn('results', methods)

    def test_pdf_fallback_and_method_cache_hash(self):
        text = 'Graph representation learning\n3 Method\n' + 'We train graph representations. ' * 25 + '\n4 Experiments\nresults'
        p = {'title':'Graph representation learning','abstract':'Abstract','arxiv_id':'2609.00001','pdf_url':'https://arxiv.org/pdf/2609.00001'}
        before = content_hash(p)
        with patch('gnn_digest.fulltext.read_document', side_effect=[VerificationError('HTML missing'), (text, 'pdf')]) as read:
            load_methods(p)
        self.assertEqual(read.call_count, 2)
        self.assertEqual(p['fulltext_source']['format'], 'pdf')
        self.assertNotEqual(content_hash(p), before)

    def test_summary_character_limit_is_200(self):
        v = {'relevant':True,'confidence':'high','keywords':['a','b','c','d','e'],
             'method':'**图方法**'+'图'*197,'evidence':['We train graph representations.']}
        validate_summary(v, 'We train graph representations.')
        with self.assertRaises(ValueError):
            validate_summary({**v,'method':'图'*201}, 'We train graph representations.')

    def test_arbitrary_directory_cannot_prove_conference(self):
        with self.assertRaises(VerificationError):
            verify_directory_match('Some Graph Neural Network Paper', 'https://evil.test/list')

    def test_audited_directory_requires_exact_title(self):
        class Response:
            url = 'https://sigir2025.dei.unipd.it/proceedings.html'
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'<html><body><p>Graph Learning for Recommender Systems</p></body></html>'
        with patch('gnn_digest.verification.urllib.request.urlopen', return_value=Response()):
            self.assertEqual(verify_directory_match('Graph Learning for Recommender Systems', Response.url)['status'], 'title_listed_only')
            with self.assertRaises(VerificationError):
                verify_directory_match('Graph Learning for Different Recommender Systems', Response.url)
