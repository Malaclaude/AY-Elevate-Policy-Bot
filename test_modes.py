"""Verify the three finding modes: edit, clarify (insert), notice."""
import io, sys, os, json, zipfile, urllib.request, urllib.parse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from docx import Document
from detect_gap import detect_all_gaps
from send_review import encode_findings
from publish_draft import get_services, _download_bytes, _insert_paragraph_bytes

BASE = "http://localhost:5001"
RID = "modetest1"
SAFE_ID = "1kZDRHmz4b-liBx_w8Nnwvxuz56GLtJow"
TEXT = "Americans with Disabilities Act (ADA). Working Together to Safeguard Children Act 2018."


def media_count(b):
    z = zipfile.ZipFile(io.BytesIO(b)); return sum(1 for n in z.namelist() if n.startswith("word/media/"))


def post(path):
    req = urllib.request.Request(BASE + path, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=15); return r.getcode(), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


print("== 1. paragraph insert keeps the docx valid + images intact ==")
orig = _download_bytes(get_services()[0], SAFE_ID)
ins = _insert_paragraph_bytes(orig, "TEST SECTION inserted by bot.")
doc = Document(io.BytesIO(ins))  # raises if XML is broken
has = any("TEST SECTION inserted by bot." in p.text for p in doc.paragraphs)
print(f"valid docx: True | text present: {has} | media {media_count(orig)} -> {media_count(ins)}",
      "PASS" if has and media_count(orig) == media_count(ins) else "FAIL")

print("\n== 2. dashboard renders the three modes ==")
findings = detect_all_gaps(TEXT)
all_enc = urllib.parse.quote(encode_findings(findings))
html = urllib.request.urlopen(f"{BASE}/review?id={RID}&d={all_enc}&test=1", timeout=10).read().decode()
print("edit card (Approve and rewrite):", "PASS" if "Approve and rewrite" in html else "FAIL")
print("clarify card (radio + Apply my answer):", "PASS" if 'type="radio"' in html and "Apply my answer" in html else "FAIL")
print("notice card (Mark as seen):", "PASS" if "Mark as seen" in html else "FAIL")

print("\n== 3. apply each mode (test mode, no Drive) ==")
def enc(f): return urllib.parse.quote(encode_findings([f]))
fmap = {f["gap_id"]: f for f in findings}
c, j = post(f"/apply?id={RID}&d={enc(fmap['ada_jurisdiction'])}&test=1")
print("edit ada ->", j.get("status"), "PASS" if j["status"] == "approved" else "FAIL")
c, j = post(f"/apply?id={RID}&d={enc(fmap['ofsted_camps_gap'])}&test=1&choice=exempt")
print("clarify ofsted (choice=exempt) ->", j.get("status"), "PASS" if j["status"] == "approved" else "FAIL")
c, j = post(f"/apply?id={RID}&d={enc(fmap['insurance_expired'])}&test=1")
print("notice insurance ->", j.get("status"), "PASS" if j["status"] == "approved" else "FAIL")
