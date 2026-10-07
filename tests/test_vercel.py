"""Exercise the Vercel entrypoints using in-memory HTTP requests."""
import base64
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api.analyze import handler as Analyze
from api.report import handler as Report
from api.health import handler as Health

class Connection:
    def __init__(self,data):self.stream=io.BytesIO(data);self.output=bytearray()
    def makefile(self,*args):return self.stream
    def sendall(self,data):self.output.extend(data)

def request(handler,body=None,origin='https://credit-demo.vercel.app',method='POST'):
    payload=json.dumps(body or {}).encode()
    header=f'{method} /api/function HTTP/1.1\r\nHost: credit-demo.vercel.app\r\nOrigin: {origin}\r\nContent-Type: application/json\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n'.encode()
    conn=Connection(header+payload)
    with patch.dict(os.environ,{'VERCEL':'1'}):handler(conn,('127.0.0.1',10000),object())
    head,content=bytes(conn.output).split(b'\r\n\r\n',1)
    return int(head.split()[1]),content

class VercelTests(unittest.TestCase):
    def test_https_analyze(self):
        code,data=request(Analyze,{'sample':True})
        self.assertEqual(code,200)
        self.assertEqual(len(json.loads(data)['result']['anomalies']),6)
    def test_cross_origin_rejected(self):
        code,_=request(Analyze,{'sample':True},origin='https://other.example')
        self.assertEqual(code,403)
    def test_cloud_upload_limit(self):
        data=base64.b64encode(b'x'*(3*1024*1024+1)).decode()
        code,body=request(Analyze,{'filename':'a.csv','content':data})
        self.assertEqual(code,400);self.assertIn('3 MB',json.loads(body)['error'])
    def test_report_and_health(self):
        code,body=request(Report,{'sample':True,'human':{'debt_ratio':.7}})
        self.assertEqual(code,200);self.assertIn('有差異',body.decode())
        code,body=request(Health,method='GET')
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['max_file_mb'],3)
    def test_cloud_llm_falls_back_without_network(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('network should not be used')):
            code,data=request(Analyze,{'sample':True,'use_llm':True})
        self.assertEqual(code,200);self.assertIn('llm_error',json.loads(data)['result'])

if __name__=='__main__':unittest.main()
