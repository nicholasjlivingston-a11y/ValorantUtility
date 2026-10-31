#!/usr/bin/env python3
"""Colab bootstrap: put a verified vrfkit binary in ./bin and stop if anything is off.

Run in a Colab cell:  %run parser/colab_bootstrap.py   (or: python3 parser/colab_bootstrap.py [DRIVE_PATH])

1. Mounts Google Drive when running in Colab.
2. Copies vrfkit from DRIVE_PATH (default MyDrive/valosaber/bin/vrfkit) to ./bin/vrfkit.
3. Checks its SHA-256 against parser/vrfkit.sha256 and refuses to continue on a mismatch.
4. Marks it executable. It never downloads from anywhere else and never runs the binary.
Not yet tested inside Colab; the hash check was tested locally.
"""
import hashlib, os, shutil, stat, sys
from pathlib import Path

DEFAULT = "/content/drive/MyDrive/valosaber/bin/vrfkit"
src = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else DEFAULT)
here = Path(__file__).resolve().parent
want = (here / "vrfkit.sha256").read_text().split()[0].lower()
dst = Path("bin/vrfkit")

if not src.exists():
    try:
        from google.colab import drive  # only exists in Colab
        drive.mount("/content/drive")
    except ImportError:
        pass
if not src.exists():
    sys.exit(f"vrfkit not found at {src}. Put it in Drive, or pass the path as an argument.")

h = hashlib.sha256(src.read_bytes()).hexdigest()
if h != want:
    sys.exit(f"REFUSING: sha256 {h} does not match parser/vrfkit.sha256 ({want}). Do not run this binary.")
dst.parent.mkdir(exist_ok=True)
shutil.copyfile(src, dst)
dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print(f"vrfkit verified and installed at {dst} (sha256 {h[:12]}...)")
