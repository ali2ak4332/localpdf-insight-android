"""Validation-only immutable case records, inventory and explicit terminal results.

Does not authorize application answers or release. A completed test process and a
complete evidence run are separate claims. Model/fixture fields cannot select a
case identity or report a pytest terminal outcome.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

MATRIX_FUNCTIONS = {
    'test_grounding_matrix': 'original',
    'test_independent_verifier_matrix': 'boundary',
    'test_held_out_variations': 'variations',
    'test_frozen_adversarial_corpus': 'fresh',
}
LEGACY = {'original': 'LOCALPDF_GROUNDING_MATRIX', 'boundary': 'LOCALPDF_BOUNDARY_MATRIX',
          'variations': 'LOCALPDF_HOLDOUT_MATRIX', 'fresh': 'LOCALPDF_FRESH_MATRIX'}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')


def exclusive(path, value):
    with Path(path).open('xb') as stream:
        stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())


def key(node_id):
    return hashlib.sha256(node_id.encode('utf-8')).hexdigest()


def load(path):
    def unique(items):
        result = {}
        for k, v in items:
            if k in result: raise ValueError('Duplicate record field')
            result[k] = v
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


class EvidenceRun:
    def __init__(self, directory, nodes, required, provenance=None):
        if len(set(nodes)) != len(nodes) or not set(required) <= set(nodes):
            raise ValueError('Invalid case inventory')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        for folder in ('records', 'outcomes', 'problems'):
            (self.directory / folder).mkdir()
        self.manifest = {'version': 1, 'run_id': uuid.uuid4().hex,
                         'created_at_unix': time.time(), 'nodes': list(nodes),
                         'required_records': dict(required), 'provenance': provenance or {}}
        exclusive(self.directory / 'manifest.json', self.manifest)

    def problem(self, message):
        exclusive(self.directory / 'problems' / (uuid.uuid4().hex + '.json'),
                  {'run_id': self.manifest['run_id'], 'message': message})

    def record(self, node_id, channel, value):
        if self.manifest['required_records'].get(node_id) != channel:
            self.problem('Unexpected record identity or channel: ' + node_id)
            raise ValueError('Unexpected evidence record')
        try:
            exclusive(self.directory / 'records' / (key(node_id) + '.json'),
                      {'run_id': self.manifest['run_id'], 'node_id': node_id,
                       'channel': channel, 'data': value})
        except (OSError, ValueError, TypeError):
            self.problem('Record write failed or duplicate: ' + node_id)
            raise

    def terminal(self, node_id, phases):
        if node_id not in self.manifest['nodes']:
            self.problem('Unknown terminal identity: ' + node_id)
            raise ValueError('Unknown test')
        outcome = ('failed' if any(p['outcome'] == 'failed' for p in phases) else
                   'skipped' if any(p['outcome'] == 'skipped' for p in phases) else 'passed')
        try:
            exclusive(self.directory / 'outcomes' / (key(node_id) + '.json'),
                      {'run_id': self.manifest['run_id'], 'node_id': node_id,
                       'outcome': outcome, 'phases': phases})
        except (OSError, ValueError, TypeError):
            self.problem('Terminal write failed or duplicate: ' + node_id)
            raise


def inspect_run(directory, junit=None):
    directory = Path(directory)
    manifest = load(directory / 'manifest.json')
    errors = []
    nodes = manifest['nodes']; required = manifest['required_records']
    if len(set(nodes)) != len(nodes) or not set(required) <= set(nodes):
        errors.append('invalid_inventory')
    parsed = {}
    for folder in ('records', 'outcomes'):
        parsed[folder] = {}
        for path in sorted((directory / folder).iterdir()):
            try:
                record = load(path); node = record['node_id']
                if record['run_id'] != manifest['run_id'] or path.name != key(node) + '.json':
                    raise ValueError('Identity or filename mismatch')
                if node in parsed[folder] or node not in nodes:
                    raise ValueError('Duplicate or unknown identity')
                if folder == 'records':
                    if required.get(node) != record['channel'] or not isinstance(record.get('data'), dict):
                        raise ValueError('Invalid record channel/payload')
                else:
                    phases = record['phases']
                    if not isinstance(phases, list) or not phases or phases[-1]['when'] != 'teardown':
                        raise ValueError('No terminal teardown')
                    if [p['when'] for p in phases] not in [['setup', 'call', 'teardown'], ['setup', 'teardown']]:
                        raise ValueError('Missing, duplicate or unordered phases')
                    if len(phases) == 2 and phases[0]['outcome'] == 'passed':
                        raise ValueError('A successful setup requires a call outcome')
                    outcomes = [p['outcome'] for p in phases]
                    if any(o not in {'passed', 'failed', 'skipped'} for o in outcomes):
                        raise ValueError('Invalid phase outcome')
                    expected = 'failed' if 'failed' in outcomes else 'skipped' if 'skipped' in outcomes else 'passed'
                    if expected != record['outcome']:
                        raise ValueError('Contradictory terminal status')
                parsed[folder][node] = record
            except (OSError, ValueError, KeyError, TypeError):
                errors.append('invalid_' + folder + ':' + path.name)
    errors.extend('missing_record:' + n for n in required if n not in parsed['records'])
    errors.extend('missing_terminal:' + n for n in nodes if n not in parsed['outcomes'])
    for n, record in parsed['records'].items():
        terminal = parsed['outcomes'].get(n)
        if terminal and terminal['outcome'] != 'skipped' and (record['data'].get('passed') is True) != (terminal['outcome'] == 'passed'):
            errors.append('record_disagrees_with_test:' + n)
    if list((directory / 'problems').iterdir()): errors.append('recording_problems_present')
    counts = {v: sum(r['outcome'] == v for r in parsed['outcomes'].values())
              for v in ('passed', 'failed', 'skipped')}
    if junit is not None:
        try:
            cases = ET.parse(junit).findall('.//testcase'); observed = {}
            for c in cases:
                ident = (c.attrib.get('classname'), c.attrib.get('name'))
                if ident in observed: raise ValueError('Duplicate JUnit case')
                observed[ident] = ('failed' if c.find('failure') is not None or c.find('error') is not None
                                  else 'skipped' if c.find('skipped') is not None else 'passed')
            expected = {}
            for node, terminal in parsed['outcomes'].items():
                parts = node.split('::'); module = parts[0].removesuffix('.py').replace('/', '.')
                expected[('.'.join([module] + parts[1:-1]), parts[-1])] = terminal['outcome']
            if observed != expected: errors.append('junit_inventory_or_outcome_mismatch')
        except (OSError, ET.ParseError, ValueError): errors.append('invalid_junit')
    return {'run_id': manifest['run_id'], 'complete': not errors, 'errors': errors,
            'expected_cases': len(nodes), 'terminal_cases': len(parsed['outcomes']),
            'expected_records': len(required), 'actual_records': len(parsed['records']),
            'counts': counts, 'junit_reconciled': junit is not None and not errors,
            'validation_passed': not errors and counts['failed'] == 0,
            'skips_require_separate_disposition': counts['skipped']}


_ACTIVE = None
_RUN = None
_PHASES = {}


def capture(channel, value):
    if _RUN is not None:
        _RUN.record(_ACTIVE, channel, value)
    path = os.environ.get(LEGACY[channel])
    if path:
        # Optional compatibility export; the immutable run remains canonical.
        try:
            with open(path, 'ab') as stream:
                stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
        except (OSError, ValueError, TypeError):
            if _RUN is not None: _RUN.problem('Legacy export write failed: ' + str(_ACTIVE))
            raise


def pytest_collection_finish(session):
    global _RUN
    path = os.environ.get('LOCALPDF_EVIDENCE_RUN')
    if not path: return
    nodes = [i.nodeid for i in session.items]
    required = {i.nodeid: MATRIX_FUNCTIONS[i.originalname] for i in session.items
                if getattr(i, 'originalname', None) in MATRIX_FUNCTIONS}
    root = Path(__file__).parents[1]
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    paths = list((root / 'src/localpdf_insight').glob('*.py')) + list((root / 'tests').glob('*.py'))
    paths += list((root / 'tests/fixtures/b1-independent').glob('*.json'))
    provenance = {'commit': sha, 'platform': platform.platform(),
                  'file_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    _RUN = EvidenceRun(path, nodes, required, provenance)


def pytest_runtest_setup(item):
    global _ACTIVE
    _ACTIVE = item.nodeid


# Importing the standalone reconciler needs pytest only for plugin registration.
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if _RUN is None: return
    phases = _PHASES.setdefault(item.nodeid, [])
    phase = {'when': report.when, 'outcome': report.outcome, 'duration': report.duration}
    if report.failed or report.skipped: phase['detail'] = str(report.longrepr)
    phases.append(phase)
    if report.when == 'teardown': _RUN.terminal(item.nodeid, phases)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    if _RUN is None: return
    summary = inspect_run(_RUN.directory)
    summary['pytest_exitstatus'] = int(exitstatus)
    summary['validation_passed'] &= int(exitstatus) == 0
    exclusive(_RUN.directory / 'session-summary.json', summary)
    if not summary['complete'] and int(exitstatus) == 0: session.exitstatus = 1
