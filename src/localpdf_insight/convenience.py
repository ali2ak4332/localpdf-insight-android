"""Small source-derived prompts and presentation helpers; evidence remains authoritative."""
import re
from .evidence import normalize, query_tokens

# Every format uses answer() and its existing claim validation, not another AI path.
TEMPLATES = {
    'Executive summary': ('الملخص التنفيذي', 'Summarize the main findings and conclusions.'),
    'Key facts': ('الحقائق الرئيسية', 'List the most important explicit facts.'),
    'Key numbers': ('الأرقام الرئيسية', 'Extract key numbers with their units, period and stated meaning. Do not calculate missing values.'),
    'Risks': ('المخاطر', 'Extract explicitly stated risks and their stated consequences. Do not infer new risks.'),
    'Obligations': ('الالتزامات', 'Identify explicit obligations, responsible parties and any stated deadlines. Do not infer duties.'),
    'Timeline': ('التسلسل الزمني', 'List explicit dates and associated events in chronological order. Do not invent dates.'),
    'FAQ': ('أسئلة شائعة', 'Select self-contained passages that answer useful questions about the source topics.'),
    'Glossary': ('المصطلحات', 'Extract only terms with definitions explicitly supplied by the sources. Do not add dictionary knowledge.'),
    'Study Guide': ('دليل الدراسة', 'Select the central concepts, definitions and conclusions worth studying.'),
    'Flashcards': ('بطاقات المراجعة', 'Select self-contained factual passages with a clear concept or number for a short recall exercise.'),
    'Quiz': ('اختبار قصير', 'Select self-contained factual passages with an unambiguous concept or number for a short recall exercise.'),
}
STUDY = {'Flashcards', 'Quiz'}


def usable_prompt_text(text):
    # Do not turn known broken/visual-order extraction into a misleading study prompt.
    # The reader still exposes the original page and extraction warnings.
    return not re.search(r'[\ufffd\ufb50-\ufdff\ufe70-\ufeff]',text)


def source_language(sources):
    text=' '.join(s['text'] for s in sources)
    arabic=len(re.findall(r'[\u0621-\u064a\ufb50-\ufdff\ufe70-\ufeff]', text))
    latin=len(re.findall('[a-zA-Z]', text))
    return 'ar' if arabic>latin else 'en'


def sampled_sources(chunks, ids, limit=16):
    """Reuse the reader's spaced, round-robin sampling with a bounded context."""
    groups={i:[c for c in chunks if c['document_id']==i] for i in ids}
    samples={i:group[::max(1,len(group)//8)][:8] for i,group in groups.items()}
    result=[];used=0
    for n in range(8):
        for i in ids:
            if n>=len(samples[i]):continue
            c=samples[i][n]
            if used+len(c['text'])>14000:continue
            result.append(c);used+=len(c['text'])
            if len(result)>=limit:return result
    return result


def anchor(source):
    heading=source.get('heading','').strip()
    text=heading if query_tokens(heading) and any(c.isalpha() for c in heading) else source['text']
    # Do not split numbered headings at their clause number.
    text=text.strip().lstrip('.!?؟;؛ ')
    first=text if text==heading else re.split(r'[\n!?؟;؛]|(?<!\d)\.(?!\d)',text)[0]
    words=first.split()
    if not words or (len(words)<2 and len(first)<4) or not any(c.isalpha() for c in first):return ''
    return ' '.join(words[:8])[:100].strip()


def suggested_questions(chunks, ids):
    questions=[];seen=set()
    samples=sampled_sources([c for c in chunks if usable_prompt_text(c['text'])],ids,limit=48)
    # Use distinct sections first; a short document may contain several topics in
    # one chunk. Sentence candidates retain that same authoritative chunk ID.
    candidates=samples+[s | {'heading':'','text':sentence} for s in samples
        for sentence in re.split(r'\n|(?<=[.!?؟])\s+',s['text']) if len(sentence.strip())>30]
    for source in candidates:
        topic=anchor(source)
        key=normalize(topic)
        if not topic or key in seen:continue
        seen.add(key)
        ar=source_language([source])=='ar'
        question=f'ماذا يوضح المستند بشأن «{topic}»؟' if ar else f'What does the document explain about “{topic}”?'
        questions.append({'question':question,'source_ids':[source['id']]})
        if len(questions)==6:break
    return questions


def study_cards(claims, sources, language):
    """Exact-source cloze exercises: no fabricated distractors or answer keys."""
    known={s['id']:s for s in sources};cards=[];seen=set()
    for claim in claims:
        # Even in assisted mode a study answer must pass exact-span validation.
        text=claim['text']
        if not usable_prompt_text(text):continue
        if not all(text in known[i]['text'] for i in claim['source_ids']):continue
        for sentence in re.split(r'(?<=[.!?؟])\s+|\n',text):
            if not 25<=len(sentence)<=450 or sentence in seen:continue
            candidates=re.findall(r'\d+(?:[.,٫٬]\d+)*|[^\W\d_]{4,}',sentence)
            important=set(query_tokens(sentence))
            candidates=[w for w in candidates if normalize(w) in important]
            if not candidates:continue
            term=next((w for w in candidates if w[0].isdigit()),max(candidates,key=len))
            front=sentence.replace(term,'____',1)
            cards.append({'front':('أكمل النص: ' if language=='ar' else 'Complete the passage: ')+front,
                          'back':term,'explanation':sentence,'source_ids':claim['source_ids']})
            seen.add(sentence)
            break
        if len(cards)==5:break
    return cards
