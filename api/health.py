"""Vercel Python Function: GET /api/health."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Handler

class handler(Handler):
    def do_GET(self):
        self.send(200,'{"ok":true,"llm_configured":false,"deployment":"vercel","max_file_mb":3}')
    def do_POST(self):
        self.send(405,'{"error":"請使用 GET"}')
