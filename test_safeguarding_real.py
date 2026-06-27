"""
Dry-run: does the Working Together fix actually match the REAL Safeguarding doc?
Downloads the live bytes, runs the surgical replace IN MEMORY, verifies, uploads NOTHING.
Leaves the live doc untouched (still 'wrong') so it can be demoed live.
"""
import io, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from docx import Document
from publish_draft import get_services, _download_bytes, _replace_in_docx_bytes

SAFEGUARDING_ID = "1kZDRHmz4b-liBx_w8Nnwvxuz56GLtJow"
SEARCH = "Working Together to Safeguard Children Act 2018"
REPLACE = "Working Together to Safeguard Children 2023"


def main():
    drive, _ = get_services()
    original = _download_bytes(drive, SAFEGUARDING_ID)
    print(f"Downloaded {len(original)} bytes from live Safeguarding doc.")

    updated, count = _replace_in_docx_bytes(original, SEARCH, REPLACE)
    print(f"Surgical replace matched: {count} occurrence(s)")

    doc = Document(io.BytesIO(updated))
    full = "\n".join(p.text for p in doc.paragraphs)
    print(f"Result contains '{REPLACE}': {REPLACE in full}")
    print(f"Result still contains 'Children Act 2018': {'Safeguard Children Act 2018' in full}")

    ok = count >= 1 and REPLACE in full and "Safeguard Children Act 2018" not in full
    print("\nWILL THE FIX LAND ON THE REAL DOC?", "YES" if ok else "NO (phrase split or mismatch)")
    print("(Nothing uploaded. Live doc unchanged.)")


if __name__ == "__main__":
    main()
