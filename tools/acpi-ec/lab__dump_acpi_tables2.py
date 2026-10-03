#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dump_acpi_tables2.py -- 导出 HKLM\\HARDWARE\\ACPI 下【所有平级表键】。
实测本机布局：
  HKLM\\HARDWARE\\ACPI\\
      DSDT | SSDT            <- 主表键
      SSD1 .. SSDS, SSDT ... <- 每键一张独立表（顶层平级，不是 SSDT 的子键！）
  表键 -> OEMID -> OEMTABLEID -> REV -> 值名 "00000000" = REG_BINARY
只读。
"""
import os, sys, json, winreg

ROOT = r'HARDWARE\ACPI'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'acpi_raw'

def subkeys(hive, path):
    out = []
    try:
        with winreg.OpenKey(hive, path) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumKey(k, i)); i += 1
                except OSError:
                    break
    except OSError:
        pass
    return out

def values(hive, path):
    out = []
    try:
        with winreg.OpenKey(hive, path) as k:
            j = 0
            while True:
                try:
                    n, v, t = winreg.EnumValue(k, j); out.append((n, v, t)); j += 1
                except OSError:
                    break
    except OSError:
        pass
    return out

os.makedirs(OUT, exist_ok=True)
found = []
for top in subkeys(winreg.HKEY_LOCAL_MACHINE, ROOT):
    base = ROOT + '\\' + top
    # 该表键下 -> OEMID
    for oem in subkeys(winreg.HKEY_LOCAL_MACHINE, base):
        for tid in subkeys(winreg.HKEY_LOCAL_MACHINE, base + '\\' + oem):
            for rev in subkeys(winreg.HKEY_LOCAL_MACHINE, base + '\\' + oem + '\\' + tid):
                p = '%s\\%s\\%s\\%s' % (base, oem, tid, rev)
                for (vn, v, vt) in values(winreg.HKEY_LOCAL_MACHINE, p):
                    if not isinstance(v, (bytes, bytearray)) or len(v) < 36:
                        continue
                    sig = bytes(v[0:4]).decode('ascii', 'replace')
                    oemid = bytes(v[10:16]).decode('ascii', 'replace').strip()
                    oemtid = bytes(v[16:24]).decode('ascii', 'replace').strip()
                    fname = '%s_%s_%s_%s.bin' % (sig, oemid or 'x', oemtid or 'x', top)
                    fname = ''.join(c if (c.isalnum() or c in '._-') else '_' for c in fname)
                    with open(os.path.join(OUT, fname), 'wb') as f:
                        f.write(bytes(v))
                    found.append(dict(key=top, oemid=oemid, oemtableid=oemtid,
                                      sig=sig, size=len(v), file=fname))
                    print("  %-6s %-6s %-10s %-10s %8d  -> %s" % (top, sig, oemid, oemtid, len(v), fname))

with open(os.path.join(OUT, '_summary.json'), 'w', encoding='utf-8') as f:
    json.dump(found, f, ensure_ascii=False, indent=2)
print("total tables = %d, bytes = %d" % (len(found), sum(x['size'] for x in found)))
