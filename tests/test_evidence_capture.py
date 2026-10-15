"""Fault injection for the validation recorder, not product/model reliability."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
import evidence_capture as recorder

NODE = 'tests/test_sample.py::test_case[ar-strict]'
PHASES = [{'when': p, 'outcome': 'passed'} for p in ('setup', 'call', 'teardown')]


def new_run(tmp_path):
    return recorder.EvidenceRun(tmp_path/'run', [NODE], {NODE: 'fresh'})


def populate(run, passed=True):
    run.record(NODE, 'fresh', {'passed': passed, 'question': 'سؤال'})
    run.terminal(NODE, PHASES)


def test_complete_run_requires_inventory_and_final_junit(tmp_path):
    run = new_run(tmp_path); populate(run)
    junit = tmp_path/'junit.xml'
    junit.write_text('<testsuites><testsuite><testcase classname="tests.test_sample" name="test_case[ar-strict]"/></testsuite></testsuites>', encoding='utf-8')
    result = recorder.inspect_run(run.directory, junit)
    assert result['complete'] and result['junit_reconciled'] and result['validation_passed']
    assert result['actual_records'] == result['expected_records'] == 1
    assert recorder.load(run.directory/'records'/(recorder.key(NODE)+'.json'))['data']['question'] == 'سؤال'


@pytest.mark.parametrize('fault', ['missing_record', 'missing_terminal', 'duplicate_record',
    'duplicate_terminal', 'wrong_run', 'duplicate_file', 'truncated', 'false_pass', 'missing_call', 'wrong_junit'])
def test_incomplete_or_contradictory_evidence_cannot_pass(tmp_path, fault):
    run = new_run(tmp_path); populate(run)
    record = run.directory/'records'/(recorder.key(NODE)+'.json')
    outcome = run.directory/'outcomes'/(recorder.key(NODE)+'.json')
    junit = None
    if fault == 'missing_record': record.unlink()
    if fault == 'missing_terminal': outcome.unlink()
    if fault == 'duplicate_record':
        with pytest.raises(FileExistsError): run.record(NODE, 'fresh', {'passed': True})
    if fault == 'duplicate_terminal':
        with pytest.raises(FileExistsError): run.terminal(NODE, PHASES)
    if fault == 'wrong_run':
        value = recorder.load(record); value['run_id'] = 'other-run'
        record.write_bytes(recorder.encoded(value))
    if fault == 'duplicate_file': (record.parent/'duplicate.json').write_bytes(record.read_bytes())
    if fault == 'truncated': record.write_bytes(b'{"partial":')
    if fault == 'false_pass':
        value = recorder.load(outcome); value['phases'][1]['outcome'] = 'failed'; value['outcome'] = 'failed'
        outcome.write_bytes(recorder.encoded(value))
    if fault == 'missing_call':
        value = recorder.load(outcome); value['phases'].pop(1)
        outcome.write_bytes(recorder.encoded(value))
    if fault == 'wrong_junit':
        junit = tmp_path/'wrong.xml'; junit.write_text('<testsuite/>', encoding='utf-8')
    result = recorder.inspect_run(run.directory, junit)
    assert not result['complete'] and not result['validation_passed'], result


def test_write_failure_propagates_and_prevents_completeness(tmp_path, monkeypatch):
    run = new_run(tmp_path); original = recorder.exclusive
    def no_space(path, value):
        if Path(path).parent.name == 'records': raise OSError(28, 'Simulated disk full')
        original(path, value)
    monkeypatch.setattr(recorder, 'exclusive', no_space)
    with pytest.raises(OSError): run.record(NODE, 'fresh', {'passed': True})
    run.terminal(NODE, PHASES)
    result = recorder.inspect_run(run.directory)
    assert not result['complete'] and 'recording_problems_present' in result['errors']


def test_new_run_cannot_overwrite_an_old_run(tmp_path):
    run = new_run(tmp_path); original = (run.directory/'manifest.json').read_bytes()
    with pytest.raises(FileExistsError): new_run(tmp_path)
    assert (run.directory/'manifest.json').read_bytes() == original
    other = recorder.EvidenceRun(tmp_path/'rerun', [NODE], {NODE:'fresh'})
    assert run.manifest['run_id'] != other.manifest['run_id']


def child_env():
    env = {k:v for k,v in os.environ.items() if k not in recorder.LEGACY.values() and k != 'LOCALPDF_EVIDENCE_RUN'}
    env['PYTHONPATH'] = str(Path(__file__).parent)
    return env


def test_actual_process_interruption_preserves_record_but_cannot_complete(tmp_path):
    code = '''import os,sys
from evidence_capture import EvidenceRun
r=EvidenceRun(sys.argv[1],['case'],{'case':'fresh'})
r.record('case','fresh',{'passed':True})
os._exit(17)
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path/'interrupted')], env=child_env(), capture_output=True, timeout=15)
    assert result.returncode == 17
    check = recorder.inspect_run(tmp_path/'interrupted')
    assert check['actual_records'] == 1 and check['terminal_cases'] == 0 and not check['complete']


def test_passing_pytest_without_required_record_returns_failure(tmp_path):
    test = tmp_path/'test_missing.py'
    test.write_text('def test_grounding_matrix():\n    assert True\n', encoding='utf-8')
    env = child_env(); env['LOCALPDF_EVIDENCE_RUN'] = str(tmp_path/'missing')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'evidence_capture', '-q', str(test)],
                            cwd=tmp_path, env=env, capture_output=True, timeout=30)
    assert result.returncode == 1, result.stdout.decode('utf-8', errors='replace')
    check = recorder.load(tmp_path/'missing/session-summary.json')
    assert check['counts']['passed'] == 1 and not check['complete'] and not check['validation_passed']


def test_duplicate_json_keys_and_unknown_case_id_are_rejected(tmp_path):
    path = tmp_path/'bad.json'; path.write_text('{"run_id":"a","run_id":"b"}', encoding='utf-8')
    with pytest.raises(ValueError): recorder.load(path)
    run = new_run(tmp_path)
    with pytest.raises(ValueError): run.record('not-collected', 'fresh', {'passed':True})
    assert not recorder.inspect_run(run.directory)['complete']
