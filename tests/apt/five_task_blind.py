"""Prepare source-grounded review packs without model identity/timing metadata."""
from pathlib import Path
import argparse, json

p=argparse.ArgumentParser();p.add_argument('workdir',type=Path);args=p.parse_args();root=args.workdir
corpus=json.loads((root/'corpus.json').read_text())['documents']
gold={d['id']:d for d in json.loads((root/'gold-frozen.json').read_text())['documents']}
mapping={'A':'qwen35-2b.json','B':'qwen35-0.8b.json'}
reports={label:json.loads((root/name).read_text()) for label,name in mapping.items() if (root/name).exists()}
for category in ['financial','contractual','technical']:
 docs=[]
 for doc in corpus:
  if doc['category']!=category:continue
  candidates={}
  for label,report in reports.items():
   rs=[r for r in report['responses'] if r['documentId']==doc['id']]
   if len(rs)!=4:continue
   candidates[label]=[{k:r.get(k) for k in ['task','rawContent','parsedContent','finish_reason','assessment']} for r in rs]
  docs.append({'id':doc['id'],'title':doc['title'],'pages':doc['pages'],'gold':gold[doc['id']]['tasks'],'candidates':candidates})
 pack={'scope':'Blinded source-based review; gold is non-exhaustive and agent-authored','documents':docs}
 dest=root/f'blind-{category}.json';temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(pack,indent=2,ensure_ascii=False)+'\n');temp.replace(dest)
 print(category,{label:sum(label in d['candidates'] for d in docs) for label in mapping})
