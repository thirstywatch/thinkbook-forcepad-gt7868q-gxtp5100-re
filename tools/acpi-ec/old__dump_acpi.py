# -*- coding: utf-8 -*-
"""Dump ACPI table bodies from HKLM\\HARDWARE\\ACPI (recursive; no reg.exe)."""
import os, sys, winreg

OUT = r"<WORKSPACE>"
os.makedirs(OUT, exist_ok=True)

base = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\ACPI", 0, winreg.KEY_READ)

def subkeys(h):
    out, i = [], 0
    while True:
        try:
            out.append(winreg.EnumKey(h, i))
        except OSError:
            return out
        i += 1

def values(h):
    out, i = [], 0
    while True:
        try:
            out.append(winreg.EnumValue(h, i))
        except OSError:
            return out
        i += 1

def best_blob(h):
    best = None
    for name, data, typ in values(h):
        if isinstance(data, bytes) and len(data) > 60:
            if best is None or len(data) > len(best):
                best = data
    return best

rows = []

def walk(h, path, depth):
    blob = best_blob(h)
    if blob is not None:
        name = "_".join(path)
        fn = os.path.join(OUT, name + ".bin")
        with open(fn, "wb") as f:
            f.write(blob)
        rows.append(("/".join(path), len(blob), fn))
    if depth >= 3:
        return
    for k in subkeys(h):
        try:
            kh = winreg.OpenKey(h, k, 0, winreg.KEY_READ)
        except OSError:
            continue
        walk(kh, path + [k], depth + 1)

for top in subkeys(base):
    try:
        th = winreg.OpenKey(base, top, 0, winreg.KEY_READ)
    except OSError:
        continue
    walk(th, [top], 0)

print("== dumped ACPI table bodies ==")
tot = 0
for p, n, fn in rows:
    tot += n
    print("  %-28s %8d bytes  %s" % (p, n, os.path.basename(fn)))
print()
print("%d tables, %d bytes total -> %s" % (len(rows), tot, OUT))
