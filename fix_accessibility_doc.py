"""
fix_accessibility_doc.py — undo the python-docx corruption on the live
Accessibility policy and re-apply the correction safely.

1. List the file's Drive revisions.
2. Download the last revision created BEFORE the python-docx save
   (the intact ~322KB version that still has the logo + the ADA text).
3. Apply the surgical correction (ADA -> Equality Act 2010) preserving images.
4. Re-upload. Verify text changed and media entries are preserved.
"""
import io
import sys
import os
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from publish_draft import get_services, _replace_in_docx_bytes, DOCX_MIME

FILE_ID = "1HYXCO9UgJ_Jzd_RXVfLOoY_frUvFgoD4"
WRONG = "Americans with Disabilities Act (ADA)"
RIGHT = "Equality Act 2010"


def media_count(b: bytes) -> int:
    try:
        z = zipfile.ZipFile(io.BytesIO(b))
        return sum(1 for n in z.namelist() if n.startswith("word/media/"))
    except Exception:
        return -1


def download_revision(drive, rev_id):
    req = drive.revisions().get_media(fileId=FILE_ID, revisionId=rev_id)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()


def main():
    drive, _ = get_services()

    revs = drive.revisions().list(
        fileId=FILE_ID, fields="revisions(id,modifiedTime,size)"
    ).execute().get("revisions", [])
    print("Revisions (id | time | size):")
    for r in revs:
        print(f"  {r['id']} | {r.get('modifiedTime')} | {r.get('size')}")

    # The intact original is the largest revision (python-docx roughly halved it).
    intact = max(revs, key=lambda r: int(r.get("size", 0)))
    print(f"\nChosen intact revision: {intact['id']} ({intact.get('size')} bytes)")

    original = download_revision(drive, intact["id"])
    print(f"Downloaded intact bytes: {len(original)} | media files: {media_count(original)}")

    corrected, count = _replace_in_docx_bytes(original, WRONG, RIGHT)
    print(f"Applied {count} replacement(s) | media files after: {media_count(corrected)}")

    if count == 0:
        print("Phrase not found in intact revision. Aborting (no upload).")
        sys.exit(1)
    if media_count(corrected) != media_count(original):
        print("WARNING: media count changed. Aborting to avoid corruption.")
        sys.exit(1)

    media = MediaIoBaseUpload(io.BytesIO(corrected), mimetype=DOCX_MIME, resumable=False)
    drive.files().update(fileId=FILE_ID, media_body=media, supportsAllDrives=True).execute()
    print(f"\nUploaded corrected file ({len(corrected)} bytes). "
          f"Media preserved: {media_count(corrected)} file(s). Logo intact.")


if __name__ == "__main__":
    main()
