"""Capture a test run once, then reconcile inventory, records, JUnit and raw log.

Use a new output directory for every attempt. An interrupted collector has no
completion.json. A console/JUnit mismatch cannot certify a completed run.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests'))
from evidence_capture import exclusive, inspect_run


def console_matches(text, counts):
    # Ignore per-test failure details; only the final pytest summary counts.
    lines = [line for line in text.splitlines() if re.search(r'\bin \d+(?:\.\d+)?s', line)]
    if not lines: return False
    summary = lines[-1]
    return all(int(re.search(r'(\d+) '+name, summary)[1]) == n if re.search(r'(\d+) '+name, summary)
               else n == 0 for name, n in counts.items())


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('pytest_args', nargs=argparse.REMAINDER); args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    tail = args.pytest_args[1:] if args.pytest_args[:1] == ['--'] else args.pytest_args
    cmd = [sys.executable, '-m', 'pytest', '-ra', '--color=no', '--junitxml='+str(output/'junit.xml'), *tail]
    env = dict(os.environ, LOCALPDF_EVIDENCE_RUN=str(output/'cases'))
    exclusive(output/'started.json', {'command':cmd, 'started_at_unix':time.time(), 'cwd':str(ROOT)})
    result = subprocess.run(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with (output/'pytest.txt').open('xb') as f:
        f.write(result.stdout); f.flush(); os.fsync(f.fileno())
    try: summary = inspect_run(output/'cases', output/'junit.xml')
    except Exception as exc: summary = {'complete':False,'validation_passed':False,'errors':[type(exc).__name__+': '+str(exc)],'counts':{}}
    summary['pytest_exitstatus'] = result.returncode
    summary['console_complete'] = bool(summary['counts']) and console_matches(result.stdout.decode('utf-8', errors='replace'), summary['counts'])
    if not summary['console_complete']:
        summary['complete'] = summary['validation_passed'] = False
        summary['errors'].append('console_summary_missing_or_inconsistent')
    summary['validation_passed'] &= result.returncode == 0
    summary['artifact_sha256'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (output/'pytest.txt',output/'junit.xml') if p.exists()}
    exclusive(output/'completion.json', summary)
    print(json.dumps(summary)); return 0 if summary['validation_passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
