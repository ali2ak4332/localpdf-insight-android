"""Small editable PDF fixtures and independent PyMuPDF export inspection.

The browser writes actual saveDocument/native-export bytes; inspection never uses
the browser's annotation storage as its expected result.
"""
import hashlib
import json
import sys
from pathlib import Path

import fitz


def fixtures(root):
    root.mkdir(parents=True, exist_ok=True)
    with fitz.open() as doc:
        for number in range(3):
            page = doc.new_page(width=595, height=842)
            page.insert_text((50, 60), f"Private agreement - Page {number + 1}", fontsize=18)
            page.insert_text((50, 100), "Original source passage remains linked to this document.", fontsize=12)
            if number == 1:
                page.insert_text((50, 160), "Signature: __________________________", fontsize=14)
            if number == 2:
                page.insert_htmlbox(
                    fitz.Rect(40, 150, 550, 250), '<p dir="rtl">توقيع المستند مع الاحتفاظ بالمصدر الأصلي.</p>',
                    css="@font-face {font-family: validation; src: url(DejaVuSans.ttf);} * {font-family:validation; font-size:20px;}",
                    archive=fitz.Archive("/usr/share/fonts/truetype/dejavu"),
                )
        doc.save(root / "editable.pdf")
    with fitz.open() as doc:
        page = doc.new_page(width=700, height=400)
        page.insert_text((40, 70), "Intrinsically rotated signature page", fontsize=16)
        page.set_rotation(90)
        doc.save(root / "rotated-editable.pdf")
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 50), "PDF form validation", fontsize=18)
        page.insert_text((50, 110), "Name:", fontsize=12)
        text = fitz.Widget()
        text.field_name = "signer_name"
        text.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        text.rect = fitz.Rect(110, 90, 430, 120)
        text.field_value = ""
        text.text_font = "Helv"
        text.text_fontsize = 14
        page.add_widget(text)
        page.insert_text((50, 165), "Approved:", fontsize=12)
        approved = fitz.Widget()
        approved.field_name = "approved"
        approved.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
        approved.rect = fitz.Rect(120, 145, 140, 165)
        approved.field_value = "Off"
        page.add_widget(approved)
        doc.save(root / "form.pdf")


def inspect(original, exported, output):
    source_sha = hashlib.sha256(original.read_bytes()).hexdigest()
    exported_sha = hashlib.sha256(exported.read_bytes()).hexdigest()
    report = {"original_sha": source_sha, "exported_sha": exported_sha, "pages": []}
    with fitz.open(original) as old, fitz.open(exported) as doc:
        report["page_count"] = len(doc)
        for number, page in enumerate(doc):
            annotations = []
            for annotation in page.annots() or []:
                annotations.append({"type": annotation.type[1], "rect": list(annotation.rect),
                                    "vertices": annotation.vertices, "info": annotation.info})
            widgets = [{"name": widget.field_name, "value": widget.field_value} for widget in page.widgets() or []]
            native = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            native.save(output / f"exported-page-{number + 1}.png")
            before = old[number].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            changed = sum(a != b for a, b in zip(before.samples, native.samples)) if before.width == native.width and before.height == native.height else -1
            report["pages"].append({"number": number + 1, "rotation": page.rotation, "annotations": annotations,
                                    "widgets": widgets, "text": page.get_text(), "changed_channels": changed})
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1] == "fixtures":
        fixtures(Path(sys.argv[2]))
    elif sys.argv[1] == "inspect":
        inspect(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    else:
        raise SystemExit("fixtures ROOT | inspect ORIGINAL EXPORTED ARTIFACTS")
