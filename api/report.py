"""Vercel Python Function: POST /api/report."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Handler

class handler(Handler):
    max_body=4_450_000
    max_file=3*1024*1024
    def do_POST(self):
        self.path='/api/report'
        super().do_POST()
    def do_GET(self):
        self.send(405,'{"error":"請使用 POST"}')
