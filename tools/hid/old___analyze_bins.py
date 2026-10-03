# -*- coding: utf-8 -*-
# READ-ONLY binary analysis of previously captured HID feature .bin files.
# Touches NO HID device: only reads local files.
import hashlib, os, sys, json
import numpy as np

D = r'<WORKSPACE>'
P = os.path.join

TARGETS = [
    'col02_feature_rid2_full.bin',
    'col02_feature_rid9_full.bin',
    'col02_feature_256B.bin',
    'col02_feat_rid2.bin',
    'col02_feat_rid9.bin',
]
# extra context files from the later "precise" run
PRECISE = ['rid02_len2.bin','rid02_len257.bin','rid02_len737.bin','rid06_len257.bin',
           'rid06_len737.bin','rid07_len257.bin','rid07_len737.bin','rid09_len257.bin',
           'rid09_len737.bin','rid11_len257.bin','rid11_len737.bin','rid12_len737.bin',
           'rid13_len257.bin','rid13_len737.bin']

def md5(b): return hashlib.md5(b).hexdigest()
def sha(b): return hashlib.sha256(b).hexdigest()[:16]

def hexdump(b, start=0, n=None, width=16):
    if n is None: n = len(b)
    out = []
    for off in range(start, min(start+n, len(b)), width):
        chunk = b[off:off+width]
        hx = ' '.join('%02X' % x for x in chunk)
        asc = ''.join(chr(x) if 32 <= x < 127 else '.' for x in chunk)
        out.append('%04X  %-*s  |%s|' % (off, width*3-1, hx, asc))
    return '\n'.join(out)

report = []
def say(s=''):
    report.append(str(s))

say('='*100)
say('SECTION 0: identity of the 5 target files')
say('='*100)
blobs = {}
for t in TARGETS:
    p = P(D, t)
    b = open(p,'rb').read()
    blobs[t] = b
    say('%-30s len=%4d md5=%s sha256_16=%s' % (t, len(b), md5(b), sha(b)))
    say('  first 32 bytes : ' + ' '.join('%02X'%x for x in b[:32]))
    say('  last  32 bytes : ' + ' '.join('%02X'%x for x in b[-32:]))
    vals, cnts = np.unique(np.frombuffer(b, dtype=np.uint8), return_counts=True)
    top = sorted(zip(cnts.tolist(), vals.tolist()), reverse=True)[:6]
    say('  n_distinct_bytes=%d  top bytes: %s' % (len(vals),
        ', '.join('0x%02X x%d' % (v,c) for c,v in top)))
    say('')

say('='*100)
say('SECTION 1: full hexdump of the short files (8 B each)')
say('='*100)
for t in ['col02_feat_rid2.bin','col02_feat_rid9.bin']:
    say(t)
    say(hexdump(blobs[t]))
    say('')

say('='*100)
say('SECTION 2: 737 B pair -- byte-by-byte diff')
say('='*100)
a = blobs['col02_feature_rid2_full.bin']
b = blobs['col02_feature_rid9_full.bin']
say('len(a)=%d len(b)=%d  a==b ? %s' % (len(a), len(b), a == b))
say('md5 equal ? %s' % (md5(a) == md5(b)))
diffs = [(i, a[i], b[i]) for i in range(min(len(a),len(b))) if a[i] != b[i]]
say('number of differing byte positions: %d' % len(diffs))
for i, x, y in diffs[:200]:
    say('  off %d (0x%X): a=0x%02X b=0x%02X  delta=%+d' % (i, i, x, y, y-x))
if not diffs:
    say('  -> files are byte-identical (no differing position at all)')

say('')
say('='*100)
say('SECTION 3: 256 B file vs the 737 B files')
say('='*100)
c = blobs['col02_feature_256B.bin']
say('256B head32 : ' + ' '.join('%02X'%x for x in c[:32]))
say('256B md5=%s' % md5(c))
for name, big in [('rid2_full', a), ('rid9_full', b)]:
    # is c a contiguous substring of big?
    locs = []
    st = 0
    while True:
        i = big.find(c, st)
        if i < 0: break
        locs.append(i); st = i+1
    prefix_ok = big[:len(c)] == c
    say('%-10s : exact-substring occurrences = %s ; prefix(0..255) identical = %s'
        % (name, locs if locs else 'NONE', prefix_ok))
    # also: how many of the 256 bytes match at the same offsets
    n = min(len(c), len(big))
    same = sum(1 for i in range(n) if c[i] == big[i])
    say('%-10s : same-offset match count = %d / %d' % (name, same, n))
    for i in range(n):
        if c[i] != big[i]:
            say('%-10s : first same-offset mismatch at off 0x%X (%d): 256B=0x%02X big=0x%02X'
                % (name, i, i, c[i], big[i]))
            break

say('')
say('='*100)
say('SECTION 4: first byte / report-ID hypothesis')
say('='*100)
for t in TARGETS:
    bb = blobs[t]
    say('%-30s first byte = 0x%02X (%d)' % (t, bb[0], bb[0]))
say('')
say('737 = 1 + 736 ?  -> %s ; 257 = 1 + 256 ? -> %s' % (737 == 738-1, True))

say('')
say('='*100)
say('SECTION 5: context from the later precise-read run (same directory)')
say('='*100)
pj = P(D, 'col02-precise')
prec = {}
for f in PRECISE:
    p = P(pj, f)
    if os.path.exists(p):
        bb = open(p,'rb').read()
        prec[f] = bb
        say('%-20s len=%4d md5=%s  head16=%s' % (f, len(bb), md5(bb),
            ' '.join('%02X'%x for x in bb[:16])))
say('')
# does the 737B rid2_full equal the precise rid02_len737?
for f in ['rid02_len737.bin','rid09_len737.bin','rid12_len737.bin','rid06_len737.bin','rid02_len257.bin']:
    if f in prec:
        for t in ['col02_feature_rid2_full.bin','col02_feature_rid9_full.bin','col02_feature_256B.bin']:
            same = prec[f] == blobs[t]
            say('%s == %-30s ? %s' % (f, t, same))
say('')
# tail fill analysis for rid02 files
for f in ['rid02_len2.bin','rid02_len257.bin','rid02_len737.bin']:
    if f in prec:
        bb = prec[f]
        eff = 2
        say('%s: eff bytes = %s ; bytes[2:] all 0xEE ? %s ; value at [0xEE] count=%d'
            % (f, ' '.join('%02X'%x for x in bb[:eff]),
               all(x == 0xEE for x in bb[eff:]), sum(1 for x in bb if x == 0xEE)))
for f in ['rid06_len737.bin','rid09_len737.bin','rid12_len737.bin','rid11_len737.bin','rid13_len737.bin']:
    if f in prec:
        bb = prec[f]
        say('%s: eff first 211 bytes md5=%s ; bytes[211:] all 0xEE ? %s'
            % (f, md5(bb[:211]), all(x == 0xEE for x in bb[211:])))

say('')
say('='*100)
say('SECTION 6: hexdump of 737 B payload region (rows 0x00-0x200)')
say('='*100)
say('--- col02_feature_rid2_full.bin ---')
say(hexdump(a, 0, 0x200))
say('')
say('--- col02_feature_rid9_full.bin ---')
say(hexdump(b, 0, 0x200))
say('')
say('--- col02_feature_256B.bin (full) ---')
say(hexdump(c))
say('')
say('--- 737B rid2_full, region 0x200..0x2E1 ---')
say(hexdump(a, 0x200))

open(P(D, '_report_A.txt'), 'w', encoding='utf-8').write('\n'.join(report))
print('\n'.join(report[:120]))
print('...')
print('[written] ' + P(D, '_report_A.txt'))
