"""PyMuPDF adapter. All calls run in spawned processes in the web application."""
from __future__ import annotations
import base64
import re
from pathlib import Path
import fitz
from .evidence import EvidenceIndex, digest


def inspect_pdf(path, password=''):
    with fitz.open(path) as doc:
        if not doc.is_pdf or not len(doc):raise ValueError('Choose a non-empty PDF file.')
        if doc.needs_pass and not doc.authenticate(password):raise ValueError('This PDF needs its correct password.')
        return {'page_count':len(doc),'outline':[{'level':l,'title':t,'page':p} for l,t,p in doc.get_toc() if p>0]}


def normalized_box(page, bbox):
    r=fitz.Rect(bbox)*page.rotation_matrix
    return [max(0,min(1,r.x0/page.rect.width)),max(0,min(1,r.y0/page.rect.height)),
            max(0,min(1,r.x1/page.rect.width)),max(0,min(1,r.y1/page.rect.height))]


def native_text_quality(text):
    chars=[c for c in text if not c.isspace()]
    return bool(chars) and text.count('\ufffd')/len(chars)<.03 and sum(c.isalnum() for c in chars)/len(chars)>.35


def extract_page(page, languages='eng', ocr=True):
    textpage=None; warnings=[]; method='native'
    text=page.get_text('text',sort=True)
    images=page.get_image_info()
    # OCR image regions on mixed pages, or whole page when native text is unusable.
    image_area=sum(abs(fitz.Rect(i['bbox']).get_area()) for i in images)
    has_scan=image_area>page.rect.get_area()*.35
    if ocr and (not native_text_quality(text) or has_scan):
        try:
            textpage=page.get_textpage_ocr(language=languages,dpi=200,full=not native_text_quality(text))
            text=page.get_text('text',textpage=textpage,sort=True)
            method='ocr' if not native_text_quality(page.get_text()) else 'native+ocr'
        except Exception as exc:
            warnings.append('OCR unavailable or failed ('+languages+'): '+str(exc)[:180])
    if re.search(r'[\ufb50-\ufdff\ufe70-\ufeff]', text):
        warnings.append('Arabic visual-order/presentation-form text detected. Search uses alternate Arabic token order; the original extraction is preserved. Verify quotations and numbers against the page.')
    if not native_text_quality(text):warnings.append('No reliable text layer. Use OCR with the document language installed, or inspect this page visually.')
    data=page.get_text('dict',textpage=textpage,sort=True,flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)
    sizes=[s['size'] for b in data['blocks'] if b['type']==0 for l in b['lines'] for s in l['spans'] if s['text'].strip()]
    median=sorted(sizes)[len(sizes)//2] if sizes else 10
    units=[]; heading=''
    for block in data['blocks']:
        if block['type']!=0:continue
        lines=[]
        for line in block['lines']:
            line_text=''.join(s['text'] for s in line['spans']).strip()
            if not line_text:continue
            size=max(s['size'] for s in line['spans'])
            is_heading=len(line_text)<150 and (size>median*1.18 or bool(re.match(r'^\s*(?:\d+(?:\.\d+)*[.)]?\s+|المادة\s|الفصل\s|Appendix\s|Section\s)',line_text)))
            lines.append((line_text,line['bbox'],is_heading))
        # Group within layout blocks, splitting only at line/heading boundaries.
        buffer=[]; box=None; kind='paragraph'; local_heading=heading
        def flush():
            nonlocal buffer,box
            if buffer:
                units.append({'text':'\n'.join(buffer),'bbox':normalized_box(page,box),'kind':kind,
                              'heading':local_heading,'ordinal':len(units)})
            buffer=[];box=None
        for line,bbox,is_heading in lines:
            if is_heading or sum(map(len,buffer))+len(line)>1800:flush()
            if is_heading:heading=line;local_heading=line;kind='heading'
            elif buffer and kind=='heading':flush();kind='paragraph'
            else:kind='paragraph'
            buffer.append(line); box=fitz.Rect(bbox) if box is None else box|fitz.Rect(bbox)
        flush()
    tables=[]
    try:
        for table in page.find_tables().tables:
            rows=table.extract()
            if len(rows)<2 or len(rows[0])<2:continue
            rows=[['' if cell is None else str(cell) for cell in row] for row in rows]
            markdown='\n'.join('| '+' | '.join(c.replace('|','\\|').replace('\n',' ') for c in row)+' |' for row in rows)
            tables.append({'rows':rows,'bbox':normalized_box(page,table.bbox),'confidence':'heuristic — verify against page'})
            units.append({'text':markdown,'bbox':normalized_box(page,table.bbox),'kind':'table','heading':heading,'ordinal':len(units)})
    except Exception as exc:warnings.append('Table extraction failed: '+str(exc)[:100])
    # Prefer structured cells over duplicate flattened text inside detected tables.
    table_boxes=[fitz.Rect(t['bbox']) for t in tables]
    units=[u for u in units if u['kind']=='table' or not any(
        (fitz.Rect(u['bbox']) & box).get_area() > fitz.Rect(u['bbox']).get_area()*.6 for box in table_boxes)]
    return {'page':page.number+1,'text':text,'units':units,'tables':tables,'method':method,
            'width':page.rect.width,'height':page.rect.height,'rotation':page.rotation,
            'visual_recommended':bool(images or tables or warnings),'warnings':warnings}


def index_document(path, doc_id, revision, db_path, languages='eng', embed_model=''):
    index=EvidenceIndex(Path(db_path))
    try:
        if digest(Path(path))!=revision:raise ValueError('PDF changed before indexing. Reimport the current version.')
        with fitz.open(path) as doc:
            index.begin(doc_id,revision,len(doc));warnings=[];section=''
            for page in doc:
                result=extract_page(page,languages)
                for unit in result['units']:
                    if unit['heading']:section=unit['heading']
                    elif section:unit['heading']=section
                index.put_page(doc_id,revision,result)
                warnings.extend(f"p.{page.number+1}: {w}" for w in result['warnings'])
        if digest(Path(path))!=revision:raise ValueError('PDF changed during indexing. Reimport it before asking questions.')
        if embed_model:
            from .evidence import OllamaEmbeddings
            try:index.cache_embeddings([doc_id],OllamaEmbeddings(embed_model))
            except Exception as exc:warnings.append('Embeddings unavailable; lexical search remains available: '+str(exc)[:180])
        index.finish(doc_id,'\n'.join(warnings[:30]))
    except Exception as exc:
        index.finish(doc_id,str(exc),error=True)
        raise


def page_image(path, page_number, width=1200, bbox=None):
    with fitz.open(path) as doc:
        if page_number<1 or page_number>len(doc):raise ValueError('Page is outside this document')
        page=doc[page_number-1]
        scale=min(2.5,max(100,min(width,1800))/max(page.rect.width,1))
        # Maximum total pixels, including unusually tall pages.
        scale=min(scale,(6_000_000/max(1,page.rect.get_area()))**.5)
        return page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png')
