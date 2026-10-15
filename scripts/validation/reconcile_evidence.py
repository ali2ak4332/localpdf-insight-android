"""Check immutable case evidence against inventory and finalized pytest JUnit."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests'))
from evidence_capture import inspect_run
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
p.add_argument('--junit',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
try:result=inspect_run(a.run,a.junit)
except Exception as exc:result={'complete':False,'validation_passed':False,'errors':[type(exc).__name__+': '+str(exc)]}
with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(result,ensure_ascii=False))
raise SystemExit(0 if result['complete'] and result['validation_passed'] else 1)
