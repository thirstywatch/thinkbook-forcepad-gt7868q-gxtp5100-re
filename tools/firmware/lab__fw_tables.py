# fw_tables.py - dump the three table pointers' targets and try to parse them as HID descriptors
import struct

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
def foff(a): return VOFF + (a - BASE)
def dump(a, n=96):
    off = foff(a & ~1)
    if off < 0 or off >= len(data):
        print('  0x%08X out of range' % a); return
    b = data[off:off+n]
    print('\n--- data @0x%08X (file 0x%X), %d bytes ---' % (a & ~1, off, len(b)))
    for i in range(0, len(b), 16):
        row = b[i:i+16]
        print('   %04X  %-47s  %s' % (i, ' '.join('%02X' % x for x in row),
              ''.join(chr(x) if 32 <= x < 127 else '.' for x in row)))

for a in (0x0800DB38, 0x0800DB5C, 0x0800DADC, 0x0800DEE8, 0x0800D628):
    dump(a, 96)

# HID report-descriptor item walker
def walk(a, limit=2000):
    off = foff(a & ~1)
    print('\n=== HID descriptor attempt @0x%08X ===' % (a & ~1))
    i = 0
    depth = 0
    while i < limit and off + i < len(data):
        b = data[off + i]
        if b == 0xFE:   # long item
            sz = data[off+i+1]
            print('   %04X LONG tag=0x%02X size=%d' % (i, data[off+i+2], sz))
            i += 3 + sz
            continue
        size = {0:0, 1:1, 2:2, 3:4}[b & 3]
        typ = (b >> 2) & 3
        tag = (b >> 4) & 0xF
        val = 0
        for k in range(size):
            val |= data[off+i+1+k] << (8*k)
        tname = {0:'MAIN', 1:'GLOBAL', 2:'LOCAL', 3:'RESERVED'}[typ]
        if typ == 0 and tag == 8:      # Input
            pass
        if typ == 0 and tag == 12:     # End Collection
            depth -= 1
        desc = ''
        if typ == 1 and tag == 0: desc = 'UsagePage=0x%04X' % val
        elif typ == 1 and tag == 1: desc = 'LogicalMin=%d' % val
        elif typ == 1 and tag == 2: desc = 'LogicalMax=%d' % val
        elif typ == 1 and tag == 7: desc = 'ReportSize=%d' % val
        elif typ == 1 and tag == 8: desc = 'ReportID=%d' % val
        elif typ == 1 and tag == 9: desc = 'ReportCount=%d' % val
        elif typ == 2 and tag == 0: desc = 'Usage=0x%04X' % val
        elif typ == 2 and tag == 1: desc = 'UsageMin=0x%04X' % val
        elif typ == 2 and tag == 2: desc = 'UsageMax=0x%04X' % val
        elif typ == 0 and tag == 10: desc = 'Collection(type=%d)' % val
        print('   %04X  %-10s tag=%X size=%d  %s' % (i, tname, tag, size, desc))
        if typ == 0 and tag == 10:
            depth += 1
        i += 1 + size
        if depth <= 0 and i > 4:
            print('   (collection depth back to 0 at %04X - looks like a complete descriptor)' % i)
            break
        if i > 400:
            print('   (stopping: not descriptor-like)')
            break

walk(0x0800DB38)
walk(0x0800DADC)
