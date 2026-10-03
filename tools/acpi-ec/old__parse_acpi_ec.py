# -*- coding: utf-8 -*-
"""Parse dumped ACPI tables: locate EmbeddedControl regions and decode their Field lists
(= the EC RAM byte map). Pure offline; nothing is touched on the machine."""
import os, re, glob, struct

DIR = r"<WORKSPACE>"

NAME_OK = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")

def is_nameseg(b):
    if len(b) != 4:
        return False
    if not (b[0:1].isalpha() or b[0:1] == b"_"):
        return False
    return all(c in NAME_OK for c in b)

def pkg_len(data, i):
    """Decode ACPI PkgLength at offset i. Returns (value, bytes_consumed)."""
    if i >= len(data):
        return None, 0
    lead = data[i]
    n = lead >> 6
    if n == 0:
        return lead & 0x3F, 1
    v = lead & 0x0F
    for k in range(1, n + 1):
        if i + k >= len(data):
            return None, 0
        v |= data[i + k] << (8 * k)
    return v, n + 1

def read_integer(data, i):
    """Decode ACPI integer object at i. Returns (value, bytes_consumed)."""
    if i >= len(data):
        return None, 0
    op = data[i]
    if op == 0x00:
        return 0, 1
    if op == 0x01:
        return 1, 1
    if op == 0x0A:
        return data[i + 1], 2
    if op == 0x0B:
        return struct.unpack_from("<H", data, i + 1)[0], 3
    if op == 0x0C:
        return struct.unpack_from("<I", data, i + 1)[0], 5
    if op == 0x0E:
        return struct.unpack_from("<Q", data, i + 1)[0], 9
    return None, 0

def parse_field_list(data, i, end):
    """Parse a FieldList at offset i; returns (list_of(name, byte_off, bit_off, width_bits, kind), next_i)."""
    out = []
    bitpos = 0
    while i < end:
        if data[i] == 0x5B and i + 1 < end and data[i + 1] in (0x80, 0x81, 0x82, 0x86, 0x87):
            break
        name = data[i:i + 4]
        if len(name) < 4 or not is_nameseg(name):
            break
        val, n = pkg_len(data, i + 4)
        if val is None:
            break
        i += 4 + n
        if val == 0:
            # reserved field -> next is Offset(Integer)
            v, k = read_integer(data, i)
            if v is None:
                break
            i += k
            if v % 8 and False:
                pass
            bitpos = v * 8
            out.append((name.decode("ascii", "replace"), v, 0, 0, "offset"))
            continue
        out.append((name.decode("ascii", "replace"), bitpos // 8, bitpos % 8, val, "field"))
        bitpos += val
    return out, i

# ---------- 1. sniff ----------
print("== header sniff ==")
for fn in sorted(glob.glob(os.path.join(DIR, "*.bin")))[:3]:
    d = open(fn, "rb").read(64)
    print("  %-46s %s" % (os.path.basename(fn), d[:8].hex(" ")))
print()

files = sorted(glob.glob(os.path.join(DIR, "*.bin")))

# ---------- 2. EmbeddedControl regions ----------
ec_regions = []   # (file, region_name, off)
print("== OperationRegion ... EmbeddedControl ==")
for fn in files:
    data = open(fn, "rb").read()
    i = 0
    while True:
        j = data.find(b"\x5b\x80", i)
        if j < 0:
            break
        i = j + 2
        nm = data[j + 2:j + 6]
        if len(nm) < 6:
            continue
        space = data[j + 6]
        if space == 0x03:
            v, n = pkg_len(data, j + 7)
            off_obj, k1 = read_integer(data, j + 7 + n)
            len_obj, k2 = read_integer(data, j + 7 + n + k1)
            ec_regions.append((os.path.basename(fn), nm.decode("ascii", "replace"), off_obj, len_obj))
            print("  %-42s region=%-5s kind=0x%02X offset=%s len=%s"
                  % (os.path.basename(fn), nm.decode("ascii", "replace"), space, off_obj, len_obj))
if not ec_regions:
    print("  (none found by strict walk; falling back to string search below)")
    for fn in files:
        data = open(fn, "rb").read()
        for m in re.finditer(rb"EmbeddedControl", data):
            print("  %-42s literal 'EmbeddedControl' @0x%X  before=%s"
                  % (os.path.basename(fn), m.start(),
                     data[m.start() - 12:m.start()].hex(" ")))
print()

# ---------- 3. Field lists bound to EmbeddedControl regions ----------
print("== Field lists -> EC RAM map ==")
any_field = False
for fn in files:
    data = open(fn, "rb").read()
    i = 0
    while True:
        j = data.find(b"\x5b\x81", i)
        if j < 0:
            break
        i = j + 2
        fname = data[j + 2:j + 6]
        rname = data[j + 6:j + 10]
        if len(rname) < 4:
            continue
        if not any(r[1] == rname.decode("ascii", "replace") for r in ec_regions):
            continue
        flags = data[j + 10]
        fields, _ = parse_field_list(data, j + 11, min(len(data), j + 11 + 6000))
        if not fields:
            continue
        any_field = True
        print("-- %s  field=%s  region=%s  flags=0x%02X  (%d entries)"
              % (os.path.basename(fn), fname.decode("ascii", "replace"),
                 rname.decode("ascii", "replace"), flags, len(fields)))
        for name, bo, bb, w, kind in fields:
            if kind == "offset":
                print("     ----  Offset -> byte 0x%02X (%d)" % (bo, bo))
            else:
                print("     0x%02X.%d  %-5s  width=%d bit" % (bo, bb, name, w))
        print()
if not any_field:
    print("  (no Field found referencing those regions)")
print()

# ---------- 4. name survey ----------
print("== name survey across all tables ==")
def names_in(data):
    s = set()
    for m in re.finditer(rb"[A-Z_][A-Z0-9_]{3}", data):
        s.add(m.group(0).decode("ascii"))
    return s

per_file = {os.path.basename(f): names_in(open(f, "rb").read()) for f in files}
allnames = set()
for v in per_file.values():
    allnames |= v

q = sorted(n for n in allnames if n.startswith("_Q"))
print("  _Qxx methods present (%d): %s" % (len(q), " ".join(q)))
for key in ("_LID", "VPCR", "VPCW", "EC0", "VPC0", "LID0", "GBMD", "HALS", "DYTC", "FAN0", "_Q15", "_Q04"):
    hit = [f for f, s in per_file.items() if key in s]
    print("  %-6s in %d table(s): %s" % (key, len(hit), ", ".join(hit[:4]) + (" ..." if len(hit) > 4 else "")))
print()
print("  literal 'PNP0C0D' files:", [f for f in files if b"PNP0C0D" in open(f, "rb").read()])
