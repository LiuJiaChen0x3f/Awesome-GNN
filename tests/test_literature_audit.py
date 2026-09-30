import json
import unittest
from datetime import date
from unittest.mock import patch

from gnn_digest.verification import verify_candidate, venue_abbreviation, VerificationError, program_text


class LiteratureAuditTests(unittest.TestCase):
    def test_vldb_program_excludes_tutorials_demos_and_workshops(self):
        html = '''<div id="res-23"><div class="paper"><span class="ptitle"><a>Graph RAG Research</a></span></div></div>
        <div id="demo-A"><span class="ptitle">Graph RAG Demo</span></div>
        <div id="tut-15"><span class="ptitle">Graph RAG Tutorial</span></div>
        <div id="ws-1"><span class="ptitle">Graph RAG Workshop</span></div>'''
        program_text.cache_clear()
        try:
            with patch('gnn_digest.verification.fetch_page', return_value=html):
                self.assertEqual(program_text('https://www.vldb.org/2026/program.html'), 'Graph RAG Research')
        finally:
            program_text.cache_clear()

    def test_vldb_program_does_not_fall_back_when_layout_changes(self):
        program_text.cache_clear()
        try:
            with patch('gnn_digest.verification.fetch_page', return_value='<h1>Graph RAG Tutorial</h1>'):
                with self.assertRaises(VerificationError):
                    program_text('https://www.vldb.org/2026/program.html')
        finally:
            program_text.cache_clear()

    def test_iclr_proceedings_main_track_with_pdf(self):
        html='''<meta name="citation_title" content="Text Graph Learning">
        <meta name="citation_journal_title" content="International Conference on Learning Representations">
        <meta name="citation_publication_date" content="2026-04-20">
        <meta name="citation_pdf_url" content="https://proceedings.iclr.cc/paper_files/paper/2026/file/x-Paper-Conference.pdf">'''
        c={'title':'Text Graph Learning','url':'https://proceedings.iclr.cc/paper_files/paper/2026/hash/x-Abstract-Conference.html'}
        with patch('gnn_digest.verification.fetch_page',return_value=html):
            p=verify_candidate(c,date(2025,1,1),date(2026,9,29))
            self.assertEqual((p['venue_label'],p['conference_year']),('ICLR',2026))
            self.assertIn('Paper-Conference.pdf',p['pdf_url'])
            c['url']=c['url'].replace('Abstract-Conference','Abstract-Workshop')
            with self.assertRaises(VerificationError):verify_candidate(c,date(2025,1,1),date(2026,9,29))

    def test_iclr_official_program_requires_exact_credit_and_title(self):
        c={'title':'Text Graph Learning','url':'https://iclr.cc/virtual/2026/poster/123'}
        record={'@type':'CreativeWork','name':c['title'],'creditText':'ICLR 2026','datePublished':'2026-02-06'}
        def page(*a,**k):return '<a href="https://openreview.net/forum?id=test">Paper</a><script type="application/ld+json">'+json.dumps(record)+'</script>'
        with patch('gnn_digest.verification.fetch_page',side_effect=page):
            self.assertEqual(verify_candidate(c,date(2025,1,1),date(2026,9,29))['venue_label'],'ICLR')
            record['creditText']='ICML 2026'
            with self.assertRaises(VerificationError):verify_candidate(c,date(2025,1,1),date(2026,9,29))

    def test_expanded_venues_do_not_accept_workshops(self):
        for name in ('ICLR','LoG','ICDM','WSDM','NAACL'):
            self.assertEqual(venue_abbreviation(name),name)
            self.assertEqual(venue_abbreviation(name+' Workshop'),'')


if __name__=='__main__':unittest.main()
