"""Aggregate the completed paired five-function evaluation without running models.

Default: require two complete 120-response reports, 240 unique source-reviewed
case grades, identical whole-document requests, and completed independent task-5
checks. --allow-partial writes a clearly marked preview, never a completion claim.
Only whitelisted metadata is published; source text, prompts, quotations and raw
model outputs stay in the private work directory. No application code is changed.
"""
import argparse
from collections import Counter, defaultdict
import datetime
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

TASKS = ('summarize', 'insights', 'figures', 'risks')
CATEGORIES = ('contractual', 'financial', 'technical')
# Unblinded only here, after independent grading. Never copy this into grader inputs.
CANDIDATES = {'A': 'qwen35-2b', 'B': 'qwen35-0.8b'}
GRADE_FLAGS = ('technicalComplete', 'factualCorrect', 'relevant', 'adequateCoverage', 'evidenceCorrect', 'strictPass')
NUMERIC_FIELDS = ('fullyCorrect', 'valueCorrect', 'unitCorrect', 'entityCorrect', 'periodCorrect')
LENGTHS = {'claim': 240, 'quote': 160, 'metric': 80, 'entity': 80, 'value': 48, 'unit': 48,
           'period': 64, 'obligation': 200, 'party': 80, 'deadline': 100, 'exception': 160}
FIELDS = {'summarize': ('claim', 'quote', 'page'), 'insights': ('claim', 'quote', 'page'),
          'figures': ('metric', 'entity', 'value', 'unit', 'period', 'quote', 'page'),
          'risks': ('obligation', 'party', 'deadline', 'exception', 'quote', 'page')}


class InvalidEvaluation(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidEvaluation(message)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf-8')).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def read_json(path, optional=False):
    if optional and not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise InvalidEvaluation(f'{path.name}: cannot read JSON: {error}') from error


def nonnegative_integer(value, label):
    require(type(value) is int and value >= 0, f'{label}: expected a nonnegative integer')
    return value


def ratio(count, denominator):
    return {'count': count, 'denominator': denominator,
            'rate': count / denominator if denominator else None}


def keyed(rows, key, label):
    result = {}
    require(isinstance(rows, list), f'{label}: expected a list')
    for row in rows:
        require(isinstance(row, dict), f'{label}: expected object rows')
        k = key(row)
        require(k not in result, f'{label}: duplicate case {k}')
        result[k] = row
    return result


def case_key(row):
    return row.get('documentId'), row.get('task')


def prompt_text(request):
    messages = request.get('messages') if isinstance(request, dict) else None
    require(isinstance(messages, list) and len(messages) == 1 and
            isinstance(messages[0], dict) and messages[0].get('role') == 'user' and
            isinstance(messages[0].get('content'), str), 'Request must contain one user prompt')
    return messages[0]['content']


def validate_coverage(coverage, pages, label):
    chars = sum(len(p['text']) for p in pages)
    require(isinstance(coverage, dict) and coverage.get('wholeDocumentTextIncluded') is True,
            f'{label}: whole PDF text was not included')
    for key in ('sourcePageCount', 'sourceTextCharacters', 'includedCharacters', 'omittedSourceCharacters'):
        nonnegative_integer(coverage.get(key), label + '/' + key)
    require(coverage.get('sourcePageCount') == len(pages) and
            coverage.get('sourceTextCharacters') == chars and coverage.get('includedCharacters') == chars and
            coverage.get('omittedSourceCharacters') == 0 and coverage.get('omittedPageNumbers') == [] and
            coverage.get('includedPageNumbers') == sorted(p['page'] for p in pages) and
            coverage.get('sectionTruncated') is False, f'{label}: coverage metadata does not match the whole PDF')


def validate_report(report, model_id, docs, corpus_hash, issues):
    require(isinstance(report, dict), f'{model_id}: missing report')
    require(report.get('corpusSha256') == corpus_hash, f'{model_id}: frozen corpus fingerprint mismatch')
    require(report.get('goldUsedInPromptsOrAutomaticEvidenceScoring') is False,
            f'{model_id}: gold must not be used in prompts or automatic scoring')
    model = report.get('model', {})
    require(isinstance(model, dict) and model.get('sha256') == report.get('verifiedModelSha256'),
            f'{model_id}: verified model fingerprint mismatch')
    expected_filename = {'qwen35-2b': 'Qwen3.5-2B-Q4_K_M.gguf', 'qwen35-0.8b': 'Qwen3.5-0.8B-Q4_K_M.gguf'}[model_id]
    require(model.get('filename') == expected_filename, f'{model_id}: unexpected artifact filename')
    require(isinstance(model.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', model['sha256']),
            f'{model_id}: malformed model SHA-256')
    require(isinstance(model.get('filename'), str) and type(model.get('bytes')) is int and model['bytes'] > 0,
            f'{model_id}: missing pinned artifact size/name')
    report_docs = keyed(report.get('documents'), lambda x: x.get('id'), f'{model_id} documents')
    require(set(report_docs) == set(docs), f'{model_id}: document set differs from frozen corpus')
    inputs = {}
    for doc_id, source in docs.items():
        d = report_docs[doc_id]
        pages = source['pages']
        expected_pages = [{'page': p['page'], 'characters': len(p['text']), 'sha256': sha(p['text'])} for p in pages]
        require(d.get('sourcePages') == expected_pages, f'{model_id}/{doc_id}: source page identities differ')
        sections = d.get('sections')
        require(isinstance(sections, list) and len(sections) == 1 and sections[0].get('id') == 'main',
                f'{model_id}/{doc_id}: expected one complete main section')
        section = sections[0]
        require(section.get('pages') == pages, f'{model_id}/{doc_id}: section text is not the full frozen PDF')
        validate_coverage(section.get('coverage'), pages, f'{model_id}/{doc_id}')
        input_hash = sha(json.dumps(pages, ensure_ascii=False, sort_keys=True))
        require(section.get('inputSha256') == input_hash, f'{model_id}/{doc_id}: input fingerprint mismatch')
        inputs[doc_id] = input_hash
    expected = {(d, t) for d in docs for t in TASKS}
    plans = keyed(report.get('plan'), case_key, f'{model_id} plan')
    require(set(plans) == expected, f'{model_id}: expected exactly 120 planned document/task cases')
    for (doc_id, task), row in plans.items():
        require(row.get('sectionId') == 'main', f'{model_id}/{doc_id}/{task}: section differs')
        validate_coverage(row.get('coverage'), docs[doc_id]['pages'], f'{model_id}/{doc_id}/{task}')
        require(row.get('inputSha256') == inputs[doc_id], f'{model_id}/{doc_id}/{task}: input fingerprint differs')
        validate_request_schema(row.get('request', {}), task, docs[doc_id]['pages'])
        prompt = prompt_text(row.get('request'))
        require(row.get('promptSha256') == sha(prompt), f'{model_id}/{doc_id}/{task}: prompt fingerprint mismatch')
        require(all(f"[PAGE {p['page']}]\n{p['text']}" in prompt for p in docs[doc_id]['pages']),
                f'{model_id}/{doc_id}/{task}: prompt omits authoritative PDF text')
    rows = keyed(report.get('responses'), case_key, f'{model_id} responses')
    require(set(rows) <= expected, f'{model_id}: unexpected response case')
    for key, row in rows.items():
        plan = plans[key]
        for field in ('request', 'coverage', 'inputSha256', 'promptSha256', 'sectionId'):
            require(row.get(field) == plan.get(field), f'{model_id}/{key}: response {field} differs from frozen plan')
        require(row.get('prompt') == prompt_text(plan['request']), f'{model_id}/{key}: raw prompt differs from request')
        assessment = row.get('assessment')
        require(isinstance(assessment, dict), f'{model_id}/{key}: missing assessment')
        for field in ('schemaValid', 'httpSuccessful', 'completedWithinBudget'):
            require(type(assessment.get(field)) is bool, f'{model_id}/{key}: assessment {field} is not boolean')
        require(assessment['httpSuccessful'] == (row.get('api', {}).get('httpStatus') == 200),
                f'{model_id}/{key}: HTTP assessment differs')
        require(assessment['completedWithinBudget'] == (row.get('finish_reason') == 'stop'),
                f'{model_id}/{key}: output completion assessment differs')
        try:
            parsed_raw = json.loads(row.get('rawContent', ''))
        except (ValueError, TypeError):
            parsed_raw = None
        require(parsed_raw == row.get('parsedContent'), f'{model_id}/{key}: parsed content differs from raw output')
        schema = validate_request_schema(plan['request'], key[1], docs[key[0]]['pages'])
        require(assessment['schemaValid'] == schema_matches(parsed_raw, schema),
                f'{model_id}/{key}: schema-valid flag differs from actual raw output/schema')
        findings = parsed_findings(row)
        nonnegative_integer(assessment.get('findingsCount'), f'{model_id}/{key}/findingsCount')
        nonnegative_integer(assessment.get('exactQuoteCount'), f'{model_id}/{key}/exactQuoteCount')
        require(assessment.get('findingsCount') == len(findings), f'{model_id}/{key}: finding count differs')
    if report.get('status') != 'completed' or len(rows) != 120:
        issues.append(f'{model_id}: generation report {report.get("status")}, {len(rows)}/120 responses')
    return plans, rows


def schema_matches(value, schema):
    """Evaluate the bounded JSON-schema subset actually emitted by this harness."""
    kind = schema.get('type')
    if kind == 'object':
        if not isinstance(value, dict):
            return False
        properties = schema.get('properties', {})
        return (all(k in value for k in schema.get('required', [])) and
                (schema.get('additionalProperties') is not False or set(value) <= set(properties)) and
                all(k not in properties or schema_matches(v, properties[k]) for k, v in value.items()))
    if kind == 'array':
        return isinstance(value, list) and len(value) <= schema.get('maxItems', len(value)) and all(
            schema_matches(v, schema.get('items', {})) for v in value)
    if kind == 'string':
        return isinstance(value, str) and len(value) <= schema.get('maxLength', len(value))
    if kind == 'integer':
        return type(value) is int and ('enum' not in schema or value in schema['enum'])
    return False


def validate_request_schema(request, task, pages):
    response = request.get('response_format', {})
    wrapper = response.get('json_schema', {})
    schema = wrapper.get('schema', {})
    require(response.get('type') == 'json_schema' and wrapper.get('strict') is True and
            wrapper.get('name') == task + '_findings', 'Missing strict task JSON schema')
    require(schema.get('type') == 'object' and schema.get('required') == ['findings'] and
            schema.get('additionalProperties') is False and set(schema.get('properties', {})) == {'findings'},
            'Unexpected top-level task schema')
    array = schema['properties']['findings']
    require(array.get('type') == 'array' and type(array.get('maxItems')) is int and 0 < array['maxItems'] <= 2,
            'Task schema is not bounded to at most two findings')
    item = array.get('items', {})
    properties = item.get('properties', {})
    require(item.get('type') == 'object' and item.get('additionalProperties') is False and
            set(item.get('required', [])) == set(FIELDS[task]) and set(properties) == set(FIELDS[task]),
            'Task finding schema differs from expected fields')
    for field, rules in properties.items():
        if field == 'page':
            require(rules.get('type') == 'integer' and rules.get('enum') == sorted(p['page'] for p in pages),
                    'Task page schema differs from source physical pages')
        else:
            bound = rules.get('maxLength')
            require(rules.get('type') == 'string' and type(bound) is int and 0 < bound <= LENGTHS[field],
                    'Task string fields must have bounded lengths')
    return schema


def parsed_findings(row):
    parsed = row.get('parsedContent')
    return parsed['findings'] if isinstance(parsed, dict) and isinstance(parsed.get('findings'), list) else []


def record_valid(finding, task, pages):
    return (isinstance(finding, dict) and set(finding) == set(FIELDS[task]) and
            all(type(finding.get(k)) is int if k == 'page' else isinstance(finding.get(k), str) for k in FIELDS[task]) and
            finding['page'] in pages)


def raw_case_metadata(row, doc):
    task = row['task']
    pages = {p['page']: p['text'] for p in doc['pages']}
    findings = parsed_findings(row)
    valid = [f for f in findings if record_valid(f, task, pages)]
    exact = sum(bool(f['quote'].strip()) and f['quote'] in pages[f['page']] for f in valid)
    raw = row.get('rawContent', '')
    require(isinstance(raw, str), 'rawContent must be a string')
    flags = row['assessment']
    return {'rawOutputSha256': sha(raw), 'rawOutputCharacters': len(raw),
            'rawOutputUtf8Bytes': len(raw.encode('utf-8')), 'parsedFindings': len(findings),
            'validFindingRecords': len(valid), 'literalExactQuoteRecords': exact,
            'fieldLengths': [{'findingIndex': i, 'page': f.get('page') if type(f.get('page')) is int else None,
                             'characters': {k: len(v) for k, v in f.items() if k in FIELDS[task] and isinstance(v, str)}}
                            for i, f in enumerate(findings) if isinstance(f, dict)],
            'finishReason': row.get('finish_reason'), 'httpStatus': row.get('api', {}).get('httpStatus'),
            'milliseconds': row.get('milliseconds'),
            'technicalComplete': all(flags[k] for k in ('schemaValid', 'httpSuccessful', 'completedWithinBudget')),
            'tokenUsage': {k: v for k, v in row.get('tokenUsage', {}).items() if k in ('completion_tokens', 'prompt_tokens', 'total_tokens') and type(v) in (int, float)}}


def validate_grade(grade, metadata, label):
    for key in GRADE_FLAGS:
        require(type(grade.get(key)) is bool, f'{label}: {key} must be a boolean')
    expected_strict = all(grade[k] for k in GRADE_FLAGS[:-1])
    require(grade['strictPass'] == expected_strict, f'{label}: strictPass must equal all five constituent booleans')
    require(grade['technicalComplete'] == metadata['technicalComplete'], f'{label}: technical completion differs from actual response')
    require(isinstance(grade.get('reasons'), list) and all(isinstance(x, str) for x in grade['reasons']),
            f'{label}: reasons must be strings')
    q = grade.get('quotes')
    require(isinstance(q, dict), f'{label}: missing quote counts')
    records = nonnegative_integer(q.get('records'), label + '/quotes.records')
    exact = nonnegative_integer(q.get('exactOnPage'), label + '/quotes.exactOnPage')
    require(records == metadata['parsedFindings'] and exact <= records, f'{label}: quote counts exceed/mismatch response records')
    n = grade.get('numeric')
    require(isinstance(n, dict), f'{label}: missing numeric counts')
    count = nonnegative_integer(n.get('records'), label + '/numeric.records')
    require(count == (metadata['parsedFindings'] if grade['task'] == 'figures' else 0),
            f'{label}: numeric records must describe figures only')
    for key in NUMERIC_FIELDS:
        nonnegative_integer(n.get(key), label + '/numeric.' + key)
        require(n[key] <= count, f'{label}: numeric {key} exceeds records')
    require(n['fullyCorrect'] <= min(n[k] for k in NUMERIC_FIELDS[1:]), f'{label}: full numeric correctness exceeds a component')
    unsupported = nonnegative_integer(grade.get('unsupportedFindings'), label + '/unsupportedFindings')
    require(unsupported <= metadata['parsedFindings'], f'{label}: unsupported count exceeds findings')


def redact_reasons(reasons, sensitive):
    result = []
    for original in reasons:
        text = original
        for quote in sensitive:
            if len(quote) >= 3:
                text = text.replace(quote, '[quotation redacted]')
        # Preserve the rationale around copied snippets without publishing quotations.
        text = re.sub(r"“[^”]*”|‘[^’]*’|\"[^\"\n]*\"|`[^`\n]*`|(?<!\w)'[^'\n]+'(?!\w)", "[quotation redacted]", text)
        result.append({'text': text, 'originalSha256': sha(original), 'originalCharacters': len(original)})
    return result


def summarize_cases(cases, denominator):
    def eligible(c):
        return c['raw']['technicalComplete'] and (c['raw']['validFindingRecords'] > 0 or c['correctAbstention'])
    counts = {'technicalComplete': sum(c['raw']['technicalComplete'] for c in cases),
              'contentPass': sum(c['contentPass'] for c in cases), 'strictPass': sum(c['strictPass'] for c in cases),
              'factualCorrect': sum(eligible(c) and c['grade']['factualCorrect'] for c in cases)}
    q_records = sum(c['grade']['quotes']['records'] for c in cases)
    result = {'documentCases': denominator, 'gradedCases': len(cases),
              **{k: ratio(v, denominator) for k, v in counts.items()},
              'emptyResponses': sum(c['raw']['parsedFindings'] == 0 for c in cases),
              'correctAbstentions': sum(c['correctAbstention'] for c in cases),
              'unsupportedFindings': sum(c['grade']['unsupportedFindings'] for c in cases),
              'quotes': {'records': q_records,
                         'literalExactOnPage': ratio(sum(c['raw']['literalExactQuoteRecords'] for c in cases), q_records),
                         'graderExactOnPage': ratio(sum(c['grade']['quotes']['exactOnPage'] for c in cases), q_records)}}
    if cases and all(c['task'] == 'figures' for c in cases):
        records = sum(c['grade']['numeric']['records'] for c in cases)
        result['numeric'] = {'records': records, **{k: ratio(sum(c['grade']['numeric'][k] if c['raw']['technicalComplete'] else 0
                                                               for c in cases), records) for k in NUMERIC_FIELDS}}
    times = [c['raw']['milliseconds'] for c in cases if type(c['raw']['milliseconds']) in (int, float)]
    result['medianRequestMilliseconds'] = statistics.median(times) if times else None
    return result


def sanitized_model(report):
    model = report['model']
    arguments = list(report.get('serverArguments', []))
    for index, value in enumerate(arguments):
        if index and arguments[index - 1] == '--model':
            arguments[index] = '<verified-local-model>'
        elif isinstance(value, str) and value.startswith('/'):
            arguments[index] = '<local-path>'
    return {'artifact': {k: model[k] for k in ('repo', 'revision', 'filename', 'bytes', 'sha256', 'quantization') if k in model},
            'verifiedModelSha256': report.get('verifiedModelSha256'),
            'runtime': {**{k: report.get(k) for k in ('serverBinarySha256', 'expectedRuntimeCommit', 'serverVersion')},
                        'host': {k: v for k, v in report.get('host', {}).items() if k in ('system', 'machine')},
                        'serverArguments': arguments},
            'additionalFineTuningPerformed': report.get('additionalFineTuningPerformed'),
            'startupMilliseconds': report.get('startupMilliseconds'),
            'sourceRunStatus': report.get('status'), 'receivedGenerations': len(report['responses'])}


def integer_counts(value):
    return {k: v for k, v in value.items() if type(v) is int and v >= 0} if isinstance(value, dict) else {}


def verification_count_names():
    return ('responseRows', 'malformedRows', 'findings', 'exactQuoteAccepted',
            'exactQuoteAcceptedAtRequestedPage', 'exactQuoteWrongPage', 'quoteRejected', 'quoteTooShort',
            'wholePageExactButIndexedSourceRejected', 'wholePageExactButTooShort',
            'wholePageExactSourceBoundaryRejections', 'statementTextExact', 'statementTextNotExact')


def verification_metadata(verification, docs, corpus_hash, reports, report_hashes, issues):
    initial_issues = len(issues)
    if not isinstance(verification, dict):
        issues.append('Fifth function: verification report is missing')
        return {'status': 'not-run', 'semanticVerification': {'implemented': False, 'score': None}}
    require(verification.get('corpusSha256') == corpus_hash, 'Verification uses a different frozen corpus')
    require(verification.get('modelCalls') == 0, 'Deterministic fifth function unexpectedly called a model')
    vd = keyed(verification.get('documents', []), lambda d: d.get('documentId'), 'verification documents')
    require(set(vd) <= set(docs), 'Verification contains unknown documents')
    if set(vd) != set(docs):
        issues.append('Fifth function: source integrity does not cover all 30 PDFs')
    integrity = verification.get('sourceIntegrity', {})
    actual = Counter()
    kinds = defaultdict(Counter)
    public_docs = []
    for doc_id, doc in vd.items():
        for check in doc.get('checks', []):
            require(type(check.get('passed')) is bool, 'Source integrity check lacks a boolean result')
            outcome = 'passed' if check['passed'] else 'failed'
            actual[outcome] += 1; kinds[check['kind']][outcome] += 1
        public_docs.append({'documentId': doc_id, 'checks': len(doc.get('checks', [])),
                            'passed': sum(c['passed'] for c in doc.get('checks', []))})
    require(integrity.get('passed') == actual['passed'] and integrity.get('failed') == actual['failed'],
            'Source integrity summary differs from its checks')
    for kind, count in kinds.items():
        require(integrity.get('byKind', {}).get(kind) == {'passed': count['passed'], 'failed': count['failed']},
                'Source integrity by-kind counts differ')
    if actual['failed']:
        issues.append('Fifth function: source integrity checks failed')
    semantic = verification.get('semanticVerification', {})
    require(semantic.get('implemented') is False and semantic.get('score') is None,
            'Do not assign a semantic score to the literal source verifier')
    browser = verification.get('browser', {})
    bc = keyed(browser.get('checks', []), lambda c: c.get('documentId'), 'browser checks')
    require(set(bc) <= set(docs), 'Browser checks contain unknown documents')
    if browser.get('status') != 'passed' or set(bc) != set(docs) or not all(c.get('passed') is True for c in bc.values()):
        issues.append('Fifth function: real-reader checks do not pass for all 30 PDFs')
    require(browser.get('modelCalls', 0) == 0 and all(c.get('modelCalls', 0) == 0 for c in bc.values()),
            'Fifth-function browser path called generation')
    if browser.get('network') or browser.get('errors'):
        issues.append('Fifth function: browser network attempts or errors were recorded')
    generated_issues_start = len(issues)
    generated = verification.get('generatedFindingVerification')
    public_generated = {'status': 'not-run', 'semanticDecision': 'not-provided'}
    if not isinstance(generated, dict):
        issues.append('Fifth function: actual generated findings were not independently rechecked')
    else:
        public_files = []
        seen = set()
        all_counts = Counter()
        for item in generated.get('files', []):
            name = item.get('modelName')
            matching = [k for k, r in reports.items() if r['model']['filename'] == name]
            require(len(matching) == 1, 'Actual-output verifier has an unknown/ambiguous model')
            model_id = matching[0]
            require(model_id not in seen, 'Duplicate actual-output verification model')
            seen.add(model_id)
            # A running report may have advanced after a preview recheck. Never call it complete.
            if item.get('sha256') != report_hashes[model_id]:
                issues.append(f'Fifth function: actual-output recheck is stale for {model_id}')
            if item.get('reportComplete') is not True or item.get('receivedResponses') != 120:
                issues.append(f'Fifth function: actual-output recheck incomplete for {model_id}')
            checked_rows = keyed(item.get('rows', []), case_key, 'actual-output verifier rows')
            if set(checked_rows) != {(d, t) for d in docs for t in TASKS}:
                issues.append(f'Fifth function: actual-output row coverage incomplete for {model_id}')
            source_rows = keyed(reports[model_id]['responses'], case_key, 'source response rows')
            file_counts = Counter()
            for key, checked_row in checked_rows.items():
                require(key in source_rows, 'Actual-output verifier contains a response absent from the raw run')
                file_counts['responseRows'] += 1
                if checked_row.get('parseStatus') == 'missing-or-malformed-findings':
                    file_counts['malformedRows'] += 1
                source_findings = parsed_findings(source_rows[key])
                checked_findings = checked_row.get('findings')
                require(isinstance(checked_findings, list) and len(checked_findings) == len(source_findings),
                        f'Actual-output verifier did not check every generated finding: {model_id}/{key}')
                for source_finding, finding in zip(source_findings, checked_findings):
                    require(finding.get('rawFinding') == source_finding,
                            f'Actual-output verifier checked a different finding: {model_id}/{key}')
                    check = finding.get('quoteCheck', {})
                    require(type(check.get('accepted')) is bool and type(check.get('acceptedAtRequestedPage')) is bool,
                            'Actual-output verifier quote results must be booleans')
                    require(not check['acceptedAtRequestedPage'] or check['accepted'],
                            'Actual-output verifier accepted a requested page without an exact match')
                    file_counts['findings'] += 1
                    if check['accepted']:
                        file_counts['exactQuoteAccepted'] += 1
                        file_counts['exactQuoteAcceptedAtRequestedPage' if check['acceptedAtRequestedPage'] else 'exactQuoteWrongPage'] += 1
                    else:
                        file_counts['quoteRejected'] += 1
                    if check.get('status') == 'too-short':
                        file_counts['quoteTooShort'] += 1
                    diagnostic = finding.get('pageDiagnostic', {})
                    if diagnostic.get('exactOnWholePageButRejectedByOriginalIndexedSources') is True:
                        file_counts['wholePageExactButIndexedSourceRejected'] += 1
                    if diagnostic.get('requestedPageHasExactQuote') is True and check.get('status') == 'too-short':
                        file_counts['wholePageExactButTooShort'] += 1
                    if diagnostic.get('sourceBoundaryRejection') is True:
                        file_counts['wholePageExactSourceBoundaryRejections'] += 1
                    statement = finding.get('statementTextCheck')
                    if isinstance(statement, dict):
                        file_counts['statementTextExact' if statement.get('status') == 'exact-text-match' else 'statementTextNotExact'] += 1
            for key, value in integer_counts(item.get('summary', {})).items():
                require(value == file_counts[key], f'Actual-output file counter differs from finding checks: {key}')
            all_counts.update(file_counts)
            public_files.append({'modelId': model_id, 'sourceReportSha256': item.get('sha256'),
                                 'reportComplete': item.get('reportComplete') is True,
                                 'receivedResponses': item.get('receivedResponses'),
                                 'checkedResponses': len(checked_rows), 'summary': {k: file_counts[k] for k in verification_count_names()}})
        if seen != set(reports) or generated.get('modelReportsComplete') is not True:
            issues.append('Fifth function: both completed model reports have not been rechecked')
        require('responseRows' in generated.get('summary', {}) and 'findings' in generated.get('summary', {}),
                'Actual-output verifier is missing its response/finding counts')
        for key, value in integer_counts(generated.get('summary', {})).items():
            require(value == all_counts[key], f'Actual-output verifier overall counter differs from finding checks: {key}')
        public_generated = {'status': 'completed' if len(issues) == generated_issues_start else 'partial',
                            'semanticDecision': 'not-provided', 'summary': {k: all_counts[k] for k in verification_count_names()},
                            'files': public_files}
    browser_fields = ('documentId', 'passed', 'taskChoices', 'exactMatchUI', 'beforeCitationPage', 'afterCitationPage',
                      'citationChangedPhysicalPage', 'highlightCount', 'unsupportedUI', 'unsupportedCitations', 'modelCalls', 'pdfSha256')
    return {'status': 'completed' if len(issues) == initial_issues else 'partial',
            'function': 'Verify Findings', 'modelCalls': 0, 'corpusSha256': corpus_hash,
            'sourceIntegrity': {'passed': actual['passed'], 'failed': actual['failed'],
                                'byKind': {k: {'passed': v['passed'], 'failed': v['failed']} for k, v in kinds.items()},
                                'documents': public_docs},
            'semanticVerification': {'implemented': False, 'score': None,
                                     'contextChallenges': len(semantic.get('observedContextChallenges', [])),
                                     'explicitNegationProbes': len(semantic.get('explicitNegationProbes', [])),
                                     'meaning': 'Exact textual presence/source integrity only; no factual, entailment, relevance, or completeness decision.'},
            'browser': {'status': browser.get('status'), 'modelCalls': 0,
                        'networkAttempts': len(browser.get('network', [])), 'errors': len(browser.get('errors', [])),
                        'checks': [{k: c[k] for k in browser_fields if k in c} for c in bc.values()]},
            'actualGeneratedFindings': public_generated}


def argument_value(arguments, name):
    try:
        return arguments[arguments.index(name) + 1]
    except (ValueError, IndexError):
        return None


def memory_metadata(monitor, reports, issues):
    grouped = defaultdict(list)
    for sample in (monitor or {}).get('samples', []):
        require(type(sample.get('hostPid')) is int and isinstance(sample.get('model'), str), 'Malformed memory sample identity')
        for key in ('rssBytes', 'peakRssBytes'):
            require(sample.get(key) is None or type(sample[key]) is int and sample[key] >= 0, 'Malformed memory byte count')
        grouped[sample['model'], sample['hostPid']].append(sample)
    rows = []
    for (model, pid), samples in grouped.items():
        samples.sort(key=lambda s: s['time'])
        rss = [s['rssBytes'] for s in samples if s.get('rssBytes') is not None]
        hwm = [s['peakRssBytes'] for s in samples if s.get('peakRssBytes') is not None]
        rows.append({'modelFilename': model, 'hostPid': pid, 'samples': len(samples),
                     'firstSample': samples[0]['time'], 'lastSample': samples[-1]['time'],
                     'peakSampledRssBytes': max(rss) if rss else None, 'peakHwmBytes': max(hwm) if hwm else None})
    rows.sort(key=lambda r: (r['firstSample'], r['hostPid']))
    latest = {}
    for model_id, report in reports.items():
        matching = [r for r in rows if r['modelFilename'] == report['model']['filename']]
        current = argument_value(report.get('serverArguments', []), '--cache-ram') == '0'
        after_start = [r for r in matching
                       if report.get('createdAt', '') <= r['firstSample']
                       <= (report.get('finishedAt') or '\uffff')]
        if current and after_start:
            chosen = max(after_start, key=lambda r: r['firstSample'])
            latest[model_id] = {**chosen, 'identification': 'Latest matching host PID first sampled within this main run phase start/finish interval; current serverArguments explicitly set --cache-ram 0. Later isolated timing PIDs are excluded.',
                                'priorCompletedResponses': max([p.get('priorGenerationCount', 0) for p in report.get('resumePhases', [])] or [0])}
        else:
            latest[model_id] = None
            issues.append(f'{model_id}: no externally sampled current --cache-ram 0 PID phase')
    return {'scope': 'External host /proc samples, grouped by model filename and host PID. Peaks are observed process/phase measurements, not intrinsic model requirements.',
            'byPid': rows, 'latestCacheRamZeroPhase': latest,
            'limitations': 'Different phases have different prompt histories/cache settings. Do not compare the old unbounded-cache PID with a fresh cache-ram-zero phase as a model-size effect.'}


def aggregate(workdir, allow_partial=False):
    corpus_path = workdir / 'corpus.json'
    corpus = read_json(corpus_path)
    corpus_hash = sha(corpus_path.read_bytes())
    docs = keyed(corpus.get('documents', []), lambda d: d.get('id'), 'corpus')
    require(len(docs) == 30 and Counter(d.get('category') for d in docs.values()) == Counter({c: 10 for c in CATEGORIES}),
            'Expected exactly 30 PDFs, ten in each category')
    for doc in docs.values():
        require(isinstance(doc.get('pages'), list) and doc['pages'] and all(type(p.get('page')) is int and
                isinstance(p.get('text'), str) for p in doc['pages']), 'Invalid authoritative PDF pages')
        require(len({p['page'] for p in doc['pages']}) == len(doc['pages']), 'Duplicate PDF page number')
    gold_path = workdir / 'gold-frozen.json'
    gold = read_json(gold_path)
    require(gold.get('corpusSha256') == corpus_hash, 'Gold is not frozen against this corpus')
    gold_docs = keyed(gold.get('documents', []), lambda d: d.get('id'), 'gold')
    require(set(gold_docs) == set(docs), 'Gold document set differs from corpus')
    for doc_id, gd in gold_docs.items():
        source_hash = gd.get('sourceSha256', gd.get('pdfSha256'))
        require(source_hash is None or source_hash == docs[doc_id].get('sha256'), f'{doc_id}: gold source fingerprint differs')
        for task in TASKS:
            require(type(gd.get('tasks', {}).get(task, {}).get('absenceExpected')) is bool, f'{doc_id}/{task}: missing gold absence flag')
    issues = []
    reports = {model_id: read_json(workdir / (model_id + '.json')) for model_id in CANDIDATES.values()}
    report_hashes = {m: sha((workdir / (m + '.json')).read_bytes()) for m in reports}
    plans = {}; rows = {}
    for model_id, report in reports.items():
        plans[model_id], rows[model_id] = validate_report(report, model_id, docs, corpus_hash, issues)
    left, right = CANDIDATES.values()
    require(reports[left].get('protocol') == reports[right].get('protocol'), 'Paired model protocols differ')
    for key, plan in plans[left].items():
        require(plan == plans[right][key], f'{key}: paired prompts/schema/input/coverage differ')
    expected_grades = {(d, candidate, t) for d in docs for candidate in CANDIDATES for t in TASKS}
    grades = {}
    input_hashes = {'corpus': corpus_hash, 'goldFrozen': sha(gold_path.read_bytes()),
                    'rawReports': report_hashes, 'gradeFiles': {},
                    'pairedPreparedRequestsSha256': sha(canonical([plans[left][k] for k in sorted(plans[left])]))}
    for category in CATEGORIES:
        path = workdir / f'grades-{category}.json'
        raw = read_json(path, optional=True)
        if raw is None:
            issues.append(f'{category}: grade file missing'); continue
        input_hashes['gradeFiles'][category] = sha(path.read_bytes())
        require(isinstance(raw.get('grades'), list), f'{category}: missing grade list')
        for grade in raw['grades']:
            key = grade.get('documentId'), grade.get('candidate'), grade.get('task')
            require(key in expected_grades, f'Unknown grade case: {key}')
            require(docs[key[0]]['category'] == category, f'Grade in wrong category file: {key}')
            require(key not in grades, f'Duplicate graded case: {key}')
            grades[key] = grade
    if set(grades) != expected_grades:
        issues.append(f'Only {len(grades)}/240 unique graded cases; missing {len(expected_grades - set(grades))}')
    sensitive = set()
    for doc in docs.values():
        sensitive.update(p['text'] for p in doc['pages'])
        sensitive.update(source.get('text', '') for source in doc.get('snapshot', {}).get('sources', []))
    for doc in gold_docs.values():
        for task in doc['tasks'].values():
            sensitive.update(a.get('evidence', '') for a in task.get('anchors', []) if isinstance(a, dict))
    for report in reports.values():
        for row in report['responses']:
            sensitive.update(v for f in parsed_findings(row) if isinstance(f, dict) for v in f.values() if isinstance(v, str))
            sensitive.update(row.get(k, '') for k in ('prompt', 'renderedPrompt', 'rawContent') if isinstance(row.get(k), str))
            sensitive.add(prompt_text(row['request']))
            if isinstance(row.get('api', {}).get('rawResponse'), str):
                sensitive.add(row['api']['rawResponse'])
    sensitive.update(' '.join(text.split()) for text in list(sensitive))
    sensitive = sorted(sensitive, key=len, reverse=True)
    cases = []; discrepancies = []
    for (doc_id, candidate, task), grade in sorted(grades.items()):
        model_id = CANDIDATES[candidate]
        row = rows[model_id].get((doc_id, task))
        if row is None:
            issues.append(f'{model_id}/{doc_id}/{task}: graded response missing'); continue
        metadata = raw_case_metadata(row, docs[doc_id])
        validate_grade(grade, metadata, f'{doc_id}/{candidate}/{task}')
        absence = gold_docs[doc_id]['tasks'][task]['absenceExpected']
        content = all(grade[k] for k in ('technicalComplete', 'factualCorrect', 'relevant', 'adequateCoverage'))
        correct_abstention = metadata['parsedFindings'] == 0 and absence and content
        eligible = metadata['validFindingRecords'] > 0 or correct_abstention
        if grade['quotes']['exactOnPage'] != metadata['literalExactQuoteRecords']:
            discrepancies.append({'documentId': doc_id, 'modelId': model_id, 'task': task,
                                  'graderExactOnPage': grade['quotes']['exactOnPage'],
                                  'recomputedLiteralExactOnPage': metadata['literalExactQuoteRecords']})
        cases.append({'documentId': doc_id, 'category': docs[doc_id]['category'], 'modelId': model_id, 'task': task,
                      'expectedAbsence': absence, 'correctAbstention': correct_abstention,
                      'contentPass': content and eligible, 'strictPass': content and grade['evidenceCorrect'] and eligible,
                      'raw': metadata, 'grade': {k: grade[k] for k in (*GRADE_FLAGS, 'numeric', 'quotes', 'unsupportedFindings')},
                      'reasons': redact_reasons(grade['reasons'], sensitive)})
    verification = verification_metadata(read_json(workdir / 'verify-findings.json', optional=True), docs, corpus_hash,
                                         reports, report_hashes, issues)
    memory = memory_metadata(read_json(workdir / 'memory-monitor.json', optional=True), reports, issues)
    for key, filename in (('verificationReport', 'verify-findings.json'), ('externalMemoryMonitor', 'memory-monitor.json')):
        path = workdir / filename
        input_hashes[key] = sha(path.read_bytes()) if path.exists() else None
    if issues and not allow_partial:
        raise InvalidEvaluation('Incomplete evaluation; no public result written:\n- ' + '\n- '.join(issues))
    model_results = {}
    for model_id, report in reports.items():
        subset = [c for c in cases if c['modelId'] == model_id]
        model_results[model_id] = {**sanitized_model(report), 'overall': summarize_cases(subset, 120),
            'byTask': {t: summarize_cases([c for c in subset if c['task'] == t], 30) for t in TASKS},
            'byCategory': {category: summarize_cases([c for c in subset if c['category'] == category], 40) for category in CATEGORIES}}
    public_docs = [{'id': d['id'], 'title': d['title'], 'category': d['category'], 'sourceUrl': d.get('sourceUrl'),
                    'pdfSha256': d.get('sha256'), 'bytes': d.get('bytes'), 'pages': len(d['pages']),
                    'extractedCharacters': sum(len(p['text']) for p in d['pages'])} for d in docs.values()]
    return {'schemaVersion': 1, 'status': 'partial' if issues else 'completed',
            'statusMeaning': 'Experiment collection and review completion only; not a model-quality or Android release approval.',
            'releaseApproval': {'approved': False, 'scope': 'This host evaluation grants no APK release approval.'},
            'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'scope': 'Four actual whole-PDF generation tasks plus independently executed production Verify Findings; host CPU/text-layer experiment, not an Android device benchmark.',
            'completion': {'expectedDocuments': 30, 'expectedResponsesPerModel': 120, 'expectedGradedCases': 240,
                           'uniqueGradedCases': len(grades), 'allWholePdfTextIncluded': True, 'unmetRequirements': issues},
            'provenance': input_hashes,
            'qualityDefinitions': {'contentPass': 'Technical completion, factual correctness, task relevance and adequate source coverage.',
                'strictPass': 'Content pass plus evidence correctness; independent of mere quotation presence.',
                'factualCorrect': 'All planned document cases are the denominator. Failed outputs and unsupported empty outputs receive no factual-success credit; appropriate gold-expected abstentions are reported explicitly.',
                'quoteRate': 'Exact contiguous quotation on the cited full PDF.js page, recomputed from raw output; not semantic truth. Grader counts remain auditable.',
                'numericRate': 'Generated figure records only. Zero records yields a null rate, never 100%. Failed responses contribute no numeric-correctness numerator.',
                'gold': 'Agent-authored source annotations and agent source review, not independent human-expert validation.'},
            'documents': public_docs, 'models': model_results, 'cases': cases,
            'literalQuoteDiscrepancies': discrepancies, 'verification': verification, 'memory': memory}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, default=Path('/workspace/scratch/d991318676df/apt-test-artifacts/five-task'))
    parser.add_argument('--outputdir', type=Path, default=Path('docs/apt/five-task'))
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    try:
        result = aggregate(args.workdir, args.allow_partial)
    except InvalidEvaluation as error:
        print(str(error), file=sys.stderr)
        return 2
    args.outputdir.mkdir(parents=True, exist_ok=True)
    target = args.outputdir / 'results.json'
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(target)
    print(json.dumps({'output': str(target), 'status': result['status'],
                      'uniqueGradedCases': result['completion']['uniqueGradedCases'],
                      'unmetRequirements': result['completion']['unmetRequirements']}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
