"""No-model regression checks for the public five-function aggregation boundary."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).parent / 'apt' / 'five_task_summarize.py'
TASKS = ('summarize', 'insights', 'figures', 'risks')
FIELDS = {'summarize': ['claim', 'quote', 'page'], 'insights': ['claim', 'quote', 'page'],
          'figures': ['metric', 'entity', 'value', 'unit', 'period', 'quote', 'page'],
          'risks': ['obligation', 'party', 'deadline', 'exception', 'quote', 'page']}
SECRET = 'PRIVATE_SOURCE_AND_OUTPUT_SENTINEL'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


@pytest.fixture
def run_data(tmp_path):
    """A hand-controlled complete 30-document paired run; no service or model calls."""
    work = tmp_path / 'input'
    work.mkdir()
    docs = [{'id': f'{category}-{n:02}', 'title': f'{category} public document {n}',
             'category': category, 'sourceUrl': f'https://example.gov/{category}-{n}.pdf',
             'sha256': digest(f'pdf-{category}-{n}'), 'bytes': 100,
             'pdfPath': '/private/never/publish.pdf',
             'pages': [{'page': 1, 'text': SECRET + ' source 7 kg.'}]}
            for category in ('financial', 'technical', 'contractual') for n in range(1, 11)]
    save(work / 'corpus.json', {'documents': docs})
    corpus_hash = hashlib.sha256((work / 'corpus.json').read_bytes()).hexdigest()
    gold = {'provenance': 'Agent annotations, not expert ground truth', 'corpusSha256': corpus_hash,
            'documents': [{'id': d['id'], 'sourceSha256': d['sha256'],
                           'tasks': {t: {'anchors': [{'fact': SECRET, 'page': 1, 'evidence': SECRET}],
                                         'absenceExpected': False} for t in TASKS}} for d in docs]}
    save(work / 'gold-frozen.json', gold)
    grades = {category: [] for category in ('financial', 'technical', 'contractual')}
    for candidate, filename, model_name in [('A', 'qwen35-2b.json', 'Qwen3.5-2B-Q4_K_M.gguf'),
                                           ('B', 'qwen35-0.8b.json', 'Qwen3.5-0.8B-Q4_K_M.gguf')]:
        report = {'status': 'completed', 'createdAt': '2026-01-01T00:01:00+00:00',
                  'corpusSha256': corpus_hash, 'goldUsedInPromptsOrAutomaticEvidenceScoring': False,
                  'model': {'repo': 'example/model', 'filename': model_name, 'sha256': digest(model_name),
                            'bytes': 1000, 'revision': 'pinned', 'quantization': 'Q4_K_M', 'localPath': '/private/model'},
                  'verifiedModelSha256': digest(model_name), 'serverBinarySha256': 'c' * 64,
                  'expectedRuntimeCommit': 'd' * 40, 'serverVersion': 'test-runtime',
                  'host': {'system': 'Linux', 'machine': 'x86_64'},
                  'serverArguments': ['--model', '/private/model', '--cache-ram', '0'],
                  'protocol': {'tasks': list(TASKS), 'fields': FIELDS, 'maximumFindings': 2,
                               'maximumOutputTokens': 512, 'contextTokens': 8192, 'maximumInputCharacters': 20000,
                               'temperature': 0, 'seed': 0}, 'documents': [], 'plan': [], 'responses': []}
        for d in docs:
            pages = d['pages']
            input_hash = digest(json.dumps(pages, ensure_ascii=False, sort_keys=True))
            coverage = {'wholeDocumentTextIncluded': True, 'sourcePageCount': 1,
                        'sourceTextCharacters': len(pages[0]['text']), 'includedCharacters': len(pages[0]['text']),
                        'omittedSourceCharacters': 0, 'includedPageNumbers': [1], 'omittedPageNumbers': [],
                        'sectionTruncated': False}
            report['documents'].append({'id': d['id'], 'title': d['title'],
                'sourcePages': [{'page': 1, 'characters': len(pages[0]['text']), 'sha256': digest(pages[0]['text'])}],
                'sections': [{'id': 'main', 'pages': copy.deepcopy(pages), 'coverage': coverage, 'inputSha256': input_hash}]})
            for task in TASKS:
                prompt = f'Task {task}\n[PAGE 1]\n{pages[0]["text"]}\nEND PDF EXCERPTS'
                request = {'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0, 'seed': 0,
                           'max_tokens': 512, 'response_format': {'type': 'json_schema', 'json_schema': {
                               'name': task + '_findings', 'strict': True, 'schema': {
                                   'type': 'object', 'properties': {'findings': {'type': 'array', 'maxItems': 2,
                                       'items': {'type': 'object', 'additionalProperties': False, 'required': FIELDS[task],
                                                 'properties': {key: {'type': 'integer', 'enum': [1]} if key == 'page' else
                                                     {'type': 'string', 'maxLength': {'claim': 240, 'quote': 160, 'metric': 80,
                                                      'entity': 80, 'value': 48, 'unit': 48, 'period': 64, 'obligation': 200,
                                                      'party': 80, 'deadline': 100, 'exception': 160}[key]} for key in FIELDS[task]}}}},
                                   'required': ['findings'], 'additionalProperties': False}}}}
                plan = {'documentId': d['id'], 'sectionId': 'main', 'task': task, 'coverage': coverage,
                        'inputSha256': input_hash, 'promptSha256': digest(prompt), 'request': request}
                report['plan'].append(copy.deepcopy(plan))
                finding = {k: SECRET for k in FIELDS[task]}
                finding['page'] = 1
                row = {**copy.deepcopy(plan), 'prompt': prompt, 'renderedPrompt': SECRET,
                       'rawContent': json.dumps({'findings': [finding]}), 'parsedContent': {'findings': [finding]},
                       'finish_reason': 'stop', 'milliseconds': 10.0,
                       'api': {'httpStatus': 200, 'rawResponse': SECRET},
                       'assessment': {'schemaValid': True, 'httpSuccessful': True, 'completedWithinBudget': True,
                                      'findingsCount': 1, 'exactQuoteCount': 1,
                                      'evidence': [{'findingIndex': 0, 'validRecord': True, 'exactQuoteOnCitedPage': True}]}}
                report['responses'].append(row)
                grades[d['category']].append({'documentId': d['id'], 'candidate': candidate, 'task': task,
                    'technicalComplete': True, 'factualCorrect': True, 'relevant': True, 'adequateCoverage': True,
                    'evidenceCorrect': True, 'strictPass': True, 'reasons': ['Grounded claim; quoted passage “' + SECRET + '” was checked.'],
                    'numeric': {'records': int(task == 'figures'), 'fullyCorrect': int(task == 'figures'),
                                'valueCorrect': int(task == 'figures'), 'unitCorrect': int(task == 'figures'),
                                'periodCorrect': int(task == 'figures'), 'entityCorrect': int(task == 'figures')},
                    'quotes': {'records': 1, 'exactOnPage': 1}, 'unsupportedFindings': 0})
        save(work / filename, report)
    for category, values in grades.items():
        save(work / f'grades-{category}.json', {'grades': values})
    verification = {'corpusSha256': corpus_hash, 'modelCalls': 0,
        'documents': [{'documentId': d['id'], 'checks': [{'kind': 'exact-real-passage', 'expected': 'exact-text-match',
                       'actual': 'exact-text-match', 'passed': True, 'query': SECRET, 'sourceContext': SECRET}]} for d in docs],
        'sourceIntegrity': {'passed': 30, 'failed': 0, 'byKind': {'exact-real-passage': {'passed': 30, 'failed': 0}}},
        'semanticVerification': {'implemented': False, 'score': None,
                                 'observedContextChallenges': [{'query': SECRET, 'sourceContext': SECRET}]},
        'browser': {'status': 'passed', 'modelCalls': 0, 'network': [], 'errors': [],
                    'checks': [{'documentId': d['id'], 'passed': True, 'modelCalls': 0, 'taskChoices': 5,
                                'exactMatchUI': True, 'unsupportedUI': True, 'highlightCount': 1,
                                'citationChangedPhysicalPage': True, 'indexedSource': {'text': SECRET}} for d in docs]},
        'generatedFindingVerification': {'modelReportsComplete': True, 'files': [],
                                         'summary': {'responseRows': 240, 'findings': 240}}}
    for filename in ('qwen35-2b.json', 'qwen35-0.8b.json'):
        report = json.load(open(work / filename))
        verification['generatedFindingVerification']['files'].append({
            'path': str(work / filename), 'sha256': hashlib.sha256((work / filename).read_bytes()).hexdigest(),
            'modelName': report['model']['filename'], 'reportComplete': True, 'receivedResponses': 120,
            'plannedResponses': 120, 'rows': [{'documentId': r['documentId'], 'task': r['task'],
                                               'findings': [{'rawFinding': r['parsedContent']['findings'][0],
                                                             'quoteCheck': {'accepted': True, 'acceptedAtRequestedPage': True}}]}
                                              for r in report['responses']]})
    save(work / 'verify-findings.json', verification)
    save(work / 'memory-monitor.json', {'scope': 'External /proc host samples', 'samples': [
        {'model': 'Qwen3.5-0.8B-Q4_K_M.gguf', 'hostPid': 100, 'time': '2026-01-01T00:00:00+00:00', 'rssBytes': 9000, 'peakRssBytes': 10000},
        {'model': 'Qwen3.5-0.8B-Q4_K_M.gguf', 'hostPid': 101, 'time': '2026-01-01T00:01:01+00:00', 'rssBytes': 2000, 'peakRssBytes': 3000},
        {'model': 'Qwen3.5-2B-Q4_K_M.gguf', 'hostPid': 102, 'time': '2026-01-01T00:01:01+00:00', 'rssBytes': 4000, 'peakRssBytes': 5000}]})
    return work, tmp_path / 'public'


def execute(run_data, *extra):
    work, output = run_data
    result = subprocess.run([sys.executable, str(SCRIPT), '--workdir', str(work), '--outputdir', str(output), *extra],
                            capture_output=True, text=True)
    return result, output / 'results.json'


def test_complete_run_publishes_counts_without_source_or_output_text(run_data):
    # Catches accidental publication of source, prompts, generated claims, or verifier context.
    result, output = execute(run_data)
    assert result.returncode == 0, result.stderr
    public = output.read_text()
    assert SECRET not in public
    assert '/private/' not in public
    data = json.loads(public)
    assert data['status'] == 'completed'
    assert data['completion']['uniqueGradedCases'] == 240
    assert data['models']['qwen35-2b']['byTask']['figures']['contentPass']['count'] == 30
    assert data['models']['qwen35-2b']['byTask']['figures']['numeric']['records'] == 30
    assert data['verification']['semanticVerification']['implemented'] is False
    assert data['verification']['semanticVerification']['score'] is None
    assert data['memory']['latestCacheRamZeroPhase']['qwen35-0.8b']['hostPid'] == 101
    assert data['memory']['byPid'][0]['peakHwmBytes'] == 10000


def test_default_refuses_missing_grades_but_partial_preview_is_explicit(run_data):
    # Catches treating 239 judgments as completed 240-case evaluation.
    work, _ = run_data
    p = work / 'grades-technical.json'
    d = json.load(open(p)); d['grades'].pop(); save(p, d)
    result, output = execute(run_data)
    assert result.returncode != 0
    assert not output.exists()
    result, output = execute(run_data, '--allow-partial')
    assert result.returncode == 0, result.stderr
    assert json.load(open(output))['status'] == 'partial'


@pytest.mark.parametrize('mutation', ['strict', 'count', 'boolean'])
def test_rejects_inconsistent_or_untyped_grade_metrics(run_data, mutation):
    # Catches inflated strict success, out-of-range numeric scores, and truthy string booleans.
    work, _ = run_data
    p = work / 'grades-financial.json'; d = json.load(open(p))
    g = next(g for g in d['grades'] if g['task'] == 'figures')
    if mutation == 'strict': g['strictPass'] = False
    elif mutation == 'count': g['numeric']['fullyCorrect'] = 2
    else: g['factualCorrect'] = 'true'
    save(p, d)
    result, output = execute(run_data, '--allow-partial')
    assert result.returncode != 0
    assert not output.exists()


def test_rejects_cross_model_prompt_or_source_coverage_drift(run_data):
    # Catches requests that claim full coverage while including altered source or prompt text.
    work, _ = run_data
    p = work / 'qwen35-2b.json'; d = json.load(open(p))
    d['plan'][0]['request']['messages'][0]['content'] += ' changed instructions'
    save(p, d)
    result, output = execute(run_data, '--allow-partial')
    assert result.returncode != 0
    assert not output.exists()


@pytest.mark.parametrize('absence_expected, expected_passes', [(False, 0), (True, 30)])
def test_empty_outputs_only_pass_explicitly_expected_abstention_and_have_no_numeric_precision(run_data, absence_expected, expected_passes):
    # Catches vacuous accuracy rewards and 0/0 being reported as perfect numeric precision.
    work, _ = run_data
    gold_path = work / 'gold-frozen.json'; gold = json.load(open(gold_path))
    for doc in gold['documents']:
        doc['tasks']['figures']['absenceExpected'] = absence_expected
    save(gold_path, gold)
    for name in ('qwen35-2b.json', 'qwen35-0.8b.json'):
        p = work / name; report = json.load(open(p))
        for row in report['responses']:
            if row['task'] == 'figures':
                row['rawContent'] = '{"findings": []}'
                row['parsedContent'] = {'findings': []}
                row['assessment']['findingsCount'] = 0
                row['assessment']['exactQuoteCount'] = 0
                row['assessment']['evidence'] = []
        save(p, report)
    for category in ('financial', 'technical', 'contractual'):
        p = work / f'grades-{category}.json'; data = json.load(open(p))
        for grade in data['grades']:
            if grade['task'] == 'figures':
                grade['numeric'] = {key: 0 for key in grade['numeric']}
                grade['quotes'] = {'records': 0, 'exactOnPage': 0}
        save(p, data)
    verification_path = work / 'verify-findings.json'
    verification = json.load(open(verification_path)); verification.pop('generatedFindingVerification'); save(verification_path, verification)
    result, output = execute(run_data, '--allow-partial')
    assert result.returncode == 0, result.stderr
    figures = json.load(open(output))['models']['qwen35-2b']['byTask']['figures']
    assert figures['contentPass']['count'] == expected_passes
    assert figures['factualCorrect']['count'] == expected_passes
    assert figures['correctAbstentions'] == expected_passes
    assert figures['numeric']['fullyCorrect']['rate'] is None
    assert figures['numeric']['records'] == 0


def test_rejects_duplicate_grades_and_partial_pdf_claims(run_data):
    # Catches duplicated judgments and a prompt plan mislabeled as full-PDF coverage.
    work, _ = run_data
    p = work / 'grades-technical.json'; data = json.load(open(p)); data['grades'].append(data['grades'][0]); save(p, data)
    result, output = execute(run_data, '--allow-partial')
    assert result.returncode != 0
    assert not output.exists()
    data['grades'].pop(); save(p, data)
    p = work / 'qwen35-2b.json'; report = json.load(open(p))
    report['documents'][0]['sections'][0]['coverage']['omittedSourceCharacters'] = 7
    save(p, report)
    result, output = execute(run_data, '--allow-partial')
    assert result.returncode != 0
    assert not output.exists()


def refresh_verification_references(work):
    path = work / 'verify-findings.json'; verification = json.load(open(path))
    for checked_file in verification['generatedFindingVerification']['files']:
        report_path = Path(checked_file['path']); report = json.load(open(report_path))
        checked_file['sha256'] = hashlib.sha256(report_path.read_bytes()).hexdigest()
        source = {(r['documentId'], r['task']): r for r in report['responses']}
        for row in checked_file['rows']:
            findings = source[row['documentId'], row['task']]['parsedContent']['findings']
            row['findings'] = [{'rawFinding': f, 'quoteCheck': {'accepted': True, 'acceptedAtRequestedPage': True}} for f in findings]
    save(path, verification)


def test_redacts_unquoted_generated_claims_from_reasons(run_data):
    # Catches copied output surviving because it differs from the finding's quote.
    work, _ = run_data
    secret_claim = 'DISTINCT_UNQUOTED_GENERATED_CLAIM_SENTINEL'
    p = work / 'qwen35-2b.json'; report = json.load(open(p)); row = report['responses'][0]
    row['parsedContent']['findings'][0]['claim'] = secret_claim
    row['rawContent'] = json.dumps(row['parsedContent']); save(p, report)
    p = work / 'grades-financial.json'; grades = json.load(open(p))
    grades['grades'][0]['reasons'] = ['The copied generated claim is ' + secret_claim + ' and it is grounded.']; save(p, grades)
    refresh_verification_references(work)
    result, output = execute(run_data)
    assert result.returncode == 0, result.stderr
    assert secret_claim not in output.read_text()


def test_does_not_trust_a_schema_valid_flag_for_extra_top_level_content(run_data):
    # Catches technically malformed content being counted complete because a flag says true.
    work, _ = run_data
    p = work / 'qwen35-2b.json'; report = json.load(open(p)); row = report['responses'][0]
    row['parsedContent']['unexpected'] = SECRET; row['rawContent'] = json.dumps(row['parsedContent']); save(p, report)
    refresh_verification_references(work)
    result, output = execute(run_data, '--allow-partial')
    assert result.returncode != 0
    assert not output.exists()


@pytest.mark.parametrize('opening, closing', [("'", "'"), ('‘', '’')])
def test_redacts_shorter_single_quoted_source_fragments_in_reasons(run_data, opening, closing):
    # Catches copied fragments that are shorter than any complete quote or claim field.
    work, _ = run_data
    fragment = 'SEPARATE_SOURCE_FRAGMENT'
    p = work / 'grades-financial.json'; data = json.load(open(p))
    data['grades'][0]['reasons'] = ['The phrase ' + opening + fragment + closing + ' lacks a qualification.']; save(p, data)
    result, output = execute(run_data)
    assert result.returncode == 0, result.stderr
    assert fragment not in output.read_text()


@pytest.mark.parametrize('mutation', ['missing-finding', 'inflated-counter'])
def test_rejects_incomplete_or_inflated_actual_output_verification(run_data, mutation):
    # Catches calling the fifth function complete without checking every finding honestly.
    work, _ = run_data
    p = work / 'verify-findings.json'; data = json.load(open(p))
    if mutation == 'missing-finding':
        data['generatedFindingVerification']['files'][0]['rows'][0]['findings'] = []
    else:
        data['generatedFindingVerification']['summary']['exactQuoteAcceptedAtRequestedPage'] = 9999
    save(p, data)
    result, output = execute(run_data, '--allow-partial')
    assert result.returncode != 0
    assert not output.exists()


def test_unknown_model_field_names_cannot_leak_through_length_metadata():
    # Catches model-generated key text being copied into the public metadata key space.
    import runpy
    module = runpy.run_path(str(SCRIPT))
    row = {'task': 'summarize', 'rawContent': '{}', 'parsedContent': {'findings': [
        {'PRIVATE_MODEL_KEY_SOURCE_TEXT': 'value', 'quote': 'exact', 'page': 1}]},
        'assessment': {'schemaValid': False, 'httpSuccessful': True, 'completedWithinBudget': True},
        'tokenUsage': {'PRIVATE_TOKEN_KEY_SOURCE_TEXT': 2}}
    metadata = module['raw_case_metadata'](row, {'pages': [{'page': 1, 'text': 'exact source'}]})
    assert 'PRIVATE_MODEL_KEY_SOURCE_TEXT' not in json.dumps(metadata)
    assert 'PRIVATE_TOKEN_KEY_SOURCE_TEXT' not in json.dumps(metadata)
