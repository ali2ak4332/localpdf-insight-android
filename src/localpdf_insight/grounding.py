"""Question adjudication and source-only release. This is not a semantic proof system.

A local semantic review is required for generated Q&A, in addition to deterministic
source/coverage/period checks. Its reliability still requires the live release gate.
Model-authored factual prose is never released: approved units are copied server-side
with their complete local qualifications. No keyword-overlap score admits a claim.
"""
import json
import re

def json_object(raw):
    if not isinstance(raw, str):
        raise ValueError('Expected JSON text')
    fence = re.fullmatch(r'\s*```(?:json)?\s*\n(.*?)\n```\s*', raw, re.S | re.I)
    if fence:
        raw = fence.group(1)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError('Expected JSON object')
    return value


def review_question(question, sources, verifier, model=None, operation='ask'):
    """Validate a separate verifier's proposal; deterministic vetoes always win.

    `model` is retained for callers of this parsing interface, not used to invoke
    generation. Positive Boolean `checks` from the old protocol grant no access.
    """
    from .verification import Source, VerificationRequest, question_spans, units
    from .constraints import vetoes, conflict_signatures, signatures_conflict, features
    request = VerificationRequest(question, tuple(Source(c['id'], c['text']) for c in sources), operation)
    result = json_object(verifier(request))
    parts = result.get('parts')
    expected = question_spans(question)
    if not isinstance(parts, list) or not 1 <= len(parts) <= 8 or len(parts) != len(expected):
        raise ValueError('Question coverage review missing or invalid')
    known = {c['id']: c for c in sources}
    verified = []
    for part, (start, end) in zip(parts, expected):
        if (not isinstance(part, dict) or type(part.get('start')) is not int
                or type(part.get('end')) is not int or (part['start'], part['end']) != (start, end)):
            raise ValueError('Question review omitted, overlapped or rewrote a requested part')
        status, ids = part.get('status'), part.get('source_ids')
        if status not in {'supported', 'absent', 'conflict', 'unknown'} or not isinstance(ids, list):
            raise ValueError('Invalid review status or evidence IDs')
        if not all(isinstance(i, str) and i in known for i in ids) or len(ids) != len(set(ids)):
            raise ValueError('Review cites unavailable or repeated evidence')
        references = part.get('witnesses', [])
        if not isinstance(references, list) or len(references) > 48:
            raise ValueError('Invalid evidence witnesses')
        if status in {'absent', 'unknown'} and (ids or references):
            raise ValueError('Unsupported part cannot cite an answer')
        accepted, rejected = [], []
        fragment = question[start:end]
        context = question[:start]
        if status in {'supported', 'conflict'}:
            if not ids or (status == 'conflict' and len(references) < 2):
                raise ValueError('Supported/conflicting answer lacks source evidence')
            for ref in references:
                if not isinstance(ref, dict) or ref.get('source_id') not in ids or type(ref.get('unit')) is not int:
                    raise ValueError('Invalid evidence witness identifier')
                sid, number = ref['source_id'], ref['unit']
                spans = units(known[sid]['text'])
                if not 0 <= number < len(spans):
                    raise ValueError('Evidence witness is out of bounds')
                a, b = spans[number]
                text = known[sid]['text'][a:b]
                failures = vetoes(fragment, text, context, question)
                if number == len(spans)-1 and known[sid].get('qualification_continuation'):
                    failures.append('qualification_crosses_source_boundary')
                if 'instruction_text' in vetoes('', known[sid]['text']):
                    failures.append('source_instruction_text')
                f = features(text)
                if operation in {'Obligations', 'Action items'} and f.modality not in {'obligation', 'prohibition'}:
                    failures.append('report_category_mismatch')
                if operation == 'Key numbers' and not (f.quantities or f.years):
                    failures.append('report_category_mismatch')
                record = {'source_id': sid, 'unit': number, 'start': a, 'end': b}
                if failures:
                    rejected.append({**record, 'reasons': failures})
                elif record not in accepted:
                    accepted.append(record)
            if not accepted:
                status, ids = 'unknown', []
                if not references:
                    rejected.append({'reasons': ['missing_bound_evidence']})
            else:
                ids = list(dict.fromkeys(r['source_id'] for r in accepted))
                # Discover explicit numeric or proposition-level oppositions,
                # including two sides in the same source. Different conditions,
                # actors and reporting scopes do not collapse into one fact.
                values, sides = {}, {}
                for r in accepted:
                    text = known[r['source_id']]['text'][r['start']:r['end']]
                    for signature, value in conflict_signatures(fragment, text):
                        values.setdefault(signature, set()).add(value)
                        sides.setdefault(signature, []).append(r)
                for sid, source in known.items():
                    for n, (a, b) in enumerate(units(source['text'])):
                        if source.get('qualification_continuation') and n == len(units(source['text']))-1:
                            continue
                        text = source['text'][a:b]
                        remaining = set(vetoes(fragment, text, context, question)) - {
                            'quantity_mismatch', 'polarity_mismatch', 'modality_mismatch'}
                        if remaining or 'instruction_text' in vetoes('', source['text']):
                            continue
                        for signature, value in conflict_signatures(fragment, text):
                            if signature in values:
                                values[signature].add(value)
                                r = {'source_id': sid, 'unit': n, 'start': a, 'end': b}
                                if r not in sides[signature]: sides[signature].append(r)
                for signature, options in values.items():
                    if signatures_conflict(signature, options):
                        status = 'conflict'
                        for r in sides[signature]:
                            if r not in accepted: accepted.append(r)
                # A partly vetoed claimed conflict is never a one-sided answer.
                if status == 'conflict' and len(accepted) < 2:
                    status, ids, accepted = 'unknown', [], []
                else:
                    ids = list(dict.fromkeys(r['source_id'] for r in accepted))
        verified.append({'question': fragment, 'start': start, 'end': end,
                         'status': status, 'source_ids': ids, 'witnesses': accepted,
                         'vetoes': rejected})
    return verified


def release_units(ids, sources):
    """No generated words, source IDs, filenames, pages or coordinates are trusted."""
    known = {c['id']: c for c in sources}
    return [{'text': known[i]['text'], 'source_ids': [i], 'verbatim': True}
            for i in dict.fromkeys(ids) if i in known]


def release_witnesses(parts, sources):
    """Copy only approved server-defined spans, retaining source/page identity.

    Adjacent approved spans may be grouped. A source ID never authorizes other
    sentences in that source. All offsets and text originate on the server.
    """
    from .verification import units
    known = {s['id']: s for s in sources}
    selected = {}
    for part in parts:
        if part['status'] not in {'supported', 'conflict'}: continue
        for r in part['witnesses']:
            source = known[r['source_id']]
            allowed = units(source['text'])
            if not 0 <= r['unit'] < len(allowed) or allowed[r['unit']] != (r['start'], r['end']):
                raise ValueError('Release witness no longer matches server evidence')
            selected.setdefault(r['source_id'], set()).add((r['start'], r['end']))
    claims = []
    for sid, spans in selected.items():
        grouped = []
        for a, b in sorted(spans):
            if grouped and grouped[-1][1] == a: grouped[-1] = (grouped[-1][0], b)
            else: grouped.append((a, b))
        for a, b in grouped:
            claims.append({'text': known[sid]['text'][a:b], 'source_ids': [sid], 'verbatim': True,
                           'source_span': {'start': a, 'end': b}})
    return claims


def safe_saved_output(output):
    """Retain historical SQLite bytes, but do not re-release unvalidated AI prose."""
    content = output.get('content', {})
    from .verification import RELEASE_POLICY
    if content.get('claims') and content.get('mode') in {'strict', 'assisted'} and (not isinstance(content.get('grounding'), dict) or content['grounding'].get('version') != 2 or content['grounding'].get('release_policy') != RELEASE_POLICY):
        return {**output, 'content': {**content, 'claims': [], 'cards': [],
                'message': 'This saved AI answer predates the grounding checks. Regenerate it from its sources.',
                'grounding': {'version': 1, 'status': 'legacy_answer_withheld'}}}
    return output


def safe_answer(question, sources, candidates, strict, verifier, model, operation, refusal):
    """No model-written claims or approvals cross the source-only release boundary."""
    from .verification import Source, VerificationRequest, OllamaVerifier, VERSION, RELEASE_POLICY
    mode = 'strict' if strict else 'assisted'
    request = VerificationRequest(question, tuple(Source(c['id'], c['text']) for c in sources), operation)
    audit = {'version': VERSION, 'rendering': 'server_source_units', 'status': 'insufficient',
             'release_policy': RELEASE_POLICY,
             'classification': 'UNVERIFIED', 'request_sha256': request.fingerprint(),
             'scope_of_absence': 'retrieved_passages_only',
             'verifier': {'implementation': type(verifier).__name__,
                          'model': verifier.model if isinstance(verifier, OllamaVerifier) else None,
                          'same_model_weights': True if isinstance(verifier, OllamaVerifier) and verifier.model == model else None,
                          'identity_basis': 'configured_model_tag_not_runtime_digest',
                          'semantic_independence_claimed': False},
             'semantic_guarantee': 'probabilistic_review_with_deterministic_vetoes'}
    base = {'claims': [], 'mode': mode, 'message': refusal, 'grounding': audit}
    if not candidates:
        audit['failure'] = 'no_valid_candidate'
        return base
    try:
        parts = review_question(question, sources, verifier, operation=operation)
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
        audit.update(status='review_failed', failure=type(exc).__name__)
        base['message'] = ('تعذر التحقق من كفاية الأدلة؛ لم تُعرض إجابة.' if re.search('[\u0600-\u06ff]', question)
                           else 'Evidence verification could not establish sufficient support; no answer was released.')
        return base
    missing = [p['question'] for p in parts if p['status'] in {'absent', 'unknown'}]
    conflicts = [p for p in parts if p['status'] == 'conflict']
    claims = release_witnesses(parts, sources)
    ar = bool(re.search('[\u0600-\u06ff]', question))
    if claims:
        message = 'مقتطفات المصدر المرتبطة بالأجزاء المدعومة من السؤال.' if ar else 'Source extracts for the supported parts of the question.'
        if missing:
            message += (' لم تثبت المقتطفات المسترجعة إجابة الأجزاء التالية: ' if ar else 'Retrieved passages did not establish an answer for: ') + ' | '.join(missing)
        if conflicts:
            message += ' توجد أدلة متعارضة؛ تُعرض المصادر دون ترجيح.' if ar else 'Conflicting evidence is shown without choosing one account as true.'
        if operation != 'ask':
            message += ' تغطية مقتطفات محدودة.' if ar else ' Source extracts have sampled coverage.'
        base.update(claims=claims, message=message)
    else:
        base['message'] = ('لم تثبت المقتطفات المسترجعة أدلة كافية للإجابة؛ هذا لا يثبت غياب المعلومة من كامل المستندات.' if ar
                           else 'I could not establish sufficient evidence in the retrieved passages. This does not prove absence from the complete documents.')
    classification = ('CONFLICTING' if conflicts else 'PARTIAL' if claims and missing else 'SUPPORTED' if claims
                      else 'ABSENT' if all(p['status'] == 'absent' for p in parts) else 'UNVERIFIED')
    audit.update(status='conflict' if conflicts else 'partial' if claims and missing else 'supported' if claims else 'insufficient',
                 classification=classification, parts=parts, unsupported_questions=missing, conflicts=conflicts)
    return base
