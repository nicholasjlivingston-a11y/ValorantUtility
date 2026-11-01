#!/usr/bin/env python3
"""Register a vrfkit binary: hash it and list the replay builds it contains. Never runs the binary.

usage: register_vrfkit.py PATH_TO_VRFKIT_OR_BOOTSTRAP_ZIP [--label "text"] [--write]

Reads the file as bytes, computes its SHA-256 and finds every 'release-NN.NN' string in it (the builds the
decoder knows). Prints the registry entry. With --write it adds the entry to data/vrfkit_supported_builds.json and the
hash to parser/vrfkit.sha256. Without --write nothing is changed, so the output can be pasted to the maintainer.
Listing a build here means the binary contains that build's definitions, not that its output has been verified.
"""
import argparse, hashlib, json, re, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("path"); ap.add_argument("--label", default=""); ap.add_argument("--write", action="store_true")
a = ap.parse_args()
p = Path(a.path)
if p.suffix.lower() == ".zip":
    with zipfile.ZipFile(p) as z:
        m = [n for n in z.namelist() if n.endswith("bin/vrfkit")]
        if len(m) != 1:
            sys.exit(f"expected one bin/vrfkit in {p}, found {m}")
        data = z.read(m[0])
else:
    data = p.read_bytes()
sha = hashlib.sha256(data).hexdigest()
builds = sorted({b.decode() for b in re.findall(rb"release-1[0-9]\.[0-9]+", data)},
                key=lambda s: tuple(int(x) for x in s.split("-")[1].split(".")))
entry = {"label": a.label or "unlabelled", "bytes": len(data), "known_in_binary": builds,
         "thin_support": [], "note": "listed from strings in the binary; output not verified unless stated elsewhere"}
print(json.dumps({sha: entry}, indent=2))
print(f"newest build in this binary: {builds[-1] if builds else 'NONE FOUND'}")
if a.write:
    jp = HERE.parent / "data" / "vrfkit_supported_builds.json"
    reg = json.load(open(jp)); reg.setdefault("binaries", {})[sha] = entry
    json.dump(reg, open(jp, "w"), indent=2)
    sp = HERE / "vrfkit.sha256"; have = sp.read_text() if sp.exists() else ""
    if sha not in have:
        sp.write_text(have.rstrip("\n") + ("\n" if have else "") + f"{sha}  vrfkit\n")
    print("registered in", jp, "and", sp)
