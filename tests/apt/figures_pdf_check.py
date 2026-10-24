"""PDF.js integration check for the deterministic figure extractor (no model).

Usage: CHROMIUM_EXECUTABLE=... python tests/apt/figures_pdf_check.py
Builds synthetic PDFs with PyMuPDF (statements, earnings release, fund and ETF fact sheets,
a technical fact sheet, a contract, an infographic, a regulation sheet), extracts them with the
app's own PDF.js/IndexedDB pipeline (five_task_extract.cjs), then checks figure candidates.
Synthetic numbers; layouts imitate the public corpus. Requires PyMuPDF, Playwright and Chromium.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pymupdf as fitz

HERE = Path(__file__).resolve().parent


def doc_with(pages):
    d = fitz.open()
    for lines in pages:
        p = d.new_page(width=612, height=792)
        for (x, y, text, size) in lines:
            p.insert_text((x, y), text, fontsize=size, fontname="helv")
    return d


def row(y, label, values, xs=(330, 400, 470, 540), size=9, dollar=False):
    return [(50, y, label, size)] + [(x, y, ("$ " if dollar else "") + v, size) for x, v in zip(xs, values)]


def cells(y, label, values, xs, size=8):
    return [(50, y, label, size)] + [(x, y, v, size) for x, v in zip(xs, values)]


def build(out):
    fin = [[(50, 50, "Northwind Devices Inc.", 12), (50, 66, "CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS (Unaudited)", 10),
            (50, 80, "(In millions, except number of shares, which are reflected in thousands, and per-share amounts)", 8),
            (330, 100, "Three Months Ended", 8), (470, 100, "Twelve Months Ended", 8),
            (330, 112, "September 28, 2024", 7), (400, 112, "September 30, 2023", 7), (470, 112, "September 28, 2024", 7), (540, 112, "September 30, 2023", 7),
            (50, 128, "Net sales:", 9)]
           + row(140, "Products", ["61,250", "58,410", "250,118", "247,903"], dollar=True)
           + row(152, "Services", ["22,035", "19,872", "84,610", "76,402"])
           + row(164, "Total net sales", ["83,285", "78,282", "334,728", "324,305"])
           + row(184, "Operating income", ["24,102", "22,511", "96,447", "91,028"])
           + row(196, "Provision for income taxes", ["(1,215)", "2,980", "16,733", "15,100"])
           + row(208, "Net income", ["16,742", "19,530", "81,996", "79,412"], dollar=True)
           + row(228, "Diluted earnings per share", ["1.12", "1.27", "5.40", "5.10"], dollar=True)
           + row(240, "Shares used in computing diluted earnings per share", ["14,950,112", "15,320,664", "15,180,240", "15,560,101"])
           + [(50, 770, "See accompanying Notes.", 7), (540, 770, "Page 1 of 2", 7)]]
    fin.append([(50, 50, "Northwind Devices Inc.", 12), (50, 66, "CONDENSED CONSOLIDATED BALANCE SHEETS (Unaudited)", 10),
                (50, 80, "(In millions)", 8), (400, 100, "September 28, 2024", 7), (470, 100, "September 30, 2023", 7)]
               + row(116, "Cash and cash equivalents", ["31,108", "29,965"], xs=(400, 470), dollar=True)
               + row(128, "Total assets", ["362,880", "352,583"], xs=(400, 470), dollar=True)
               + row(140, "Total liabilities", ["301,422", "290,437"], xs=(400, 470))
               + [(50, 770, "Page 2 of 2", 7)])
    fund = [[(50, 50, "Contoso Total Market Index Fund", 14), (50, 70, "Fact sheet | September 30, 2024", 9),
             (50, 96, "Expense ratio as of 04/26/2024: 0.04%", 9), (50, 110, "Fund total net assets $1.79 trillion", 9),
             (50, 124, "Number of stocks 3,691", 9), (50, 150, "Average annual total returns", 10),
             (200, 166, "1 year", 8), (260, 166, "3 years", 8), (320, 166, "5 years", 8), (380, 166, "10 years", 8),
             (50, 180, "Fund (at NAV)", 8), (200, 180, "35.19%", 8), (260, 180, "10.27%", 8), (320, 180, "15.23%", 8), (380, 180, "12.80%", 8),
             (50, 194, "Benchmark", 8), (200, 194, "35.20%", 8), (260, 194, "10.26%", 8), (320, 194, "15.24%", 8), (380, 194, "12.81%", 8),
             (50, 220, "Past performance is no guarantee of future returns. Figures for periods ended September 30, 2024.", 8)]]
    tech = [[(50, 50, "Aurora Lander Mission Fact Sheet", 14),
             (50, 80, "Launch: July 30, 2027, from Cape Canaveral, Florida.", 9),
             (50, 94, "The lander weighs 1,025 kilograms (2,260 pounds) including its robotic arm.", 9),
             (50, 108, "Its radioisotope generator provides about 110 watts of electrical power at launch.", 9),
             (50, 122, "Planned surface mission: at least one Mars year (about 687 Earth days).", 9),
             (50, 136, "Engineers estimate the arm could lift up to 15 kg, but this has not been tested on Mars.", 9),
             (50, 160, "Top speed on flat ground is 152 meters per hour.", 9)]]
    contract = [[(50, 50, "MUTUAL NONDISCLOSURE AGREEMENT", 13), (50, 76, "1. Definitions", 10),
                 (50, 92, "1.1 \"Confidential Information\" means information disclosed by either party under this Agreement.", 8),
                 (50, 110, "4. Term. This Agreement remains in force for 3 years from the Effective Date.", 8),
                 (50, 126, "7.2 Notice is deemed delivered 24 hours after dispatch by overnight courier, or the earlier of", 8),
                 (50, 138, "72 hours or signed receipt when sent by certified mail.", 8),
                 (50, 156, "The Recipient shall pay liquidated damages of USD 50,000 for each breach of Section 5.", 8),
                 (50, 174, "Signed: ____________________ Date: ____/____/20____", 8), (540, 770, "Page 1 of 1", 7)]]
    info = [[(50, 50, "Fabrikam Q3 2024 Earnings at a Glance", 14), (50, 80, "Revenue $13.3B, up 6% year over year", 11),
             (50, 100, "Gross margin 38.8%", 11), (50, 120, "Operating cash flow $2.1 billion in Q3", 11),
             (50, 140, "Guidance: Q4 revenue expected between $13.6B and $14.0B", 11)]]
    X4 = (330, 400, 470, 540)
    bh = [[(50, 50, "Tailspin Holdings Inc. news release", 12),
           (50, 70, "Tailspin's operating earnings for the third quarter of 2024 were $10.1 billion.", 9),
           (50, 90, "(dollars in millions)", 8),
           (330, 106, "Third Quarter", 8), (470, 106, "First Nine Months", 8),
           (330, 118, "2024", 8), (400, 118, "2023", 8), (470, 118, "2024", 8), (540, 118, "2023", 8)]
          + cells(132, "Insurance-underwriting", ["$ 750", "$ 2,423", "$ 6,451", "$ 5,029"], X4)
          + cells(144, "Investments and derivative gains/losses", ["16,000", "(23,000)", "45,000", "38,000"], X4)
          + cells(156, "Net earnings attributable to shareholders", ["$ 26,251", "$ (12,767)", "$ 81,900", "$ 74,236"], X4)
          + cells(168, "Other", ["—", "112", "—", "300"], X4)
          + [(50, 190, "Book value per share increased 14% in the first nine months of 2024.", 9)]]
    fund2 = [[(50, 50, "Woodgrove Core S&P 500 ETF", 14), (50, 70, "Fact Sheet as of 09/30/2024", 9),
             (50, 90, "Average Annual Returns", 10),
             (200, 104, "1y", 8), (260, 104, "5y", 8), (320, 104, "10y", 8), (380, 104, "Since Inception", 8),
             (50, 118, "NAV", 8)] + [(x, 118, v, 8) for x, v in zip((200, 260, 320, 380), ["36.31%", "15.95%", "13.35%", "7.98%"])]
           + [(50, 140, "Calendar Year Returns", 10)]
           + [(200 + 50*i, 154, y, 8) for i, y in enumerate(["2023", "2022", "2021", "2020", "2019"])]
           + [(50, 168, "Total Return", 8)] + [(200 + 50*i, 168, v, 8) for i, v in enumerate(["26.24%", "-18.13%", "28.66%", "18.38%", "31.43%"])]
           + [(50, 190, "Expense Ratio 0.03%", 9), (50, 204, "Number of Holdings 504", 9), (50, 218, "Net Assets of Fund $570,512,341,123", 9)]]
    epa = [[(50, 50, "Proposed PFAS National Primary Drinking Water Regulation", 12),
            (50, 74, "EPA is setting an enforceable Maximum Contaminant Level (MCL) of 4.0 parts per trillion (ppt) for PFOA.", 8),
            (50, 88, "Public water systems must comply with the MCLs by 2029 and complete initial monitoring by 2027.", 8),
            (50, 102, "Approximately 6% to 10% of the 66,000 public drinking water systems may have to take action.", 8),
            (50, 116, "Geothermal heat pumps can reduce energy use by 25%-50% compared with conventional systems.", 8),
            (50, 140, "Contact: (202) 564-4355 or see 40 CFR Part 141.", 8)]]
    docs = [("fin", fin), ("fund", fund), ("tech", tech), ("contract", contract), ("info", info), ("bh", bh), ("etf", fund2), ("epa", epa)]
    manifest = []
    for name, pages in docs:
        path = out / f"{name}.pdf"
        doc_with(pages).save(path)
        manifest.append({"id": name, "title": name, "category": "test", "pdfPath": str(path),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (out / "manifest.json").write_text(json.dumps({"documents": manifest}))
    return out / "manifest.json"


CHECK = r"""
import fs from 'node:fs';
import {lineUnits} from '%s/src/localpdf_insight/static/apt_lines.mjs';
import {figureCandidates} from '%s/src/localpdf_insight/static/apt_figures.mjs';
const corpus=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out={};
for(const d of corpus.documents){const {candidates}=figureCandidates(lineUnits(d.pages));
 out[d.id]=candidates.map(c=>({raw:c.raw,unit:c.unit,period:c.period,row:c.rowLabel,kind:c.kind}));}
console.log(JSON.stringify(out));
""" % (str(HERE.parents[1]), str(HERE.parents[1]))


def main():
    with tempfile.TemporaryDirectory(prefix="apt-figures-pdf-") as directory:
        root = Path(directory)
        manifest = build(root)
        corpus = root / "corpus.json"
        subprocess.run(["node", str(HERE / "five_task_extract.cjs"), str(manifest), str(corpus)], check=True,
                       capture_output=True, text=True, timeout=600)
        script = root / "check.mjs"
        script.write_text(CHECK)
        got = json.loads(subprocess.run(["node", str(script), str(corpus)], check=True, capture_output=True, text=True).stdout)
    def find(doc, raw):
        matches = [c for c in got[doc] if c["raw"] == raw]
        assert matches, (doc, raw, [c["raw"] for c in got[doc]])
        return matches[0]
    checks = 0
    def expect(doc, raw, **fields):
        nonlocal checks
        c = find(doc, raw)
        for k, v in fields.items():
            assert c[k] == v, (doc, raw, k, c[k], v)
            checks += 1
    expect("fin", "61,250", unit="$ millions", period="Three Months Ended September 28, 2024", row="Net sales: Products", kind="table")
    expect("fin", "(1,215)", unit="$ millions", period="Three Months Ended September 28, 2024", row="Provision for income taxes")
    expect("fin", "5.40", unit="$ per share", period="Twelve Months Ended September 28, 2024")
    expect("fin", "15,560,101", unit="thousands of shares", period="Twelve Months Ended September 30, 2023")
    expect("fin", "290,437", unit="$ millions", period="September 30, 2023", row="Total liabilities")
    expect("bh", "(12,767)", unit="$ millions", period="Third Quarter 2023")
    expect("bh", "300", period="First Nine Months 2023")
    expect("bh", "10.1", unit="$ billions", period="third quarter of 2024")
    expect("fund", "12.80", unit="%", period="10 years", row="Fund (at NAV)")
    expect("etf", "-18.13", unit="%", period="2022", row="Total Return")
    expect("etf", "7.98", period="Since Inception")
    expect("tech", "1,025", unit="kilograms", period="")
    expect("tech", "152", unit="meters per hour")
    expect("contract", "3", unit="years")
    expect("contract", "72", unit="hours")
    expect("contract", "50,000", unit="USD")
    expect("info", "13.3", unit="$ billions", period="Q3 2024")
    expect("epa", "4.0", unit="parts per trillion")
    absent = {"contract": ["1.1", "4", "7.2", "1", "20"], "etf": ["500"], "epa": ["40", "202", "564", "4355", "2029"],
              "fin": ["1", "2", "2024"], "tech": ["30", "2027"]}
    for doc, raws in absent.items():
        present = {c["raw"] for c in got[doc]}
        for raw in raws:
            assert raw not in present, (doc, raw)
            checks += 1
    print(json.dumps({"passed": True, "checks": checks, "documents": len(got),
                      "scope": "Synthetic PDFs through the app's PDF.js extraction; deterministic extractor only, no model"}))


if __name__ == "__main__":
    main()
