"""Separate, explicitly controlled verification fixtures; never live evidence.

Labels come from the document/question fixture, not from answer-generation output.
The unconditional approver is used to challenge server vetoes, not to certify NLP.
"""
import json
from localpdf_insight.verification import units, question_spans


def approving_verifier(request):
    return json.dumps({'parts': [
        {'start': a, 'end': b, 'status': 'supported',
         'source_ids': [s.id for s in request.sources],
         'witnesses': [{'source_id': s.id, 'unit': n}
                       for s in request.sources for n, _ in enumerate(units(s.text))]}
        for a, b in question_spans(request.question)]})


def case_verifier(case):
    calls = []
    def verify(request):
        assert request.question == case['question']
        def source_for(n):
            target = ' '.join(case['documents'][n].split())
            return next(s for s in request.sources if ' '.join(s.text.split()) == target)
        boundaries = [0, case['split'], len(case['question'])] if case['split'] else [0, len(case['question'])]
        parts = []
        for n, status in enumerate(case['statuses']):
            selected = [source_for(i) for i in case['sides'][n]]
            parts.append({'start': boundaries[n], 'end': boundaries[n+1], 'status': status,
                          'source_ids': [s.id for s in selected],
                          'witnesses': [{'source_id': s.id, 'unit': k}
                                        for s in selected for k, _ in enumerate(units(s.text))]})
        raw = json.dumps({'parts': parts})
        calls.append({'request': request.payload(), 'raw_response': raw, 'controlled': True})
        return raw
    return verify, calls
