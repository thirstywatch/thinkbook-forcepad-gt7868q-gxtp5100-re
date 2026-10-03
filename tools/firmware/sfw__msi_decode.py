#!/usr/bin/env python3
"""Decode the MSI's raw table streams using its own string pool.

7-Zip exposes the compound-file streams (!File, !Media, ...) and the string
pool (!_StringPool / !_StringData) but not the decoded rows, and the
WindowsInstaller COM classes have no registered typelib here, so the rows are
decoded directly:

  !_StringPool  per-string (codepage|refcount) + u16 length; a length with the
                high bit set continues in the next u16
  !_StringData  the concatenated string bytes
  !<Table>      rows of u16 string indices / u32 integers, laid out per the
                column list in !_Columns

Media.File_ lists cabinet members in storage order, which is what maps a File
row to its cabinet and sequence position.
"""
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAB = HERE / "tables"


CODEPAGES = {0: "cp1252", 1: "cp1250", 2: "cp1251", 3: "cp1252", 4: "cp1253",
             5: "cp1254", 6: "cp1255", 7: "cp1256", 8: "cp1257", 9: "cp1258",
             100: "utf-8", 65001: "utf-8"}


def load_pool():
    """Decode !_StringPool + !_StringData into {string_id: text}.

    Layout: the first u16 pair is the codepage, then one (length, refcount) u16
    pair per string. String ids are 1-based over the pairs after the codepage,
    and the concatenated bytes live in !_StringData in that same order. When a
    length has bit 15 set the real length continues in the next pair's u16.
    """
    pool = (TAB / "!_StringPool").read_bytes()
    data = (TAB / "!_StringData").read_bytes()
    codepage = CODEPAGES.get(struct.unpack_from("<H", pool, 0)[0], "cp1252")
    pairs = [struct.unpack_from("<HH", pool, i) for i in range(4, len(pool), 4)]

    strings, first = {}, 0
    for i, (length, _refcount) in enumerate(pairs, start=1):
        if length & 0x8000:  # long string: 15 bits here, rest in the next u16
            nxt = pairs[i][0] if i < len(pairs) else 0
            length = (length & 0x7FFF) | ((nxt & 0x7FFF) << 15)
        strings[i] = data[first:first + length].decode(codepage, "replace")
        first += length
    return strings, codepage, len(pairs)


def load_columns():
    raw = (TAB / "!_Columns").read_bytes()
    vals = struct.unpack(f"<{len(raw)//2}H", raw)
    return vals


def read_rows(table, strings, ncols):
    p = TAB / f"!{table}"
    if not p.exists():
        return []
    raw = p.read_bytes()
    rows, pos = [], 0
    while pos + 2 * ncols <= len(raw):
        row = []
        for _ in range(ncols):
            row.append(strings.get(struct.unpack_from("<H", raw, pos)[0], ""))
            pos += 2
        rows.append(row)
    return rows


def main():
    strings, codepage, npool = load_pool()
    cols = load_columns()
    # !_Tables holds string-pool indices, so decode it through the pool.
    raw = (TAB / "!_Tables").read_bytes()
    idx = struct.unpack(f"<{len(raw)//2}H", raw)
    tables = [strings.get(i, f"?{i}") for i in idx]
    print(f"codepage={codepage} strings={npool} columns={len(cols)} tables={len(tables)}")
    print("tables:", tables)

    # !_Columns holds one entry per table column, encoded as
    # (slot << 8) | column_number. Slot 0 is the persistent (always-present)
    # set; transient table slots are numbered from 128 and are matched to names
    # by their position in !_Tables.
    per = {}
    for v in cols:
        t, c = v >> 8, v & 0xFF
        per[t] = max(per.get(t, 0), c + 1)
    print(f"column slots: {sorted(per)}")

    # !_Tables lists transient table names; slot 128+i is the i-th entry.
    named = {name: 128 + i for i, name in enumerate(tables)}
    # Sanity: a slot's column count must fit its stream length.
    for name, slot in named.items():
        if slot not in per:
            continue
        p = TAB / f"!{name}"
        if p.exists():
            rows = len(p.read_bytes()) // (2 * per[slot])
            print(f"  {name:<24} slot={slot} cols={per[slot]} rows={rows}")

    result = {}
    for name in ("File", "Media", "Component", "Directory"):
        slot = named.get(name)
        if slot is None or slot not in per:
            print(f"  !! {name} not found (slot={slot})")
            continue
        rows = read_rows(name, strings, per[slot])
        result[name] = rows
        print(f"  {name}: {len(rows)} rows x {per[slot]} cols")

    (HERE / "msi_tables.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    for name in result:
        print(f"\n-- {name} sample --")
        for r in result[name][:4]:
            print("  ", r)
    if "File" in result:
        print("\n-- File rows mentioning firmware --")
        for r in result["File"]:
            n = r[2].lower() if len(r) > 2 else ""
            if any(k in n for k in ("sam", "touchpad", "ecfirm", "haptic")):
                print("  *", r)


if __name__ == "__main__":
    main()
