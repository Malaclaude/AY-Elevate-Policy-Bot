"""
create_test_policy.py
Generates a fake policy document with deliberate compliance errors for end-to-end testing.
No external dependencies — uses only stdlib zipfile.

Run from the policy-bot directory:
    python3 src/create_test_policy.py

Produces:
    policies/test/Elevate Test Policy Document.docx

Deliberate errors inserted (all 4 demo findings should fire):
1. ADA reference     → check_ada_error() detects from text
2. Working Together 2018 → check_working_together_version() detects from text
3. No Ofsted mention → check_ofsted_camps_gap() fires (absence check)
4. Insurance expiry  → check_insurance_expiry() always fires (corpus-confirmed)
"""

import os
import zipfile
import io

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>"""

WORD_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>"""


def make_para(text):
    return (
        f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )


POLICY_PARAGRAPHS = [
    "ELEVATE PERFORMANCE ACADEMY",
    "TEST POLICY DOCUMENT — FOR BOT TESTING ONLY",
    "Version: 1.0 | Date: January 2025",
    "",
    "1. PURPOSE",
    "This document sets out Elevate Performance Academy's approach to accessibility, safeguarding, and inclusive practice across all programmes.",
    "",
    "2. ACCESSIBILITY AND INCLUSION",
    "Elevate Performance Academy is committed to ensuring all participants can access our services equally.",
    "In accordance with the Americans with Disabilities Act, we ensure that all facilities and programmes are accessible to individuals with disabilities.",
    "We review our accessibility arrangements annually and make reasonable adjustments where required.",
    "",
    "3. SAFEGUARDING",
    "Elevate Performance Academy takes its safeguarding responsibilities extremely seriously.",
    "This policy has been developed in accordance with the statutory guidance set out in Working Together to Safeguard Children 2018 (HM Government) and reflects current legislation and guidance relevant to the safeguarding and protection of children.",
    "All staff undergo enhanced DBS checks prior to working with young people.",
    "Concerns should be reported to the Designated Safeguarding Lead immediately.",
    "",
    "4. DATA PROTECTION",
    "All personal data is processed in accordance with the UK General Data Protection Regulation (UK GDPR) and the Data Protection Act 2018.",
    "We collect only the data necessary to deliver our programmes.",
    "",
    "5. HEALTH AND SAFETY",
    "Elevate complies with the Health and Safety at Work etc. Act 1974 and associated regulations.",
    "Risk assessments are completed for all programme locations and activities.",
    "",
    "6. EQUALITY AND DIVERSITY",
    "We are committed to promoting equality of opportunity for all staff and participants.",
    "This policy should be read alongside our Equality, Diversity and Inclusion policy.",
    "",
    "7. REVIEW",
    "This policy will be reviewed annually or following any significant change in legislation or guidance.",
    "Approved by: Chad Thorne | Date: January 2025",
]


def build_document_xml():
    ns = (
        'xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    )
    paras = "\n".join(make_para(p) for p in POLICY_PARAGRAPHS)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document {ns}>
  <w:body>
    {paras}
  </w:body>
</w:document>"""


def create_test_docx(output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("word/_rels/document.xml.rels", WORD_RELS)
        zf.writestr("word/document.xml", build_document_xml())

    with open(output_path, "wb") as f:
        f.write(buf.getvalue())

    print(f"Test policy document created: {output_path}")
    print("\nDeliberate errors inserted:")
    print("  [HIGH] ADA reference — 'Americans with Disabilities Act' (should be Equality Act 2010)")
    print("  [HIGH] Working Together 2018 — outdated safeguarding framework (should be 2023)")
    print("  [HIGH] Insurance expiry — corpus-confirmed (always fires)")
    print("  [MED]  No Ofsted/camps reference — absence gap (will be flagged)")


if __name__ == "__main__":
    import sys
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output = os.path.join(repo_root, "policies", "test", "Elevate Test Policy Document.docx")
    create_test_docx(output)
    print(f"\nRun the bot against it:")
    print(f"  python3 src/main.py --doc policies/test/Elevate\\ Test\\ Policy\\ Document.docx")
