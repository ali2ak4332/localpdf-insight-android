import fitz,json,hashlib
from pathlib import Path
import argparse
parser=argparse.ArgumentParser();parser.add_argument('inputs',type=Path);args=parser.parse_args()
p=args.inputs;b=p.parent
# Genuine published content; derivatives are explicitly named as stress/OCR inputs.
a=fitz.open(p/'tracemonkey.pdf');d=fitz.open()
for n in range(410):d.insert_pdf(a,from_page=n%len(a),to_page=n%len(a))
d.save(p/'stress-410-text.pdf',garbage=4,deflate=True)
for lang in ['en','ar']:
 a=fitz.open(p/f'adib-results-{lang}.pdf');d=fitz.open()
 for n in [1,5]:
  pg=a[n];pix=pg.get_pixmap(matrix=fitz.Matrix(2,2));new=d.new_page(width=pg.rect.width,height=pg.rect.height);new.insert_image(new.rect,stream=pix.tobytes('png'))
 d.save(p/f'scan-{lang}.pdf',deflate=True)
a=fitz.open(p/'adib-results-en.pdf');scan=fitz.open(p/'scan-en.pdf');d=fitz.open()
for n in range(150):
 src=scan if n%2 else a;page=n%len(src);d.insert_pdf(src,from_page=page,to_page=page)
d.save(p/'stress-150-mixed.pdf',garbage=4,deflate=True)
manifest=[]
for f in p.glob('*.pdf'):
 d=fitz.open(f);manifest.append(dict(file=f.name,pages=len(d),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
(b/'corpus.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))

# Controlled comparison revisions, labelled to avoid confusing them with publisher versions.
d=fitz.open(p/'adib-results-en.pdf');page=d[1];r=page.search_for('7.1')[0];page.add_redact_annot(r,fill=(1,1,1));page.apply_redactions();page.insert_text((r.x0,r.y1-2),'9.1',fontsize=10);d.save(p/'modified-for-validation.pdf')
d=fitz.open(p/'tracemonkey.pdf');d.select(list(reversed(range(len(d)))));d.save(p/'reordered-paper.pdf')
