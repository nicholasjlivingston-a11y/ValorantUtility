#!/usr/bin/env python3
"""Colab bootstrap: install a REGISTERED vrfkit binary into ./bin and refuse everything else.

Run in a Colab cell:  !python3 parser/colab_bootstrap.py   [optional: path to a vrfkit file or a zip holding bin/vrfkit]

Looks for candidates in this order (first registered one wins):
  1. the path you pass, if any
  2. ./bin/vrfkit already in the package
  3. MyDrive/valosaber/bin/ : a loose 'vrfkit' file, then every .zip that holds bin/vrfkit
A candidate is accepted only if its SHA-256 appears in parser/vrfkit.sha256. Every candidate's hash is printed, so an
unregistered binary can be sent to the maintainer (parser/register_vrfkit.py prints the registry entry).
It never downloads anything and never runs the binary.
"""
import hashlib, stat, sys, zipfile
from pathlib import Path

here = Path(__file__).resolve().parent
want = {ln.split()[0].lower() for ln in (here / "vrfkit.sha256").read_text().splitlines() if ln.strip()}
DRIVE_BIN = Path("/content/drive/MyDrive/valosaber/bin")
dst = Path("bin/vrfkit")


def read_candidate(p: Path):
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            m = [n for n in z.namelist() if n.endswith("bin/vrfkit")]
            return z.read(m[0]) if len(m) == 1 else None
    return p.read_bytes()


cands = []
if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
    cands.append(Path(sys.argv[1]))
if dst.exists():
    cands.append(dst)
if not DRIVE_BIN.exists():
    try:
        from google.colab import drive  # only exists in Colab
        drive.mount("/content/drive")
    except ImportError:
        pass
if DRIVE_BIN.exists():
    cands += [DRIVE_BIN / "vrfkit"] + sorted(DRIVE_BIN.glob("*.zip"))
cands = [c for c in dict.fromkeys(cands) if c.exists()]
if not cands:
    sys.exit("vrfkit not found. Put the binary (or a zip containing bin/vrfkit) in MyDrive/valosaber/bin/ or pass its path.")

chosen = None
for c in cands:
    data = read_candidate(c)
    if data is None:
        print(f"skip {c}: no single bin/vrfkit inside")
        continue
    h = hashlib.sha256(data).hexdigest()
    ok = h in want
    print(f"{'REGISTERED  ' if ok else 'unregistered'} {h}  {len(data):>10,} bytes  {c}")
    if ok and chosen is None:
        chosen = (c, data, h)
if chosen is None:
    sys.exit("REFUSING: no candidate is registered in parser/vrfkit.sha256. Do not run any of these binaries. "
             "To register one you trust, run parser/register_vrfkit.py on it and send the output to the maintainer.")
c, data, h = chosen
dst.parent.mkdir(exist_ok=True)
if not (dst.exists() and dst.read_bytes() == data):
    dst.write_bytes(data)
dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print(f"vrfkit verified and installed at {dst} (sha256 {h[:12]}..., from {c})")
