"""
roundtrip_test.py — non-destructive write proof.

Exercises the SAME Drive calls production uses (_download_bytes + _upload_bytes)
on the Accessibility policy, re-uploading byte-identical content. Proves the write
path lands. No policy text changes.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from publish_draft import get_services, _download_bytes, _upload_bytes

FILE_ID = "1HYXCO9UgJ_Jzd_RXVfLOoY_frUvFgoD4"  # Accessibility and Inclusiveness Policy


def mtime(drive):
    return drive.files().get(
        fileId=FILE_ID, fields="modifiedTime", supportsAllDrives=True
    ).execute().get("modifiedTime")


def main():
    drive, _ = get_services()
    before = mtime(drive)
    print(f"modifiedTime BEFORE: {before}")

    data = _download_bytes(drive, FILE_ID)
    print(f"Downloaded {len(data)} bytes OK")

    _upload_bytes(drive, FILE_ID, data)  # identical bytes back in
    after = mtime(drive)
    print(f"modifiedTime AFTER:  {after}")

    if after != before:
        print("\nWRITE CONFIRMED — modifiedTime advanced. Content unchanged.")
    else:
        print("\nWRITE DID NOT LAND — modifiedTime unchanged. Investigate.")


if __name__ == "__main__":
    main()
