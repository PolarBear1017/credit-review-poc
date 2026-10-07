import copy
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import parse_file, analyze, compare, validate_llm_claims
from server import report_html

class CreditTests(unittest.TestCase):
    def setUp(self):
        self.raw=(Path(__file__).resolve().parents[1]/'samples/financials.csv').read_bytes()
        self.ds=parse_file('sample.csv',self.raw)
    def test_sample_correctness(self):
        r=analyze(self.ds)
        self.assertAlmostEqual(r['growth']['revenue'],-.35)
        self.assertEqual(len(r['anomalies']),6)
        m={m['key']:m for m in r['metrics']}
        self.assertAlmostEqual(m['current_ratio']['values']['2025'],500000/560000)
        self.assertAlmostEqual(m['quick_ratio']['values']['2025'],290000/560000)
        self.assertAlmostEqual(m['debt_ratio']['values']['2025'],.7625)
        self.assertAlmostEqual(m['interest_coverage']['values']['2025'],46000/38000)
        self.assertAlmostEqual(m['net_margin']['values']['2025'],.02)
        self.assertAlmostEqual(m['roa']['values']['2025'],15600/1550000)
        self.assertAlmostEqual(m['roe']['values']['2025'],15600/515000)
        self.assertIsNone(m['roa']['values']['2024'])
        self.assertFalse(r['warnings'])
        self.assertTrue(all(id in self.ds['sources'] for m in r['metrics'] for ids in m['refs'].values() for id in ids))
    def test_zero_and_missing_not_fabricated(self):
        self.ds['data']['2025']['interest_expense']=0
        self.ds['data']['2025'].pop('inventory')
        r=analyze(self.ds); m={m['key']:m for m in r['metrics']}
        self.assertIsNone(m['interest_coverage']['values']['2025'])
        self.assertIsNone(m['quick_ratio']['values']['2025'])
        self.assertTrue(r['warnings'])
        self.assertNotIn('A05',[a['id'] for a in r['anomalies']])
    def test_reconciliation(self):
        self.ds['data']['2025']['equity']=500000
        self.assertTrue(any('資產 ≠' in w for w in analyze(self.ds)['warnings']))
    def test_negative_equity(self):
        self.ds['data']['2025']['equity']=-900000
        self.assertIsNone(next(m for m in analyze(self.ds)['metrics'] if m['key']=='roe')['values']['2025'])
    def test_duplicate_nonfinite_bad_period(self):
        for raw in [self.raw+b'net_income,1,2\n',self.raw.replace(b'1200000',b'inf'),self.raw.replace(b'2025',b'2026')]:
            with self.assertRaises(ValueError): parse_file('bad.csv',raw)
    def test_parentheses_and_missing(self):
        d=parse_file('a.csv',b'metric,2024,2025\nnet_income,"(1,200)",\n')
        self.assertEqual(d['data']['2024']['net_income'],-1200)
        self.assertIsNone(d['data']['2025']['net_income'])
    def test_human_diff(self):
        c=compare(analyze(self.ds),{'current_ratio':500000/560000,'debt_ratio':.70})
        self.assertEqual(c['compared'],2);self.assertEqual(c['matched'],1)
    def test_llm_added_omitted_repeated_ids_rejected(self):
        r=analyze(self.ds); good={'selected_risks':[a['id'] for a in r['anomalies']],'selected_actions':[p['id'] for p in r['retrieved']]}
        self.assertEqual(validate_llm_claims(good,r),good)
        for key,value in [('selected_risks',['X']),('selected_risks',[]),('selected_actions',['P01','P01'])]:
            bad=copy.deepcopy(good);bad[key]=value
            with self.assertRaises(ValueError):validate_llm_claims(bad,r)
    def test_pdf_table_mapping_and_ocr_failure(self):
        from types import SimpleNamespace
        pages=[SimpleNamespace(extract_text=lambda **kwargs:self.raw.decode().replace(',',' '))]
        with patch('pypdf.PdfReader',return_value=SimpleNamespace(pages=pages)):
            ds=parse_file('a.pdf',b'fixture');self.assertEqual(ds['data']['2025']['revenue'],780000)
            self.assertEqual(ds['sources']['2025.revenue']['location'],'PDF 第 1 頁')
        with patch('pypdf.PdfReader',return_value=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda **kwargs:'')])):
            with self.assertRaisesRegex(ValueError,'OCR'):parse_file('a.pdf',b'fixture')
    def test_excel_mapping(self):
        import pandas as pd
        df=pd.read_csv(io.BytesIO(self.raw),header=None)
        with patch('pandas.read_excel',return_value=df):
            ds=parse_file('a.xlsx',b'fixture')
            self.assertEqual(ds['data']['2025']['total_liabilities'],1220000)
            self.assertIn('工作表',ds['sources']['2025.revenue']['location'])
    def test_report_escapes_untrusted_text(self):
        r=analyze(self.ds,company='<script>alert(1)</script>')
        out=report_html(r,compare(r,{}),'<img src=x onerror=alert(1)>')
        self.assertNotIn('<script>',out);self.assertNotIn('<img',out)
        self.assertIn('SHA-256',out)
    def test_real_pdf_excel_match_csv(self):
        folder=Path(__file__).resolve().parents[1]/'samples'
        for filename in ['financials.xlsx','financials.pdf']:
            ds=parse_file(filename,(folder/filename).read_bytes())
            self.assertEqual(ds['data'],self.ds['data'])
            self.assertEqual(len(analyze(ds)['anomalies']),6)

if __name__=='__main__':unittest.main()
