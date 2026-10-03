#!/usr/bin/env python3
"""ecram_diff.py -- compare 2+ 4KB EC-RAM snapshots and annotate every differing byte
with the ACPI field name it belongs to.

Why: the EC RAM of this machine is memory-mapped at physical 0xFE0B0400 (0x1000 bytes).
Read it, move the lid slightly, read again, then run this script.

Usage:
    python ecram_diff.py ec-A.bin ec-B.bin [ec-C.bin ...]

Snapshots must be exactly 4096 bytes (the ECMM window length).
Produced for ThinkBook 14 G6+ IMH (21LD), BIOS NJCN67WW, DSDT LENOVO CB-01.
"""
import sys

SIZE = 0x1000

# (byte offset, field name, bit position inside byte, width in bits) -- from Field(ECMM)
FIELDS = [
    (0x002, "LESR", 0, 1), (0x002, "LSRN", 1, 1),
    (0x0E4, "EST4", 0, 8), (0x0E5, "EST3", 0, 8), (0x0E6, "EST5", 0, 8),
    (0x0E7, "EST1", 0, 8), (0x0E8, "EST6", 0, 8), (0x0E9, "EST2", 0, 8),
    (0x0EA, "WLIS", 3, 1), (0x0EA, "APSB", 6, 1), (0x0EA, "TCAD", 7, 1),
    (0x52B, "ERIB", 0, 16), (0x52F, "SMST", 0, 8), (0x530, "SMAD", 0, 8),
    (0x531, "SMCM", 0, 8), (0x532, "SMD0(512B)", 0, 4096),
    (0x732, "BCNT", 0, 8), (0x733, "SMAA", 0, 24), (0x736, "SMBN", 0, 8),
    (0x73B, "SUPL", 0, 8), (0x73C, "SPPT", 0, 8), (0x73D, "FPPT", 0, 8),
    (0x83E, "EECF", 0, 1),
    (0x83F, "SGMT", 0, 1), (0x83F, "VIDO", 1, 1), (0x83F, "TOUP", 2, 1),
    (0x83F, "SPMT", 3, 1), (0x83F, "MCMT", 4, 1),
    (0x840, "ODTS", 0, 8), (0x841, "OSTY", 0, 4), (0x841, "PBOV", 5, 1),
    (0x841, "ECRD", 6, 1), (0x841, "ADPT", 7, 1),
    (0x842, "PWAK", 0, 1), (0x842, "MWAK", 1, 1), (0x842, "LWAK", 2, 1),
    (0x842, "RWAK", 3, 1), (0x842, "WWAK", 4, 1), (0x842, "UWAK", 5, 1),
    (0x842, "KWAK", 6, 1), (0x842, "TWAK", 7, 1),
    (0x843, "CCAC", 0, 1), (0x843, "AOAC", 1, 1), (0x843, "BLAC", 2, 1),
    (0x843, "PSRC", 3, 1), (0x843, "BOAC", 4, 1), (0x843, "LCAC", 5, 1),
    (0x843, "AAAC", 6, 1), (0x843, "ACAC", 7, 1),
    (0x844, "S3ST", 0, 1), (0x844, "S3RM", 1, 1), (0x844, "S4ST", 2, 1),
    (0x844, "S4RM", 3, 1), (0x844, "S5ST", 4, 1), (0x844, "S5RM", 5, 1),
    (0x844, "CSST", 6, 1), (0x844, "CSRM", 7, 1),
    (0x845, "CATT", 0, 8), (0x846, "VATT", 0, 8), (0x847, "THLT", 0, 8),
    (0x848, "TCNL", 0, 8),
    (0x849, "MODE", 0, 1), (0x849, "INIT", 3, 1), (0x849, "FAEN", 4, 1),
    (0x84A, "SDTM", 0, 8), (0x84B, "FSSN", 0, 4), (0x84B, "FANU", 4, 4),
    (0x84C, "PCVL", 0, 6), (0x84C, "SWTO", 6, 1), (0x84C, "TTHR", 7, 1),
    (0x84D, "TTHM", 0, 1), (0x84D, "THTL", 1, 1), (0x84D, "TFCT", 2, 1),
    (0x84D, "NPST", 3, 5),
    (0x84E, "CTMP", 0, 8), (0x84F, "CTML", 0, 8),
    (0x851, "SKTB", 0, 8), (0x852, "SKTC", 0, 8), (0x853, "DPOT", 0, 8),
    (0x856, "**LIDF**", 1, 1), (0x856, "PMEE", 2, 1), (0x856, "PWBE", 3, 1),
    (0x856, "RNGE", 4, 1), (0x856, "BTWE", 5, 1),
    (0x857, "BRTS", 0, 8),
    (0x858, "S35M", 0, 1), (0x858, "S35S", 1, 1), (0x858, "MSFG", 3, 1),
    (0x858, "FFEN", 4, 1), (0x858, "FFST", 5, 1),
    (0x859, "WLAT", 0, 1), (0x859, "BTAT", 1, 1), (0x859, "WLEX", 2, 1),
    (0x859, "BTEX", 3, 1), (0x859, "KLSW", 4, 1), (0x859, "WLOK", 5, 1),
    (0x859, "AT3G", 6, 1), (0x859, "EX3G", 7, 1),
    (0x85A, "PJID", 0, 8), (0x85B, "CPUJ", 0, 3), (0x85B, "CPNM", 3, 3),
    (0x85B, "GATY", 6, 2),
    (0x85E, "BTY0", 0, 1), (0x85E, "BAM0", 1, 1), (0x85F, "BST0", 0, 8),
    (0x860, "BRC0", 0, 16), (0x864, "BPV0", 0, 16), (0x866, "BDV0", 0, 16),
    (0x868, "BDC0", 0, 16), (0x86A, "BFC0", 0, 16), (0x86C, "GAU0", 0, 8),
    (0x86D, "BAT0", 0, 8), (0x86E, "BPC0", 0, 16), (0x870, "BAC0", 0, 16),
    (0x872, "BCG0", 0, 16), (0x874, "BFCB", 0, 16), (0x876, "BTPB", 0, 16),
    (0x878, "BOL0", 0, 1), (0x878, "BFS0", 1, 1), (0x879, "ORRF", 0, 1),
]


def who(off):
    """Return field names covering byte `off`."""
    out = []
    for base, name, bitpos, width in FIELDS:
        b0 = base + (bitpos // 8)
        b1 = base + (bitpos + width - 1) // 8
        if b0 <= off <= b1:
            out.append(name)
    return out


def load(path):
    """Accept EITHER a raw 4096-byte .bin OR a text hex dump (RWEverything / hex editor paste)."""
    raw = open(path, "rb").read()

    # --- raw binary? ---
    if len(raw) >= SIZE and not is_texty(raw):
        return raw[:SIZE]

    # --- text hex dump ---
    txt = raw.decode("utf-8", "replace")
    out = bytearray()
    for line in txt.splitlines():
        toks = line.split()
        if not toks:
            continue
        # drop a leading address column (e.g. FE0B0400 or 0xFE0B0400:)
        if len(toks[0]) >= 6 and all(c in "0123456789abcdefABCDEFxX:" for c in toks[0]):
            toks = toks[1:]
        got = 0
        for t in toks:
            t = t.strip(",;")
            if len(t) == 2 and all(c in "0123456789abcdefABCDEF" for c in t):
                out.append(int(t, 16))
                got += 1
            elif got:
                break          # probably hit the ASCII column
        if got:
            pass
    if len(out) < SIZE:
        sys.exit("%s: parsed only %d bytes from the hex dump (need %d).\n"
                 "       Check that the dump covers FE0B0400..FE0B13FF." % (path, len(out), SIZE))
    return bytes(out[:SIZE])


def is_texty(b):
    """Heuristic: mostly printable ASCII -> it is a text dump."""
    sample = b[:4096]
    printable = sum(1 for c in sample if 9 <= c <= 13 or 32 <= c < 127)
    return printable / max(1, len(sample)) > 0.95


def main():
    paths = sys.argv[1:]
    if len(paths) < 2:
        sys.exit(__doc__)
    snaps = [(p, load(p)) for p in paths]

    print("EC RAM window 0xFE0B0400, %d bytes, %d snapshots" % (SIZE, len(snaps)))
    for p, _ in snaps:
        print("   %s" % p)
    print()

    # which offsets ever differ from snapshot[0]
    varying = []
    base = snaps[0][1]
    for off in range(SIZE):
        vals = [s[1][off] for s in snaps]
        if len(set(vals)) > 1:
            varying.append((off, vals))

    print("== differing bytes: %d of %d ==" % (len(varying), SIZE))
    if not varying:
        print("   NONE -- all snapshots identical.")
        return
    print("   off    " + "  ".join("%-8s" % p.split("/")[-1][:8] for p, _ in snaps) + "  fields")
    for off, vals in varying:
        names = who(off)
        zeros = [v for v in vals if v == 0]
        tag = ""
        if names and "**LIDF**" in names:
            tag = "   <-- LIDF byte"
        print("   0x%03X  " % off + "  ".join("%-8s" % ("0x%02X" % v) for v in vals)
              + "  " + (", ".join(names) if names else "(unnamed)") + tag)
    print()

    # heuristic verdict
    named = [(o, v) for o, v in varying if who(o)]
    unnamed = [(o, v) for o, v in varying if not who(o)]
    print("== verdict hints ==")
    print("   differing in NAMED fields   : %d" % len(named))
    print("   differing in UNNAMED bytes  : %d  %s" % (
        len(unnamed), ", ".join("0x%03X" % o for o, _ in unnamed[:16])))
    print()
    print("   if the ONLY changing thing is 0x856 -> the lid is a plain binary flag,")
    print("   and this machine has no lid-angle value anywhere. Case closed.")
    print("   if an UNNAMED byte tracks the screen movement in experiment B but not A/C,")
    print("   that offset is your angle. Report it.")


if __name__ == "__main__":
    main()
