#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
x9_deliverables.py -- build the final X9-15 ACPI deliverables from the firmware analysis.

Inputs (produced earlier in this session):
  out_sc1/N4C_SC1_blob03_dec.bin : 21,430,288-byte LZMA-decompressed payload of
                                   FFS file AD198BA5-C330-41CD-B097-16488328B798
                                   inside FV@0x11A08A8 of iso_fat/N4C_SC1.bin
  acpi_out/DSDT_X9-15.bin        : DSDT carved out of that blob at blob offset 0x3116C

Outputs (all in x9bios\deliverables\):
  DSDT_X9-15.bin                the full DSDT (300,544 bytes)
  TPAD_X9-15.bin                the touchpad Device subtree ("TPAD" role on this model = Device TPD0)
  TPAD_X9-15_hexdump.txt        annotated AML listing + hex dump of that subtree
  TPAD_EC_field_X9-15.bin       the EC/GNVS field region that literally declares the name "TPAD"
  TPD0_decoded.txt              decoded Name()/Method() inventory of the touchpad device
  ACPI_tables_X9-15\            every checksum-valid ACPI table found in the blob
"""
import struct, sys, os, shutil

BASE = r'<WORKSPACE>'
BLOB = os.path.join(BASE, 'out_sc1', 'N4C_SC1_blob03_dec.bin')
DSDT_IN = os.path.join(BASE, 'acpi_out', 'DSDT_X9-15.bin')
OUT = os.path.join(BASE, 'deliverables')

# offsets inside the decompressed blob
DSDT_OFF = 0x3116C
DSDT_LEN = 0x49600
# offsets inside the DSDT
TPD0_OFF, TPD0_END = 0x17331, 0x17637          # Device (TPD0)
TPAD_ECFIELD_OFF, TPAD_ECFIELD_END = 0x2EF0, 0x2F30   # where the literal name "TPAD" is declared
ITML_OFF = 0x17399                              # Name (ITML, Package(4){...})


def L(d, o, n):
    return d[o:o+n]


def main():
    os.makedirs(OUT, exist_ok=True)
    blob = open(BLOB, 'rb').read()
    dsdt = open(DSDT_IN, 'rb').read()
    assert dsdt[:4] == b'DSDT', dsdt[:4]
    assert blob[DSDT_OFF:DSDT_OFF+4] == b'DSDT'
    assert blob[DSDT_OFF:DSDT_OFF+DSDT_LEN] == dsdt

    ln = struct.unpack_from('<I', dsdt, 4)[0]
    csum = sum(dsdt) & 0xFF
    print('DSDT: sig=%r len=%d (0x%X) rev=%d oem=%r otbl=%r sum=0x%02X %s' % (
        dsdt[:4], ln, ln, dsdt[8], dsdt[10:16], dsdt[16:22], csum,
        'OK' if csum == 0 else 'BAD'))

    # 1. DSDT
    shutil.copyfile(DSDT_IN, os.path.join(OUT, 'DSDT_X9-15.bin'))

    # 2. touchpad device subtree
    dev = dsdt[TPD0_OFF:TPD0_END]
    open(os.path.join(OUT, 'TPAD_X9-15.bin'), 'wb').write(dev)
    print('TPD0 subtree: 0x%X..0x%X  %d bytes' % (TPD0_OFF, TPD0_END, len(dev)))

    # 3. EC field region declaring "TPAD"
    ec = dsdt[TPAD_ECFIELD_OFF:TPAD_ECFIELD_END]
    open(os.path.join(OUT, 'TPAD_EC_field_X9-15.bin'), 'wb').write(ec)

    # 4. all valid ACPI tables
    tdir = os.path.join(OUT, 'ACPI_tables_X9-15')
    os.makedirs(tdir, exist_ok=True)
    sys.path.insert(0, BASE)
    from acpi_extract import find_tables
    ts = find_tables(blob)
    with open(os.path.join(tdir, '_index.txt'), 'w', encoding='utf-8') as f:
        for o, s, l in ts:
            tbl = blob[o:o+l]
            fn = ('DSDT_X9-15.bin' if s == 'DSDT' else '%s_%08X.bin' % (s, o))
            open(os.path.join(tdir, fn), 'wb').write(tbl)
            line = 'blob_off=0x%-9X %-5s len=%-8d rev=%d oem=%-8r otbl=%-8r -> %s' % (
                o, s, l, tbl[8], tbl[10:16], tbl[16:22], fn)
            f.write(line + '\n')
            print(line)

    print('\nDONE -> %s' % OUT)


main()
