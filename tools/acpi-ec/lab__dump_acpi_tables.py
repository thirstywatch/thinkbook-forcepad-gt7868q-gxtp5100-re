#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dump_acpi_tables.py -- 从注册表 HKLM\\HARDWARE\\ACPI 导出全部 ACPI 表原始字节。
只读，不写注册表。ACPI 表在 HKLM\\HARDWARE 下，普通用户可读。

布局（实测本机）：
  HKLM\\HARDWARE\\ACPI\\<SIG>\\<OEMID>\\<OEMTABLEID>\\<REV>  ->  值名 "00000000" = REG_BINARY 表数据
"""
import os, sys, json

try:
    import winreg
except ImportError:
    print("this script must run on Windows"); sys.exit(1)

OUT = sys.argv[1] if len(sys.argv) > 1 else 'acpi_raw'

def walk(root, path=()):
    out = []
    try:
        with winreg.OpenKey(root, '') as k:
            names = []
            i = 0
            while True:
                try:
                    names.append(winreg.EnumKey(k, i)); i += 1
                except OSError:
                    break
            vals = []
            j = 0
            while True:
                try:
                    n, v, t = winreg.EnumValue(k, j); vals.append((n, v, t)); j += 1
                except OSError:
                    break
            if vals:
                out.append((root, path, vals))
            for n in names:
                try:
                    with winreg.OpenKey(root, n) as sub:
                        out.extend(walk(sub, path + (n,)))
                except OSError:
                    pass
    except OSError as e:
        print("  open fail %s: %s" % (path, e))
    return out

os.makedirs(OUT, exist_ok=True)
summary = []
for sig in ('DSDT', 'SSDT'):
    try:
        base = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\ACPI\%s' % sig)
    except OSError as e:
        print("no %s: %s" % (sig, e)); continue
    for key, path, vals in walk(base, (sig,)):
        for (vn, v, vt) in vals:
            if not isinstance(v, (bytes, bytearray)):
                continue
            if len(v) < 36:
                continue
            tbl_sig = bytes(v[0:4]).decode('ascii', 'replace')
            oemid   = bytes(v[10:16]).decode('ascii', 'replace').strip()
            oemtid  = bytes(v[16:24]).decode('ascii', 'replace').strip()
            fname = '%s_%s_%s_%s.bin' % (tbl_sig, oemid or 'x', oemtid or 'x', (path[-1] if path else '0'))
            fname = ''.join(c if (c.isalnum() or c in '._-') else '_' for c in fname)
            fp = os.path.join(OUT, fname)
            with open(fp, 'wb') as f:
                f.write(bytes(v))
            summary.append(dict(sig=tbl_sig, oemid=oemid, oemtableid=oemtid,
                                size=len(v), file=fname, regpath=('\\'.join(path))))
            print("  %-6s %-8s %-10s %8d  -> %s" % (tbl_sig, oemid, oemtid, len(v), fname))
with open(os.path.join(OUT, '_summary.json'), 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print("total tables = %d" % len(summary))
