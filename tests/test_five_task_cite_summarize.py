"""No-model checks that the aggregator accepts cited-line (cite-v1) reports and still fails closed."""
import copy
import hashlib
import json

import pytest

from test_five_task_summarize import run_data, execute, save, digest, SECRET, TASKS  # noqa: F401  (fixture reuse)

MODEL_FIELDS = {'summarize': ['claim', 'from', 'to'], 'insights': ['claim', 'from', 'to'],
                'figures': ['line', 'value', 'metric', 'entity'],
                'risks': ['obligation', 'party', 'deadline', 'exception', 'from', 'to']}
LIMITS = {'claim': 240, 'metric': 80, 'entity': 80, 'value': 48, 'obligation': 200, 'party': 80, 'deadline': 100, 'exception': 160}
SKIP = ('technical-01', 'figures')


def to_cite(work, skip=SKIP):
    """Rewrite the legacy fixture into cite-v1 reports: same corpus, grades and verifier, cited-line rows."""
    corpus = json.load(open(work / 'corpus.json'))
    pages = {d['id']: d['pages'] for d in corpus['documents']}
    for filename in ('qwen35-2b.json', 'qwen35-0.8b.json'):
        report = json.load(open(work / filename))
        report['protocol'] = {**report['protocol'], 'name': 'cite-v1', 'evidence': 'cited-lines', 'modelFields': MODEL_FIELDS}
        plans = {}
        for plan in report['plan']:
            key = (plan['documentId'], plan['task'])
            line = pages[plan['documentId']][0]['text']
            if key == skip:
                plan.update({'request': None, 'promptSha256': None, 'deterministicSkip': True})
            else:
                prompt = f'Task {plan["task"]}\n[PAGE 1]\n[1] {line}\nEND PDF LINES\nJSON:'
                props = {f: ({'type': 'integer', 'enum': [1]} if f in ('from', 'to', 'line') else {'type': 'string', 'maxLength': LIMITS[f]})
                         for f in MODEL_FIELDS[plan['task']]}
                plan['request'] = {'messages': [{'role': 'user', 'content': prompt}], 'response_format': {'type': 'json_schema',
                    'json_schema': {'name': plan['task'] + '_cited', 'strict': True, 'schema': {'type': 'object',
                        'properties': {'findings': {'type': 'array', 'maxItems': 2, 'items': {'type': 'object', 'properties': props,
                            'required': MODEL_FIELDS[plan['task']], 'additionalProperties': False}}},
                        'required': ['findings'], 'additionalProperties': False}}}}
                plan['promptSha256'] = digest(prompt)
                plan['deterministicSkip'] = False
            plans[key] = plan
        for row in report['responses']:
            key = (row['documentId'], row['task'])
            plan = plans[key]
            row.update({k: copy.deepcopy(plan[k]) for k in ('request', 'promptSha256', 'deterministicSkip')})
            legacy = row['parsedContent']['findings'][0]
            if key == skip:
                row.update({'prompt': None, 'rawContent': '', 'parsedContent': None, 'finish_reason': None, 'api': {},
                            'materialized': {'findings': []}})
                row['assessment'] = {'deterministicSkip': True, 'schemaValid': True, 'httpSuccessful': False,
                                     'completedWithinBudget': False, 'findingsCount': 0, 'exactQuoteCount': 0, 'evidence': []}
                continue
            model = {f: (1 if f in ('from', 'to', 'line') else SECRET) for f in MODEL_FIELDS[row['task']]}
            row['prompt'] = plan['request']['messages'][0]['content']
            row['rawContent'] = json.dumps({'findings': [model]})
            row['parsedContent'] = {'findings': [model]}
            built = {**legacy, 'quote': pages[row['documentId']][0]['text'], 'page': 1}
            row['materialized'] = {'findings': [built]}
            row['assessment'].update({'deterministicSkip': False, 'findingsCount': 1, 'modelFindingsCount': 1})
        save(work / filename, report)
    for category in ('financial', 'technical', 'contractual'):
        path = work / f'grades-{category}.json'
        grades = json.load(open(path))
        for g in grades['grades']:
            if (g['documentId'], g['task']) == skip:
                g.update({'factualCorrect': False, 'relevant': False, 'adequateCoverage': False, 'evidenceCorrect': False,
                          'strictPass': False, 'quotes': {'records': 0, 'exactOnPage': 0}, 'unsupportedFindings': 0,
                          'numeric': {k: 0 for k in g['numeric']}})
        save(path, grades)
    verification = json.load(open(work / 'verify-findings.json'))
    for item in verification['generatedFindingVerification']['files']:
        report = json.load(open(work / item['path'].split('/')[-1]))
        item['sha256'] = hashlib.sha256((work / item['path'].split('/')[-1]).read_bytes()).hexdigest()
        rows = {(r['documentId'], r['task']): r for r in report['responses']}
        for checked in item['rows']:
            source = rows[(checked['documentId'], checked['task'])]['materialized']['findings']
            checked['findings'] = [{'rawFinding': f, 'quoteCheck': {'accepted': True, 'acceptedAtRequestedPage': True}} for f in source]
    verification['generatedFindingVerification']['summary'] = {'responseRows': 240, 'findings': 238}
    save(work / 'verify-findings.json', verification)


def test_cite_reports_aggregate_and_count_code_built_findings(run_data):
    work, _ = run_data
    to_cite(work)
    result, output = execute(run_data)
    assert result.returncode == 0, result.stderr
    public = output.read_text()
    assert SECRET not in public
    data = json.loads(public)
    assert data['status'] == 'completed'
    case = next(c for c in data['cases'] if (c['documentId'], c['task']) == SKIP and c['modelId'] == 'qwen35-2b')
    assert case['raw']['technicalComplete'] is True and case['raw']['parsedFindings'] == 0
    assert data['models']['qwen35-2b']['byTask']['figures']['emptyResponses'] == 1
    assert data['models']['qwen35-2b']['overall']['quotes']['literalExactOnPage']['rate'] == 1.0


def test_cite_deterministic_abstention_counts_only_when_gold_expects_absence(run_data):
    work, _ = run_data
    to_cite(work)
    gold = json.load(open(work / 'gold-frozen.json'))
    next(d for d in gold['documents'] if d['id'] == SKIP[0])['tasks']['figures']['absenceExpected'] = True
    save(work / 'gold-frozen.json', gold)
    for category in ('technical',):
        path = work / f'grades-{category}.json'; grades = json.load(open(path))
        for g in grades['grades']:
            if (g['documentId'], g['task']) == SKIP:
                g.update({'factualCorrect': True, 'relevant': True, 'adequateCoverage': True})
        save(path, grades)
    result, output = execute(run_data)
    assert result.returncode == 0, result.stderr
    data = json.load(open(output))
    assert data['models']['qwen35-2b']['byTask']['figures']['correctAbstentions'] == 1


@pytest.mark.parametrize('mutation', ['quote-not-on-page', 'skip-with-findings', 'skip-on-other-task', 'unbounded-line'])
def test_cite_rejects_tampered_or_inconsistent_rows(run_data, mutation):
    work, _ = run_data
    to_cite(work)
    p = work / 'qwen35-2b.json'; d = json.load(open(p))
    row = next(r for r in d['responses'] if (r['documentId'], r['task']) == ('financial-01', 'summarize'))
    if mutation == 'quote-not-on-page':
        row['materialized']['findings'][0]['quote'] = 'text that is not on the page'
    elif mutation == 'skip-with-findings':
        skip = next(r for r in d['responses'] if (r['documentId'], r['task']) == SKIP)
        skip['materialized'] = {'findings': [{'metric': 'x', 'entity': 'x', 'value': '7', 'unit': 'kg', 'period': '', 'quote': 'x', 'page': 1}]}
    elif mutation == 'skip-on-other-task':
        plan = next(r for r in d['plan'] if (r['documentId'], r['task']) == ('financial-01', 'summarize'))
        for target in (plan, row):
            target.update({'request': None, 'promptSha256': None, 'deterministicSkip': True})
    else:
        plan = next(r for r in d['plan'] if (r['documentId'], r['task']) == ('financial-01', 'summarize'))
        props = plan['request']['response_format']['json_schema']['schema']['properties']['findings']['items']['properties']
        props['from'] = {'type': 'integer'}
        row['request'] = copy.deepcopy(plan['request'])
    save(p, d)
    result, output = execute(run_data, '--allow-partial')
    assert result.returncode != 0
    assert not output.exists()
    expected = {'quote-not-on-page': 'quote is not on the cited page', 'skip-with-findings': 'abstention row is not empty',
                'skip-on-other-task': 'only Key Figures may abstain', 'unbounded-line': 'line fields must be bounded'}[mutation]
    assert expected in result.stderr, result.stderr


def refresh_fixture_verification(work):
    path = work / 'verify-findings.json'
    data = json.load(open(path))
    rows = findings = 0
    for file in data['generatedFindingVerification']['files']:
        report = work / file['path'].split('/')[-1]
        file['sha256'] = hashlib.sha256(report.read_bytes()).hexdigest()
        counts = {'responseRows': len(file['rows']), 'findings': sum(len(r['findings']) for r in file['rows'])}
        file['summary'] = counts
        rows += counts['responseRows']
        findings += counts['findings']
    data['generatedFindingVerification']['summary'] = {'responseRows': rows, 'findings': findings}
    save(path, data)


def test_cite_real_runner_skip_allows_null_token_usage(run_data):
    work, _ = run_data
    to_cite(work)
    for name in ('qwen35-2b.json', 'qwen35-0.8b.json'):
        path = work / name
        data = json.load(open(path))
        next(r for r in data['responses'] if (r['documentId'], r['task']) == SKIP)['tokenUsage'] = None
        save(path, data)
    refresh_fixture_verification(work)
    result, output = execute(run_data)
    assert result.returncode == 0, result.stderr
    assert json.load(open(output))['status'] == 'completed'


def test_cite_all_rejected_output_is_not_a_correct_abstention(run_data):
    work, _ = run_data
    to_cite(work)
    gold = json.load(open(work / 'gold-frozen.json'))
    next(d for d in gold['documents'] if d['id'] == 'financial-01')['tasks']['figures']['absenceExpected'] = True
    save(work / 'gold-frozen.json', gold)
    for name in ('qwen35-2b.json', 'qwen35-0.8b.json'):
        path = work / name
        data = json.load(open(path))
        row = next(r for r in data['responses'] if (r['documentId'], r['task']) == ('financial-01', 'figures'))
        row['materialized'] = {'findings': []}
        row['materializationRejected'] = [{'index': 0, 'reason': 'Value does not occur as a figure on the cited line.'}]
        row['assessment'].update({'findingsCount': 0, 'exactQuoteCount': 0})
        save(path, data)
    for category in ('financial',):
        path = work / f'grades-{category}.json'
        data = json.load(open(path))
        for g in data['grades']:
            if (g['documentId'], g['task']) == ('financial-01', 'figures'):
                g.update({k: True for k in ('factualCorrect','relevant','adequateCoverage','evidenceCorrect','strictPass')})
                g['numeric'] = {k: 0 for k in g['numeric']}
                g['quotes'] = {'records': 0, 'exactOnPage': 0}
                g['unsupportedFindings'] = 0
        save(path, data)
    # Align task-5 records to the intentionally empty materialized output.
    path = work / 'verify-findings.json'
    verification = json.load(open(path))
    for file in verification['generatedFindingVerification']['files']:
        for row in file['rows']:
            if (row['documentId'], row['task']) == ('financial-01', 'figures'):
                row['findings'] = []
    save(path, verification)
    refresh_fixture_verification(work)
    result, output = execute(run_data)
    assert result.returncode == 0, result.stderr
    data = json.load(open(output))
    for model in data['models'].values():
        assert model['byTask']['figures']['correctAbstentions'] == 0
        assert model['byTask']['figures']['materializationRejected'] == 1


def test_cite_partial_rejection_is_reported_without_discarding_kept_finding(run_data):
    work, _ = run_data
    to_cite(work)
    for name in ('qwen35-2b.json', 'qwen35-0.8b.json'):
        path = work / name
        data = json.load(open(path))
        row = next(r for r in data['responses'] if (r['documentId'], r['task']) == ('financial-01', 'figures'))
        row['materializationRejected'] = [{'index': 1, 'reason': 'Value does not occur as a figure on the cited line.'}]
        save(path, data)
    refresh_fixture_verification(work)
    result, output = execute(run_data)
    assert result.returncode == 0, result.stderr
    for model in json.load(open(output))['models'].values():
        figures = model['byTask']['figures']
        assert figures['materializationRejected'] == 1
        assert figures['numeric']['records'] == 29
        assert figures['strictPass']['count'] == 29
