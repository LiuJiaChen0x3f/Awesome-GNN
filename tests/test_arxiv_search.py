import unittest
from datetime import date
from unittest.mock import patch

from gnn_digest.arxiv_search import model_arxiv_queries, search_html


class ArxivSearchTests(unittest.TestCase):
    def test_uses_model_search_direction_and_deduplicates(self):
        actions = [{'queries': ['site:arxiv.org/abs/ 2026 "text-attributed graphs"',
                                'site:arxiv.org/abs/2609 "graph domain generalization" arXiv']},
                   {'query': 'site:arxiv.org/abs/ 2026 "text-attributed graphs"'}]
        self.assertEqual(model_arxiv_queries(actions),
                         ['text-attributed graphs', 'graph domain generalization'])
        self.assertEqual(model_arxiv_queries([{'query':'site:arxiv.org/abs/260 2026 graph OOD -survey'}]),
                         ['graph OOD'])

    def test_parses_html_with_nested_title_and_filters_visible_date(self):
        page = '''<ul>
        <li class="arxiv-result"><p><a href="https://arxiv.org/abs/2609.12345">arXiv</a></p>
          <p class="title is-5"><span>Dynamic <b>Text-Attributed</b> Graphs</span></p>
          <p>Submitted 29 September, 2026</p></li>
        <li class="arxiv-result"><a href="https://arxiv.org/abs/2509.12345">arXiv</a>
          <p class="title">Old Graph Paper</p><p>Submitted 29 September, 2025</p></li>
        <li class="arxiv-result"><a href="https://evil.test/abs/2609.54321">wrong host</a>
          <p class="title">Untrusted Paper</p></li></ul>'''
        with patch('gnn_digest.arxiv_search.request', return_value=page.encode()) as fetch:
            results = search_html('text-attributed graphs', date(2026, 1, 1), date(2026, 9, 30))
        self.assertEqual(results, [{'title':'Dynamic Text-Attributed Graphs',
                                    'url':'https://arxiv.org/abs/2609.12345'}])
        self.assertIn('order=-announced_date_first', fetch.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
