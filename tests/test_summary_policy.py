import unittest
from gnn_digest.summary_policy import validate_method, method_length
from gnn_digest.agent import validate_topics
from gnn_digest.evidence import EvidenceError


class SummaryPolicyTests(unittest.TestCase):
    def test_visible_length_boundaries_ignore_markup_and_whitespace(self):
        for length in (150,151,200,201):
            text = '**方法**\n' + '图'*(length-2) + '  \t'
            self.assertEqual(method_length(text),length)
            if 151 <= length <= 200:
                validate_method(text)
            else:
                with self.assertRaises(EvidenceError): validate_method(text)

    def test_requires_balanced_method_highlights_and_rejects_html(self):
        for text in ['图'*170, '**方法*'+'图'*170, '**方法**<img src=x>'+'图'*170,
                     '**方法**[link](javascript:x)'+'图'*170]:
            with self.subTest(text=text[:20]), self.assertRaises(EvidenceError):
                validate_method(text)

    def test_only_tag_ood_are_allowed_with_evidence(self):
        source = 'We study text-attributed graphs under distribution shift.'
        for topics in (['TAG'],['OOD'],['TAG','OOD']):
            value = {'relevant':True,'confidence':'high','topics':topics,
                     'topic_evidence':{t:source for t in topics}}
            self.assertEqual(validate_topics(value,source)['topics'],topics)
        for topic in ('GNN','SSL','CL','TGN','KG','TAG_OTHER'):
            with self.subTest(topic=topic), self.assertRaises(ValueError):
                validate_topics({'relevant':True,'confidence':'high','topics':[topic],
                                 'topic_evidence':{topic:source}},source)


if __name__ == '__main__': unittest.main()
