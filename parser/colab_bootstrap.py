#!/usr/bin/env python3
"""Colab bootstrap: put a verified vrfkit binary in ./bin and stop if anything is off.

Run in a Colab cell:  %run parser/colab_bootstrap.py   (or: python3 parser/colab_bootstrap.py [DRIVE_PATH])

1. Mounts Google Drive when running in Colab.
2. Copies vrfkit from DRIVE_PATH to ./bin/vrfkit. With no argument it looks in MyDrive/valosaber/bin/ for the bootstrap zip, then for a loose vrfkit file.
   DRIVE_PATH may also be a bootstrap .zip that holds bin/vrfkit; the file is read from inside the zip.
3. Checks its SHA-256 against parser/vrfkit.sha256 and refuses to continue on a mismatch.
4. Marks it executable. It never downloads from anywhere else and never runs the binary.
Not yet tested inside Colab; the hash check was tested locally.
"""
import hashlib, os, stat, sys
from pathlib import Path

BIN = "/content/drive/MyDrive/valosaber/bin/"
CANDIDATES = [BIN + "valorant_complete_pipeline_bootstrap_package (2).zip", BIN + "vrfkit"]
if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
    src = Path(sys.argv[1])
else:
    src = Path(CANDIDATES[0])
here = Path(__file__).resolve().parent
want = (here / "vrfkit.sha256").read_text().split()[0].lower()
dst = Path("bin/vrfkit")

if not src.exists():
    try:
        from google.colab import drive  # only exists in Colab
        drive.mount("/content/drive")
    except ImportError:
        pass
if not src.exists() and len(sys.argv) <= 1:
    src = next((Path(c) for c in CANDIDATES if Path(c).exists()), src)
if not src.exists():
    sys.exit(f"vrfkit not found at {src}. Put it in Drive, or pass the path as an argument.")

if src.suffix.lower() == ".zip":
    import zipfile
    with zipfile.ZipFile(src) as z:
        members = [n for n in z.namelist() if n.endswith("bin/vrfkit")]
        if len(members) != 1:
            sys.exit(f"expected exactly one bin/vrfkit in {src}, found {members}")
        data = z.read(members[0])
else:
    data = src.read_bytes()
h = hashlib.sha256(data).hexdigest()
if h != want:
    sys.exit(f"REFUSING: sha256 {h} does not match parser/vrfkit.sha256 ({want}). Do not run this binary.")
dst.parent.mkdir(exist_ok=True)
dst.write_bytes(data)
dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print(f"vrfkit verified and installed at {dst} (sha256 {h[:12]}...)")
