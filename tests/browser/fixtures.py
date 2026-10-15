import sys
from pathlib import Path
import fitz
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
for filename,pages,notice in [('agreement.pdf',150,30),('revision.pdf',20,60)]:
    with fitz.open() as doc:
        for n in range(pages):
            page=doc.new_page()
            page.insert_text((55,60),f'LocalPDF Reader Verification - Page {n+1}',fontsize=19)
            if n==17:
                page.insert_textbox(fitz.Rect(55,110,535,270),f'8. TERMINATION\nThe agreement may be terminated with {notice} days written notice.\nThe service fee is AED 25,000 per month.\nThe supplier must return confidential materials within 10 days.',fontsize=12)
            else:
                page.insert_textbox(fitz.Rect(55,110,535,700),('This document tests continuous reading, search, source navigation and local indexing.\n\n'*9),fontsize=12)
        doc.set_toc([[1,'Introduction',1],[1,'Termination',18],[1,'Appendix',pages]])
        doc.save(root/filename)
with fitz.open() as doc:
    page=doc.new_page()
    page.insert_htmlbox(fitz.Rect(40,40,550,250),'<p dir="rtl">إنهاء العقد بإشعار كتابي خلال ٣٠ يوماً. Contract ABC-123 AED 500</p>',css='* {font-size:20px;}')
    doc.save(root/'arabic.pdf')
