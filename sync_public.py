"""Run after changing static assets, before publishing."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parent
target=root/'public'
target.mkdir(exist_ok=True)
for name in ['index.html','app.js','style.css']:
    shutil.copy2(root/'static'/name,target/name)
shutil.copy2(root/'samples/financials.csv',target/'sample.csv')
# Vercel's JSON/base64 upload limit: 3 MiB source -> about 4 MiB request.
file=target/'app.js'
file.write_text(file.read_text().replace('10*1024*1024','3*1024*1024').replace('檔案超過 10 MB','雲端展示版檔案上限 3 MB'))
file=target/'index.html'
file.write_text(file.read_text().replace('上限 10 MB','上限 3 MB').replace('啟用本機 Ollama 證據排序（需設定 OLLAMA_MODEL）','雲端展示版使用規則摘要；本機 Ollama 僅限本機版').replace('id="use_llm" type="checkbox"','id="use_llm" type="checkbox" disabled'))
print('public/ assets synchronized; cloud upload limit = 3 MB')
