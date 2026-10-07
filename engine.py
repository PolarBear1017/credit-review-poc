"""Auditable credit review tools. Monetary inputs use one declared currency/unit."""
import csv
import io
import json
import math
import re
import hashlib
from datetime import datetime, timezone

FIELDS = {
    'revenue': '營業收入', 'net_income': '本期淨利', 'ebit': '息稅前利益',
    'interest_expense': '利息費用', 'current_assets': '流動資產',
    'current_liabilities': '流動負債', 'inventory': '存貨', 'total_assets': '資產總額',
    'total_liabilities': '負債總額', 'equity': '權益總額', 'operating_cash_flow': '營業現金流量',
}
ALIASES = {**{k:k for k in FIELDS}, **{v:k for k,v in FIELDS.items()},
           '營收':'revenue','淨利':'net_income','營業活動之淨現金流入':'operating_cash_flow'}
RATIOS = {
    'current_ratio': ('流動比率','current_assets','current_liabilities',False,'流動資產 ÷ 流動負債'),
    'quick_ratio': ('速動比率','current_assets','current_liabilities',False,'(流動資產 − 存貨) ÷ 流動負債'),
    'debt_ratio': ('負債比率','total_liabilities','total_assets',True,'負債總額 ÷ 資產總額'),
    'interest_coverage': ('利息保障倍數','ebit','interest_expense',False,'息稅前利益 ÷ 利息費用'),
    'net_margin': ('淨利率','net_income','revenue',True,'本期淨利 ÷ 營業收入'),
    'roa': ('資產報酬率','net_income','total_assets',True,'本期淨利 ÷ 期初期末平均資產'),
    'roe': ('權益報酬率','net_income','equity',True,'本期淨利 ÷ 期初期末平均權益'),
    'cash_coverage': ('營業現金流／流動負債','operating_cash_flow','current_liabilities',True,'營業現金流量 ÷ 流動負債'),
}
DEFAULTS = {'revenue_drop': .2, 'liabilities_rise': .3, 'current_min':1, 'debt_max':.7, 'interest_min':2}
POLICY = [
 {'id':'P01','title':'營收衰退','text':'營收年減達門檻，應取得訂單、客戶集中度及需求變化說明。'},
 {'id':'P02','title':'負債增加','text':'負債年增達門檻，應取得借款明細、到期分布及資金用途。'},
 {'id':'P03','title':'流動性不足','text':'流動比率低於門檻，應檢視短期到期資金、存貨及應收帳款品質。'},
 {'id':'P04','title':'槓桿偏高','text':'負債比率高於門檻，應取得擔保品、契約條款及資本補強方案。'},
 {'id':'P05','title':'利息保障不足','text':'利息保障倍數低於門檻，應檢視利率壓力及現金償債能力。'},
 {'id':'P06','title':'負營業現金流','text':'營業現金流為負，應釐清營運資金占用及持續性。'},
]

def number(value):
    if value is None or str(value).strip() in ('','—','-','N/A','nan'): return None
    s=str(value).strip().replace(',','').replace('−','-')
    if re.fullmatch(r'\([\d.]+\)',s): s='-'+s[1:-1]
    try: v=float(s)
    except (ValueError, TypeError): raise ValueError(f'非數值金額：{str(value)[:40]}')
    if not math.isfinite(v): raise ValueError('金額不得為無限值')
    return v

def records_from_table(rows, source):
    if not rows: raise ValueError('空白表格')
    header=[str(x).strip() for x in rows[0]]
    if len(header)!=3 or header[0] not in ('metric','科目'): raise ValueError('需要三欄：metric, YYYY, YYYY；兩期必須是相鄰年度且採相同報表範圍')
    if not all(re.fullmatch(r'20\d{2}',x) for x in header[1:]): raise ValueError('年度欄請使用西元四位年份')
    years=header[1:]
    if int(years[1]) != int(years[0])+1: raise ValueError('請依序提供相鄰兩年資料，避免將跨期變動標示為年增減')
    data={y:{} for y in years}; sources={}
    for line,row in enumerate(rows[1:],2):
        if not row or not str(row[0]).strip(): continue
        key=ALIASES.get(str(row[0]).strip())
        if not key: continue
        if len(row)!=3: raise ValueError(f'第 {line} 列欄數不符')
        if key in data[years[0]]: raise ValueError(f'科目重複：{FIELDS[key]}；請合併或人工確認')
        for col,y in enumerate(years,1):
            data[y][key]=number(row[col]); sources[f'{y}.{key}']={'file':source,'location':f'列 {line} / 欄 {chr(65+col)}','raw':str(row[col])}
    if not any(data[y] for y in years): raise ValueError('未找到可辨識財務科目')
    return {'periods':years,'data':data,'sources':sources,'filename':source}

def parse_file(filename, content):
    if len(content)>10*1024*1024: raise ValueError('檔案大小上限 10 MB')
    ext=filename.rsplit('.',1)[-1].lower()
    if ext=='csv':
        result=records_from_table(list(csv.reader(io.StringIO(content.decode('utf-8-sig')))),filename)
    elif ext=='xlsx':
        import pandas as pd
        # Read only; do not evaluate formulas or macros. First sheet is the normalized input.
        df=pd.read_excel(io.BytesIO(content),header=None,dtype=object)
        result=records_from_table(df.where(pd.notna(df),None).values.tolist(),filename)
        for s in result['sources'].values(): s['location']='首張工作表 / '+s['location']
    elif ext=='pdf':
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(content))
        if len(reader.pages)>100: raise ValueError('PDF 上限 100 頁')
        texts=[(p.extract_text(extraction_mode='layout') or '') for p in reader.pages]
        text='\n'.join(texts)
        if not text.strip(): raise ValueError('此 PDF 無可讀文字，請先 OCR；系統不會猜測數字')
        # Explicit table header required; do not guess which numbers/years/units apply.
        header=re.search(r'(?:metric|科目)\s+(20\d{2})\s+(20\d{2})',text)
        if not header: raise ValueError('PDF 未找到「metric 2024 2025」格式表頭。請先整理為三欄表格，或改用 CSV／Excel 範本')
        rows=[['metric',header[1],header[2]]]; locations={}
        for page,t in enumerate(texts,1):
            for line in t.splitlines():
                parts=line.strip().split()
                if len(parts)==3 and parts[0] in ALIASES:
                    rows.append(parts); locations[ALIASES[parts[0]]]=(page,line)
        result=records_from_table(rows,filename)
        for path,s in result['sources'].items():
            page,line=locations[path.split('.')[1]]; s.update(location=f'PDF 第 {page} 頁',raw=line)
    else: raise ValueError('僅支援 .csv、.xlsx、文字型 .pdf')
    result['sha256']=hashlib.sha256(content).hexdigest()
    return result

def analyze(dataset, company='示範企業', currency='TWD', unit='千元', scope='合併／全年', thresholds=None):
    thresholds={**DEFAULTS,**(thresholds or {})}
    for key,value in thresholds.items():
        if key not in DEFAULTS or not isinstance(value,(float,int)) or not math.isfinite(value) or value<0: raise ValueError('異常門檻必須是有限非負數值')
    years=dataset['periods']; data=dataset['data']; warnings=[]; metrics=[]; anomalies=[]
    for y in years:
        d=data[y]
        for k in FIELDS:
            if d.get(k) is None: warnings.append(f'{y} 缺少 {FIELDS[k]}，相關結果不計算')
        for k in ['revenue','current_assets','current_liabilities','inventory','total_assets','total_liabilities','interest_expense']:
            if d.get(k) is not None and d[k]<0: raise ValueError(f'{y} {FIELDS[k]} 不得為負，請確認科目映射')
        a,l,e=(d.get(k) for k in ['total_assets','total_liabilities','equity'])
        if all(v is not None for v in [a,l,e]) and abs(a-l-e)>max(abs(a)*.001,.01): warnings.append(f'{y} 資產 ≠ 負債＋權益，請回查原始財報')
        if d.get('inventory') is not None and d.get('current_assets') is not None and d['inventory']>d['current_assets']: warnings.append(f'{y} 存貨大於流動資產，請確認輸入')
    for key,(label,num,den,pct,formula) in RATIOS.items():
        vals={}; refs={}; reasons={}
        for idx,y in enumerate(years):
            d=data[y]; n=d.get(num); dv=d.get(den); used=[f'{y}.{num}',f'{y}.{den}']; reason=None
            if key=='quick_ratio':
                inv=d.get('inventory'); n=n-inv if n is not None and inv is not None else None; used.append(f'{y}.inventory')
            if key in ('roa','roe'):
                if idx==0: dv=None; reason='缺少前一年度期初餘額'
                else:
                    prev=data[years[idx-1]].get(den); dv=(dv+prev)/2 if dv is not None and prev is not None else None; used.append(f'{years[idx-1]}.{den}')
            if dv is not None and dv<=0: reason='分母為零或非正值'; dv=None
            if n is None or dv is None: reason=reason or '缺少必要科目'
            vals[y]=n/dv if n is not None and dv is not None else None
            refs[y]=used; reasons[y]=reason
        metrics.append({'key':key,'label':label,'percent':pct,'formula':formula,'values':vals,'refs':refs,'reasons':reasons})
    previous,current=(data[y] for y in years)
    def change(key):
        p,c=previous.get(key),current.get(key)
        return (c-p)/p if p is not None and c is not None and p>0 else None
    def flag(id,title,value,rule,refs,policy):
        anomalies.append({'id':id,'title':title,'value':value,'rule':rule,'refs':refs,'policy_id':policy})
    growth={k:change(k) for k in ['revenue','total_liabilities','net_income']}
    if growth['revenue'] is not None and growth['revenue']<=-thresholds['revenue_drop']: flag('A01','營收顯著衰退',growth['revenue'],f"年增率 ≤ -{thresholds['revenue_drop']:.0%}",[f'{y}.revenue' for y in years],'P01')
    if growth['total_liabilities'] is not None and growth['total_liabilities']>=thresholds['liabilities_rise']: flag('A02','負債顯著增加',growth['total_liabilities'],f"年增率 ≥ {thresholds['liabilities_rise']:.0%}",[f'{y}.total_liabilities' for y in years],'P02')
    lookup={m['key']:m for m in metrics}
    for id,key,t,op,title,pid in [('A03','current_ratio','current_min','lt','短期流動性偏低','P03'),('A04','debt_ratio','debt_max','gt','財務槓桿偏高','P04'),('A05','interest_coverage','interest_min','lt','利息保障偏弱','P05')]:
        m=lookup[key]; v=m['values'][years[-1]]
        if v is not None and ((op=='lt' and v<thresholds[t]) or (op=='gt' and v>thresholds[t])): flag(id,title,v,f"{m['label']} {'<' if op=='lt' else '>'} {thresholds[t]}",m['refs'][years[-1]],pid)
    if current.get('operating_cash_flow') is not None and current['operating_cash_flow']<0: flag('A06','營業現金流轉負',current['operating_cash_flow'],'營業現金流 < 0',[f'{years[-1]}.operating_cash_flow'],'P06')
    # Retrieval is deterministic by triggered policy IDs; facts remain independent of LLM.
    retrieved=[p for p in POLICY if p['id'] in {a['policy_id'] for a in anomalies}]
    conclusion='需補件與人工覆核' if warnings else ('建議優先人工覆審' if anomalies else '未觸發示範規則，仍需人工覆審')
    summary=[f'{company} {years[-1]} 年授信覆審：{conclusion}。',f'共觸發 {len(anomalies)} 項風險規則；此為 PoC 輔助訊號，非信用評等或核貸決策。']
    for a in anomalies:
        observed=f"{a['value']:.2f} {unit}" if a['id']=='A06' else (f"{a['value']:.2%}" if a['id'] in ('A01','A02','A04') else f"{a['value']:.4f} 倍")
        summary.append(f"[{a['id']}] {a['title']}：觀察值 {observed}（{a['rule']}），來源：{', '.join(a['refs'])}。")
    if retrieved: summary.append('待補資料：'+'；'.join(p['text'] for p in retrieved))
    if warnings: summary.append('資料品質待確認：'+'；'.join(warnings))
    return {'company':company[:120],'currency':currency[:20],'unit':unit[:20],'scope':scope[:100],
            'periods':years,'metrics':metrics,'growth':growth,'anomalies':anomalies,'warnings':warnings,
            'retrieved':retrieved,'conclusion':conclusion,'summary':'\n'.join(summary),'thresholds':thresholds,
            'dataset':dataset,'created_at':datetime.now(timezone.utc).isoformat(),'mode':'規則生成／未使用 LLM',
            'trace':[{'step':s,'status':'完成'} for s in ['解析與來源定位','資料品質檢查','財務計算','規則異常偵測','政策檢索','摘要與證據組裝']]}

def compare(result, human):
    rows=[]
    for m in result['metrics']:
        ai=m['values'][result['periods'][-1]]; hv=number(human.get(m['key']))
        status='未提供' if hv is None else ('不可比較' if ai is None else ('一致' if abs(ai-hv)<=max(abs(ai)*.001,.0001) else '有差異'))
        rows.append({'key':m['key'],'label':m['label'],'ai':ai,'human':hv,'status':status,'delta':ai-hv if ai is not None and hv is not None else None})
    comparable=[r for r in rows if r['status'] in ('一致','有差異')]
    return {'rows':rows,'compared':len(comparable),'matched':sum(r['status']=='一致' for r in comparable),
            'note':'比較容許誤差：相對 0.1% 或絕對 0.0001，取較大值；比率輸入小數，如 70%=0.7。一致不代表財報或結論已被證實。'}

def validate_llm_claims(output,result):
    if not isinstance(output,dict) or set(output)!= {'selected_risks','selected_actions'}: raise ValueError('LLM 回傳格式不符')
    valid_risks={a['id'] for a in result['anomalies']}; valid_actions={p['id'] for p in result['retrieved']}
    for key,allowed in [('selected_risks',valid_risks),('selected_actions',valid_actions)]:
        values=output[key]
        if not isinstance(values,list) or any(not isinstance(v,str) or v not in allowed for v in values) or len(set(values))!=len(values): raise ValueError('LLM 引用不存在或重複的證據')
    if set(output['selected_risks'])!=valid_risks or set(output['selected_actions'])!=valid_actions: raise ValueError('LLM 遺漏風險或待補資料')
    return output
