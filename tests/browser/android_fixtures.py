"""Reader fixtures: large native text, revision, mixed Arabic and an image-only scan."""
import sys
from pathlib import Path

import fitz


root = Path(sys.argv[1])
root.mkdir(parents=True, exist_ok=True)
for filename, pages, notice in [("agreement.pdf", 150, 30), ("revision.pdf", 20, 60)]:
    with fitz.open() as doc:
        for n in range(pages):
            page = doc.new_page()
            page.insert_text((55, 60), f"Reader validation - Page {n + 1}", fontsize=19)
            if n == 17:
                text = (f"8. TERMINATION\nThe agreement may be terminated with {notice} days written notice.\n"
                        "The service fee is AED 25,000 per month.\n"
                        "The supplier must return confidential materials within 10 days.")
            else:
                text = "This is a native PDF paragraph for private reading and saved notes.\n\n" * 9
            page.insert_textbox(fitz.Rect(55, 110, 535, 700), text, fontsize=12)
        doc.set_toc([[1, "Introduction", 1], [1, "Termination", 18], [1, "Appendix", pages]])
        doc.save(root / filename)

for filename, css, archive in [
    ("arabic.pdf", "@font-face {font-family: validation; src: url(DejaVuSans.ttf);}"
                   "* {font-family: validation; font-size:20px;}", fitz.Archive("/usr/share/fonts/truetype/dejavu")),
    ("broken-arabic-font.pdf", "* {font-size:20px;}", None),
]:
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_htmlbox(fitz.Rect(40, 40, 550, 320),
                            '<p dir="rtl">إنهاء العقد بإشعار كتابي خلال ٣٠ يوماً.</p>'
                            '<p dir="rtl">قيمة الرسوم ٥٠٠ درهم. Contract ABC-123 AED 500</p>',
                            css=css, archive=archive)
        doc.save(root / filename)

with fitz.open() as original, fitz.open() as scan:
    page = original.new_page()
    page.insert_text((55, 80), "SCANNED PAGE FOR PRIVATE OFFLINE READING", fontsize=18)
    page.insert_text((55, 130), "Scan-only answer must not appear in native text search.", fontsize=13)
    raster = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    copied = scan.new_page(width=page.rect.width, height=page.rect.height)
    copied.insert_image(copied.rect, stream=raster.tobytes("png"))
    scan.save(root / "scan.pdf")

with fitz.open(root / "revision.pdf") as doc:
    doc.save(root / "protected.pdf", encryption=fitz.PDF_ENCRYPT_AES_256,
             user_pw="reader-secret", owner_pw="owner-secret")

with fitz.open() as doc:
    page = doc.new_page(width=700, height=300)
    page.insert_text((55, 85), "Rotated evidence must remain on this page.", fontsize=17)
    page.set_rotation(90)
    doc.save(root / "rotated.pdf")
