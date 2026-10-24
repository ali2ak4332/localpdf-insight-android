"""A multiline model response must remain exactly one transport record."""
import json,subprocess,sys
r=subprocess.run([sys.argv[1],'--framing-test'],capture_output=True,text=True,check=True)
records=[json.loads(line)for line in r.stdout.splitlines()]
assert len(records)==3,records
assert [x['sequence']for x in records]==[1,2,3]
assert records[0]['text']=='\n[\n  2\n]\n'
assert json.loads(records[0]['text'])==[2]
assert records[1]['text']=='[]' and records[1]['ok']
assert not records[2]['ok'] and records[2]['error']=='test "error"\nwith newline'
print('Framing regression passed: multiline JSON, empty array, escaped errors, sequence IDs')
