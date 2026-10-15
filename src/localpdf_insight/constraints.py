"""Vetoes for explicit contradictions, never a keyword-based acceptance score.

These deliberately bounded parsers do not establish open-domain entailment. A
separate semantic verifier is still required. Unknown vocabulary is not silently
mapped to a convenient synonym. Comparison normalization never edits source text.
"""
from dataclasses import dataclass
from decimal import Decimal
from datetime import date
import re
import unicodedata


def normalized(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    text = re.sub(r'[\u0610-\u061a\u064b-\u065f\u0670\u0640]', '', text)
    text = text.translate(str.maketrans('أإآٱى٠١٢٣٤٥٦٧٨٩٫٬', 'ااااي0123456789.,'))
    return re.sub(r'\s+', ' ', text).strip()


def matches(pattern, text):
    return bool(re.search(pattern, text, re.I))


def metric_labels(text):
    # Small, explicit contrast families. These labels only veto substitution;
    # they are not a synonym dictionary or authorization for releasing a claim.
    labels = set()
    families = {
        'profit': r'\b(?:profit|income|earnings)\b|(?:ربح|ارباح|دخل)',
        'margin': r'\bmargin\b|هامش',
        'revenue': r'\b(?:revenue|sales)\b|ايرادات|مبيعات',
        'cash_flow': r'\bcash\s+flow\b|تدفق(?:ات)?\s+نقد',
        'assets': r'\bassets\b|اصول',
        'liabilities': r'\bliabilities\b|خصوم',
    }
    qualifiers = {
        'net': r'\bnet\b|صافي', 'gross': r'\bgross\b|اجمالي|مجمل',
        'operating': r'\boperating\b|\bfrom operations\b|تشغيلي|من العمليات',
        'free': r'\bfree\b|حر(?:ة)?\b',
    }
    for family, pattern in families.items():
        for hit in re.finditer(pattern, text, re.I):
            # Bind the qualifier locally to the measure, not somewhere in a PDF.
            before = text[max(0, hit.start()-24):hit.start()]
            after = text[hit.end():hit.end()+24]
            before = re.split(r'[.;؛،]|\band\b', before)[-1]
            after = re.split(r'[.;؛،]|\band\b|\bof\b|\bfor\b|\bwas\b|\bis\b', after)[0]
            local = before + ' ' + after
            modifiers = [name for name, pat in qualifiers.items() if matches(pat, local)]
            if family == 'profit' and matches(families['margin'], local):
                continue
            if family in {'profit', 'margin', 'cash_flow'}:
                labels.add(family + ':' + (modifiers[0] if len(modifiers) == 1 else 'unspecified'))
            else:
                labels.add(family)
    return frozenset(labels)


CURRENCIES = {'AED': r'\baed\b|درهم', 'USD': r'\busd\b|\bdollars?\b|دولار',
              'EUR': r'\beur\b|\beuros?\b|يورو', 'GBP': r'\bgbp\b|استرليني'}
MEASURES = {'percent': r'%|٪|\bpercent(?:age)?\b|بالمئة|بالمئه',
            'days': r'\bdays?\b|ايام|يوما?\b', 'hours': r'\bhours?\b|ساعات|ساعة',
            'people': r'\b(?:employees?|people|persons?)\b|موظف|اشخاص'}
MONTHS = [('january', 'يناير'), ('february', 'فبراير'), ('march', 'مارس'),
          ('april', 'ابريل'), ('may', 'مايو'), ('june', 'يونيو'),
          ('july', 'يوليو'), ('august', 'اغسطس'), ('september', 'سبتمبر'),
          ('october', 'اكتوبر'), ('november', 'نوفمبر'), ('december', 'ديسمبر')]


def periods(text):
    result = set()
    for m in re.finditer(r'(?<!\d)[12]\d{3}(?!\d)', text):
        before, after = text[:m.start()], text[m.end():]
        if (matches(r'(?:\b(?:aed|usd|eur|gbp)|[$€£])\s*$', before)
                or matches(r'^\s*(?:%|٪|درهم|دولار|مليون|مليار|\b(?:aed|usd|eur|gbp|million|billion|days|hours)\b)', after)):
            continue
        result.add(m.group())
    return frozenset(result)


def quantities(text):
    # Explicit decimal quantities; spelled-out numbers require semantic review.
    text = re.sub(r'\b[12]\d{3}[-/]\d{1,2}[-/]\d{1,2}\b', '', text)
    month = '(?:' + '|'.join(name for names in MONTHS for name in names) + ')'
    text = re.sub(r'\b\d{1,2}\s+' + month + r'\s+[12]\d{3}\b|\b' + month + r'\s+\d{1,2},?\s+[12]\d{3}\b', '', text)
    # Parentheses around a currency-bound amount use accounting sign notation.
    # Do not treat arbitrary parenthetical years, counts or footnotes as losses.
    currency = r'(?:\b(?:aed|usd|eur|gbp)|[$€£]|درهم|دولار|يورو)'
    for match in reversed(list(re.finditer(r'\(\s*(\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:million|billion|thousand|مليون|مليار|الف))?)\s*\)', text))):
        if (matches(currency + r'\s*$', text[:match.start()]) or
                matches(r'^\s*' + currency, text[match.end():])):
            text = text[:match.start()] + '-' + match[1] + text[match.end():]
    result = set()
    years = periods(text)
    scale = {'million': 10**6, 'billion': 10**9, 'thousand': 1000,
             'مليون': 10**6, 'مليار': 10**9, 'الف': 1000}
    for m in re.finditer(r'(?<![\w])(-?\d+(?:,\d{3})*(?:\.\d+)?)(?:\s*(million|billion|thousand|مليون|مليار|الف))?', text):
        if m[1] in years and not m[2]:
            continue
        value = Decimal(m[1].replace(',', '')) * scale.get(m[2], 1)
        result.add(format(value.normalize(), 'f') if value else '0')
    return frozenset(result)


def date_labels(text):
    """Unambiguous year-first / named-month dates and explicit quarters only."""
    labels = set()
    def add(y, m, d=None):
        try:
            value = date(int(y), int(m), int(d or 1))
        except ValueError:
            return
        labels.add(value.strftime('%Y-%m'))
        if d is not None:
            labels.add(value.isoformat())
    for hit in re.finditer(r'\b([12]\d{3})[-/](\d{1,2})[-/](\d{1,2})\b', text):
        add(hit[1], hit[2], hit[3])
    for n, names in enumerate(MONTHS, 1):
        month = '(?:' + '|'.join(names) + ')'
        for hit in re.finditer(r'\b(\d{1,2})\s+' + month + r'\s+([12]\d{3})\b', text):
            add(hit[2], n, hit[1])
        for hit in re.finditer(r'\b' + month + r'\s+(?:(\d{1,2}),?\s+)?([12]\d{3})\b', text):
            add(hit[2], n, hit[1])
    quarters = [('first', 'الاول'), ('second', 'الثاني'), ('third', 'الثالث'), ('fourth', 'الرابع')]
    for n, (en, ar) in enumerate(quarters, 1):
        if matches(r'\bq' + str(n) + r'\b|\b' + en + r' quarter\b|الربع ' + ar, text):
            labels.add('Q' + str(n))
    return frozenset(labels)


def entities(raw):
    result = set()
    # Names bound to a subject/possessive, not all capitalized words in a passage.
    name = r'([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,3})'
    for pattern in [r'\bof\s+' + name,
                    r'\b(?:did|does|will|has)\s+' + name,
                    r'\b' + name + r"(?:'s|’s)\b",
                    r'\b' + name + r'\s+(?:earned|reported|expects|forecast|projects|must|may|shall|is required)\b']:
        result.update(normalized(m[1]) for m in re.finditer(pattern, raw))
    # Explicit "of NAME for PERIOD" binds the entity even in lowercase input.
    # A generic reference such as "the company" still requires semantic review.
    for m in re.finditer(r'\bof\s+([^\W\d_][\w &-]{0,70}?)\s+for\s+(?:(?:fiscal|calendar)\s+year\s+)?[12]\d{3}\b', raw, re.I):
        value = normalized(m[1])
        if value not in {'the company', 'company', 'the group', 'group', 'the business'}:
            result.add(value)
    text = normalized(raw)
    for pattern in [r'(?:ربح|دخل|ايرادات|مبيعات|كسبت|حققت)\s+(.+?)(?=\s+(?:لعام|في عام|عام|في|مبلغ|خلال)|[.؟،]|$)',
                    r'(?:لشركة|لشركه|شركة|شركه)\s+(.+?)(?=\s+(?:لعام|في|عام|مبلغ|خلال)|[.؟،]|$)']:
        for m in re.finditer(pattern, text):
            value = re.sub(r'^(?:التشغيلي|الصافي|الاجمالي)\s+', '', m[1]).strip()
            if value and len(value.split()) <= 3 and not matches(r'^(?:لشركة|لشركه|شركة|شركه)\b', value):
                result.add(value)
    role = re.search(r'\b(?:the\s+)?(supplier|buyer|customer|contractor)\s+(?:is\s+)?(?:not\s+)?(?:must|may|shall|required|permitted|prohibited)', text)
    role_ar = re.search(r'(?:يجب علي|يلتزم|يحظر علي)\s*(المورد|المشتري|العميل|المقاول)', text)
    names = {'المورد': 'supplier', 'المشتري': 'buyer', 'العميل': 'customer', 'المقاول': 'contractor'}
    if role:
        result.add('role:' + role[1])
    if role_ar:
        result.add('role:' + names[role_ar[1]])
    result.difference_update({'aed', 'usd', 'eur', 'gbp'})
    return frozenset(result)


def modality(text):
    if matches(r'\b(?:prohibited|forbidden|must not|shall not)\b|يحظر|ممنوع|لا يجوز', text):
        return 'prohibition'
    if matches(r'\b(?:must|shall|required|obliged|mandatory)\b|يجب|يلتزم|يتعين|ملزم', text):
        return 'obligation'
    if matches(r'\b(?:may|permitted|allowed|permission)\b|يجوز|مسموح', text):
        return 'permission'
    if matches(r'\b(?:should|ought to|recommended|recommendation)\b|ينبغي|يوصي|يوصى|مستحسن', text):
        return 'recommendation'
    return ''


def intent(text):
    if matches(r'\b(?:forecast\w*|projected|projection\w*|expects?|estimat\w*|target\w*)\b|توقع|متوقع|تقدير|مستهدف', text):
        return 'prospective'
    if matches(r'\b(?:actual|historical|was|were|earned|reported|did)\b|فعلي|بلغ|كسبت|حققت', text):
        return 'actual'
    return ''


@dataclass(frozen=True)
class Features:
    metrics: frozenset
    entities: frozenset
    years: frozenset
    dates: frozenset
    quantities: frozenset
    currencies: frozenset
    measures: frozenset
    intent: str
    modality: str
    negative: bool


def features(raw):
    text = normalized(raw)
    return Features(metric_labels(text), entities(raw), periods(text),
                    date_labels(text),
                    quantities(text), frozenset(k for k, p in CURRENCIES.items() if matches(p, text)),
                    frozenset(k for k, p in MEASURES.items() if matches(p, text)),
                    intent(text), modality(text),
                    # Arabic "غير" can modify a noun (unpaid invoices), rather
                    # than negate the requested predicate. Scope is semantic;
                    # do not equate that adjective with clausal negation.
                    matches(r'\b(?:not|never|no)\b|\b(?:ليس|ليست|لم|لا)\b', text))


def effective_features(question, context='', whole_question=''):
    q, shared, whole = features(question), features(context), features(whole_question)
    # Explicit new subjects/periods override shared ones. Ellipsis cannot shed
    # inherited metric/entity constraints merely by splitting the question.
    values = []
    for k in ('metrics', 'entities', 'years', 'dates', 'quantities', 'currencies', 'measures', 'intent', 'modality'):
        local = getattr(q, k)
        inherited = getattr(shared, k)
        # One explicitly shared subject/period may follow a coordinated list.
        # Never infer that two different entities or periods are interchangeable.
        common = getattr(whole, k) if k in {'entities', 'years', 'metrics'} else frozenset()
        if not inherited and len(common) == 1:
            inherited = common
        values.append(local or inherited)
    return Features(*values, q.negative)


def explicit_scope(raw):
    """Explicit reporting/calendar/forecast kinds; never infer a missing kind."""
    text = normalized(raw)
    selectors = {
        'reporting_scope': {'consolidated': r'\bconsolidated\b|\bgroup-wide\b|موحد',
                            'standalone': r'\b(?:standalone|stand-alone|unconsolidated)\b|منفرد'},
        'year_basis': {'calendar': r'\bcalendar year\b|(?:ال|لل)سن[ةه] الميلادي[ةه]',
                       'fiscal': r'\bfiscal year\b|(?:ال|لل)سن[ةه] المالي[ةه]'},
        'extremum': {'minimum': r'\bminimum\b|ادني',
                     'maximum': r'\bmaximum\b|اقصي'},
        'prospective_kind': {'forecast': r'\b(?:forecast\w*|projection\w*|projected|expects?)\b|توقع',
                             'target': r'\b(?:targets?|goals?|aims?)\b|مستهدف|المستهدف'},
    }
    return {name: frozenset(k for k, p in choices.items() if matches(p, text))
            for name, choices in selectors.items()}


def vetoes(question, witness, context='', whole_question=''):
    q = effective_features(question, context, whole_question)
    e = features(witness)
    reasons = []
    for name, labels in explicit_scope(question).items():
        labels = labels or explicit_scope(context)[name]
        observed = explicit_scope(witness)[name]
        if labels and observed and labels != observed:
            reasons.append(name + '_mismatch')
    # Every check operates on ONE bound evidence unit. Never union an entity in
    # one sentence with a year, metric or amount from a different sentence.
    compatible = all(label in e.metrics or label.endswith(':unspecified') and
                     any(x.split(':')[0] == label.split(':')[0] for x in e.metrics) for label in q.metrics)
    if q.metrics and e.metrics and not compatible:
        reasons.append('metric_mismatch')
    if q.metrics and len(e.metrics) > len(q.metrics):
        reasons.append('ambiguous_metric_binding')
    if q.entities and e.entities and not q.entities <= e.entities:
        # Transliteration requires semantic verification; do not equate names by
        # spelling similarity or reject multilingual evidence solely by script.
        q_ar = any(matches('[\u0600-\u06ff]', x) for x in q.entities)
        e_ar = any(matches('[\u0600-\u06ff]', x) for x in e.entities)
        if q_ar == e_ar:
            reasons.append('entity_mismatch')
    if q.entities and len(e.entities) > len(q.entities):
        reasons.append('ambiguous_entity_binding')
    if q.years and not q.years <= e.years:
        reasons.append('period_mismatch')
    if q.years and e.years - q.years and not matches(r'compar|change|growth|between|مقارن|تغير|نمو|بين', normalized(question)):
        reasons.append('ambiguous_period_binding')
    if q.dates and not q.dates <= e.dates:
        reasons.append('date_mismatch')
    for name in ('currencies', 'measures'):
        if getattr(q, name) and getattr(e, name) and not getattr(q, name) <= getattr(e, name):
            reasons.append(name + '_mismatch')
    if q.intent and e.intent and q.intent != e.intent:
        reasons.append('actual_forecast_mismatch')
    if q.modality and e.modality and q.modality != e.modality:
        reasons.append('modality_mismatch')
    # A yes/no question can be answered by evidence disproving its premise. A
    # presuppositional why/how question cannot substitute the opposite assertion.
    neutral = matches(r'^\s*(?:is|are|was|were|did|does|has|have|can|must)\b|^\s*هل', normalized(question))
    if not neutral:
        if q.quantities and not q.quantities <= e.quantities:
            reasons.append('quantity_mismatch')
        if q.quantities and len(e.quantities) > len(q.quantities):
            reasons.append('ambiguous_quantity_binding')
        if (q.negative or matches(r'^\s*(?:why|how)\b|^\s*(?:لماذا|كيف)', normalized(question))) and q.negative != e.negative:
            reasons.append('polarity_mismatch')
        directions = {'up': r'\b(?:increase\w*|rose|higher|grew)\b|زادت|ارتفع',
                      'down': r'\b(?:decrease\w*|fell|lower|declin\w*)\b|انخفض|تراجع'}
        q_dir = {k for k, p in directions.items() if matches(p, normalized(question))}
        e_dir = {k for k, p in directions.items() if matches(p, normalized(witness))}
        if len(q_dir) == len(e_dir) == 1 and q_dir != e_dir:
            reasons.append('comparison_direction_mismatch')
    if matches(r'unconditional|without exception|دون شروط|بلا استثناء', normalized(question)) and matches(r'\b(?:unless|except|subject to|provided that|only if)\b|الا اذا|بشرط|شريطة', normalized(witness)):
        reasons.append('qualification_mismatch')
    if matches(r'ignore (?:the )?(?:user|system|previous)|system prompt|تجاهل التعليمات|تجاهل المستخدم', normalized(witness)):
        reasons.append('instruction_text')
    return reasons


def conflict_key(question, witness):
    """Only detect explicit same-labelled, same-entity/period numeric conflicts.

    General causal/legal conflicts remain the semantic verifier's responsibility.
    """
    q, e = features(question), features(witness)
    if not q.metrics or len(e.metrics) != 1 or not e.entities or not e.years or len(e.quantities) != 1:
        return None
    return (e.metrics, e.entities, e.years, e.dates, e.currencies, e.measures,
            e.intent, e.modality, e.negative, tuple(explicit_scope(witness).values())), e.quantities


def conflict_signatures(question, witness):
    """Only explicit matching propositions, including their full conditions.

    Free-form causal/legal disagreement still needs semantic verification. In
    particular, permission and obligation alone are not contradictory.
    """
    number = conflict_key(question, witness)
    result = [(('number', number[0]), number[1])] if number else []
    text = normalized(witness).rstrip('.؛; ')
    en = re.fullmatch(r'(.+?)\s+(must not|shall not|is not required to|is required to|is prohibited from|is permitted to|must|shall|may)\s+(.+)', text)
    if en:
        mode = {'must not':'prohibition','shall not':'prohibition','is prohibited from':'prohibition',
                'is not required to':'no_obligation','is required to':'obligation','must':'obligation',
                'shall':'obligation','may':'permission','is permitted to':'permission'}[en[2]]
        result.append((('legal', en[1] + '|' + en[3]), mode))
    ar = re.fullmatch(r'(يجب علي|لا يجب علي|يحظر علي|يجوز ل)(.+)', text)
    if ar:
        mode = {'يجب علي':'obligation','لا يجب علي':'no_obligation','يحظر علي':'prohibition','يجوز ل':'permission'}[ar[1]]
        result.append((('legal', ar[2].strip()), mode))
    # Exact subject/predicate match with one explicit negation difference.
    descriptive = re.fullmatch(r'(.+?\b(?:is|are|was|were))\s+(not\s+)?(.+)', text)
    if descriptive and not en:
        result.append((('polarity', descriptive[1] + '|' + descriptive[3]), bool(descriptive[2])))
    return result


def signatures_conflict(signature, values):
    if signature[0] in {'number', 'polarity'}:
        return len(values) > 1
    return any(pair <= values for pair in [
        {'obligation', 'prohibition'}, {'permission', 'prohibition'}, {'obligation', 'no_obligation'}])
