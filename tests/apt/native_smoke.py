"""Run the actual C++ engine/model. Not an Android device or quality benchmark."""
import json, os, subprocess, sys, time
binary, model = sys.argv[1:3]
prompts = [
 'Select the passage mentioning revenue. Return ONLY a JSON array of passage indices. 0: Revenue was USD 125 million in 2025. 1: Staff training is optional. Selected indices:',
 'Select the passage containing a contractual obligation. Return ONLY a JSON array of passage indices. 0: The sky is blue. 1: The buyer shall pay within 30 days unless the invoice is disputed. Selected indices:',
 'Select numerical findings. Return ONLY a JSON array of passage indices. 0: Revenue increased by 10% in 2025. Selected indices:',
]
start=time.perf_counter()
r=subprocess.run([binary,model],input='\n'.join(prompts)+'\n',text=True,capture_output=True,timeout=120)
lines=r.stdout.strip().splitlines()
assert r.returncode==0,(r.returncode,r.stderr[-1000:])
assert len(lines)==len(prompts),lines
for line in lines:
 v=json.loads(line);assert isinstance(v,list) and all(isinstance(i,int) for i in v),line
out={'test':'host native real Gemma inference','responses':[json.loads(x) for x in lines],
     'seconds':round(time.perf_counter()-start,3),'model_bytes':os.path.getsize(model),
     'android_device_test':False,'quality_benchmark':False}
print(json.dumps(out,indent=2))
bad=subprocess.run([binary,'/nonexistent/model.gguf'],input=prompts[0]+'\n',text=True,capture_output=True,timeout=10)
assert bad.stdout.startswith('ERROR:'),bad.stdout
print('Missing-model error path passed')
