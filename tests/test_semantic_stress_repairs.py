"""Repairs derived from the second frozen corpus; no longer holdout claims."""
import pytest
from localpdf_insight.constraints import vetoes
from localpdf_insight.grounding import safe_answer
from verification_support import approving_verifier


@pytest.mark.parametrize('question,evidence', [
    ('What is the maximum warranty duration?', 'The minimum warranty duration is fifty months.'),
    ('ما أقصى مدة للضمان؟', 'الحد الأدنى لمدة الضمان خمسون شهرا.'),
    ('What is the minimum storage capacity?', 'The maximum storage capacity is 700 GB.'),
    ('ما أدنى ارتفاع مسموح؟', 'أقصى ارتفاع مسموح 12 مترا.'),
])
def test_explicit_opposite_extrema_override_verifier(question, evidence):
    result = safe_answer(question, [{'id':'s','text':evidence}], [{'text':evidence,'source_ids':['s']}],
                         True, approving_verifier, 'controlled', 'ask', 'No evidence')
    assert not result['claims']
    assert 'extremum_mismatch' in result['grounding']['parts'][0]['vetoes'][0]['reasons']


def test_arabic_attributive_negative_does_not_prove_clausal_contradiction():
    q = 'ما نسبة الفواتير غير المدفوعة التي حصلتها سولايس في عام 2041؟'
    e = 'استردت سولايس 91 بالمئة من الفواتير المستحقة في عام 2041.'
    assert 'polarity_mismatch' not in vetoes(q, e)
    assert 'polarity_mismatch' in vetoes('لم تحقق الشركة ربحا.', 'حققت الشركة ربحا.')
