"""One local model per fresh process; same prompts/settings and robust JSON framing.
Usage: python run_comparison.py BINARY CASES_JSON MODEL_META_JSON OUTPUT_JSON
"""
import hashlib,json,os,pathlib,platform,resource,selectors,subprocess,sys,time
binary,cases_path,meta_path,output_path=sys.argv[1:5]
cases_bytes=pathlib.Path(cases_path).read_bytes();cases=json.loads(cases_bytes)
meta=json.loads(pathlib.Path(meta_path).read_text());model=meta['path'];results=[]
assert hashlib.sha256(pathlib.Path(model).read_bytes()).hexdigest()==meta['sha256']
output=pathlib.Path(output_path);output.parent.mkdir(parents=True,exist_ok=True)
with output.with_suffix('.stderr.log').open('w') as log:
 proc=subprocess.Popen([binary,model],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,bufsize=1)
 selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
 try:
  for seq,case in enumerate(cases,1):
   start=time.perf_counter();proc.stdin.write(case['prompt']+'\n');proc.stdin.flush()
   if not selector.select(timeout=60):raise TimeoutError('No complete model response within 60 seconds')
   line=proc.stdout.readline()
   if not line:raise RuntimeError('Native model process exited before responding')
   answer=json.loads(line)
   if answer.get('sequence')!=seq:raise RuntimeError('Response sequence mismatch')
   results.append({'case':case['case'],'task':case['task'],'expected':case['expected'],'milliseconds':round((time.perf_counter()-start)*1000,3),**answer})
   print(meta['filename'],seq,'of',len(cases),'ok' if answer['ok'] else answer.get('error'),flush=True)
  proc.stdin.close();proc.wait(timeout=15)
  assert proc.returncode==0,proc.returncode
 finally:
  selector.close()
  if proc.poll() is None:proc.kill();proc.wait()
rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
public_meta={k:v for k,v in meta.items() if k!='path'}
report={'scope':'32 synthetic source-selection cases, repeated templates/positions; not a representative-PDF benchmark',
 'model':public_meta,'additionalFineTuningPerformed':False,'runtimeCommit':'df9beac7153166550571c70cc667f270b745da49',
 'host':platform.machine(),'contextTokens':4096,'maximumCpuThreads':4,'sampler':'greedy plus production JSON array grammar',
 'maximumOutputTokens':96,'promptAndCaseSha256':hashlib.sha256(cases_bytes).hexdigest(),
 'peakProcessRssBytes':int(rss*1024) if rss else None,'memoryScope':'fresh-process getrusage of native child; host, not Android',
 'responses':results}
output.write_text(json.dumps(report,indent=2)+'\n');print('Saved',output)
