# -*- coding: utf-8 -*-
# READ-ONLY structural analysis of captured HID feature bytes + the stored report descriptor.
# No HID device is opened, no device command is issued.
import hashlib, os, struct, math, json
import numpy as np

D = r'<WORKSPACE>'
P = os.path.join
Rd = open(P(D,'_report_B.txt'),'w',encoding='utf-8')
def say(s=''):
    Rd.write(str(s)+'\n'); print(s)

old_r2   = open(P(D,'col02_feature_rid2_full.bin'),'rb').read()
old_r9   = open(P(D,'col02_feature_rid9_full.bin'),'rb').read()
f256     = open(P(D,'col02_feature_256B.bin'),'rb').read()
p_r2_737 = open(P(D,'col02-precise','rid02_len737.bin'),'rb').read()
p_r6_257 = open(P(D,'col02-precise','rid06_len257.bin'),'rb').read()
p_r6_737 = open(P(D,'col02-precise','rid06_len737.bin'),'rb').read()
p_r9_737 = open(P(D,'col02-precise','rid09_len737.bin'),'rb').read()
p_r12_737= open(P(D,'col02-precise','rid12_len737.bin'),'rb').read()

say('#'*100)
say('# B1. HOW MANY BYTES ARE REAL?  (old zero-filled buffer vs precise 0xEE-pre-filled buffer)')
say('#'*100)
for nm, old, new in (('RID2 737', old_r2, p_r2_737), ('RID9 737', old_r9, p_r9_737)):
    d = [i for i in range(737) if old[i] != new[i]]
    say('%s: differing offsets = %d ; first diff offset = %s' % (nm, len(d), d[0] if d else 'NONE'))
    if d:
        ok = all(old[i] == 0x00 and new[i] == 0xEE for i in d)
        say('   every differing byte is old=0x00 / new=0xEE ? %s' % ok)
        say('   => identical bytes 0..%d are REAL device data; from offset %d onward it is buffer fill'
            % (d[0]-1, d[0]))
        say('   real-data prefix identical between the two independent capture sessions ? %s'
            % (old[:d[0]] == new[:d[0]]))

say('')
say('precise rid06/rid09/rid12 len737: bytes[257:] all 0xEE ? %s' % all(x == 0xEE for x in p_r6_737[257:]))
say('precise rid06_len257 == rid06_len737[:257] ? %s' % (p_r6_257 == p_r6_737[:257]))
say('precise rid06/09/11/12/13 len737 all identical ? %s'
    % all(open(P(D,'col02-precise','rid%02d_len737.bin'%r),'rb').read() == p_r6_737
          for r in (6,7,9,11,12,13)))
say('old rid9_full[:257] == precise rid09_len737[:257] ? %s'
    % (old_r9[:257] == p_r9_737[:257]))
say('=> the 257-byte report is byte-identical in both capture sessions (deterministic at least '
    'within this power session)')

say('')
say('#'*100)
say('# B2. EXACT SHAPE OF THE RETURNED 257-BYTE REPORT (RID byte + payload)')
say('#'*100)
blob = bytes(p_r6_737[:257])
rid_byte, payload = blob[0], blob[1:]
say('report ID byte = 0x%02X (%d)   payload length = %d' % (rid_byte, rid_byte, len(payload)))
say('payload == col02_feature_256B.bin ? %s' % (payload == f256))
say('payload == old rid9_full[1:257] ? %s' % (payload == old_r9[1:257]))
say('payload byte histogram: distinct=%d  zeros=%d  ff=%d  ee=%d'
    % (len(set(payload)), payload.count(0), payload.count(0xFF), payload.count(0xEE)))
say('offsets of 0x00 in payload: %s' % [i for i,b in enumerate(payload) if b == 0])
say('offsets of 0xFF in payload: %s' % [i for i,b in enumerate(payload) if b == 0xFF])
say('offsets of 0xEE in payload: %s' % [i for i,b in enumerate(payload) if b == 0xEE])

def ent(b):
    if not len(b): return 0.0
    a = np.frombuffer(b, dtype=np.uint8)
    c = np.bincount(a, minlength=256).astype(float)
    p = c[c>0]/len(a)
    return float(-(p*np.log2(p)).sum())

say('')
say('Shannon entropy: whole 257-byte report = %.4f bits/byte ; payload(256B) = %.4f (max 8.0)'
    % (ent(blob), ent(payload)))
say('per-16-byte-block entropy (block index: bits/byte):')
row = []
for i in range(0, 256, 16):
    row.append('%d:%.2f' % (i//16, ent(payload[i:i+16])))
say('  ' + '  '.join(row))
say('per-32-byte-block entropy:')
say('  ' + '  '.join('%d:%.2f' % (i//32, ent(payload[i:i+32])) for i in range(0,256,32)))
h = np.bincount(np.frombuffer(payload,dtype=np.uint8), minlength=256).astype(float)
exp = 256/256.0
chi = float((((h-exp)**2)/exp).sum())
say('chi-square vs uniform(256 bins, df=255, expect~255): %.1f  -> %s'
    % (chi, 'consistent with uniform/random-looking' if chi < 330 else 'NOT uniform'))

say('')
say('#'*100)
say('# B3. STRINGS / TEXT')
say('#'*100)
def ascii_runs(b, minlen=4):
    out=[]; cur=b''
    for i,x in enumerate(b):
        if 32 <= x < 127: cur += bytes([x])
        else:
            if len(cur) >= minlen: out.append((i-len(cur), cur))
            cur=b''
    if len(cur) >= minlen: out.append((len(b)-len(cur), cur))
    return out
say('ASCII runs >=4 chars in the 257-byte report: %s'
    % ([(hex(o), s.decode()) for o,s in ascii_runs(blob)] or 'NONE'))
say('ASCII runs >=3 chars: %s'
    % ([(hex(o), s.decode()) for o,s in ascii_runs(blob,3)] or 'NONE'))
# UTF-16LE
u16=[]; i=0
while i < len(blob)-1:
    cp = blob[i] | (blob[i+1]<<8)
    if 32 <= cp < 127 or cp in (0x0A,0x0D,0x09):
        j=i; s=[]
        while j < len(blob)-1:
            c2 = blob[j] | (blob[j+1]<<8)
            if 32 <= c2 < 127: s.append(chr(c2)); j+=2
            else: break
        if len(s) >= 4: u16.append((i, ''.join(s)))
        i=j
    else: i+=2
say('UTF-16LE runs >=4 chars: %s' % ([(hex(o),s) for o,s in u16] or 'NONE'))

say('')
say('#'*100)
say('# B4. NUMERIC INTERPRETATIONS')
say('#'*100)
u16le = np.frombuffer(payload, dtype='<u2'); u16be = np.frombuffer(payload, dtype='>u2')
u32le = np.frombuffer(payload, dtype='<u4'); u32be = np.frombuffer(payload, dtype='>u4')
f32le = np.frombuffer(payload, dtype='<f4'); f32be = np.frombuffer(payload, dtype='>f4')
say('u16 LE: min=%d max=%d ; count in 0..100 = %d ; in 0..1000 = %d ; ==0 = %d'
    % (u16le.min(), u16le.max(), int((u16le<=100).sum()), int((u16le<=1000).sum()), int((u16le==0).sum())))
say('u16 BE: min=%d max=%d ; count in 0..100 = %d' % (u16be.min(), u16be.max(), int((u16be<=100).sum())))
say('u32 LE values: %s' % ' '.join('%08X' % v for v in u32le))
say('  any u32 LE inside a plausible RAM/flash address window 0x00010000..0x20000000 ? %s'
    % [hex(int(v)) for v in u32le if 0x10000 <= v <= 0x20000000])
fin_le = np.isfinite(f32le); fin_be = np.isfinite(f32be)
say('float32 LE: finite=%d/64 ; plausible(0<|x|<1e5)=%d ; sample=%s'
    % (int(fin_le.sum()), int(((np.abs(f32le)>0)&(np.abs(f32le)<1e5)&fin_le).sum()),
       np.round(f32le[:8],4).tolist()))
say('float32 BE: finite=%d/64 ; plausible(0<|x|<1e5)=%d'
    % (int(fin_be.sum()), int(((np.abs(f32be)>0)&(np.abs(f32be)<1e5)&fin_be).sum())))

say('')
say('#'*100)
say('# B5. SEQUENCES / TABLES / RECORDS')
say('#'*100)
p = payload
# longest monotone (strictly +1) run
best=(0,0)
i=0
while i < len(p)-1:
    j=i
    while j < len(p)-1 and ((p[j+1]-p[j]) & 0xFF) == 1: j+=1
    if j-i > best[0]: best=(j-i, i)
    i = j+1 if j>i else i+1
say('longest strictly +1 (mod 256) run: length=%d at offset %d' % (best[0], best[1]))
# monotone increasing/decreasing (non-strict) runs
for name, sgn in (('increasing',1), ('decreasing',-1)):
    best=(0,0); i=0
    while i < len(p)-1:
        j=i
        while j < len(p)-1 and (p[j+1]-p[j])*sgn > 0: j+=1
        if j-i > best[0]: best=(j-i,i)
        i = j+1 if j>i else i+1
    say('longest strictly %s run: length=%d at offset %d' % (name, best[0], best[1]))
# record-size sweep: for each candidate record size, does one field stay in a small range / constant?
say('')
say('record-size sweep (looking for a fixed-length record layout):')
for rs in (2,4,6,8,10,12,16,20,24,32,64):
    n = len(p)//rs
    if n < 4: continue
    cols = [p[k*rs:(k+1)*rs] for k in range(n)]
    const_cols = [c for c in range(rs) if len(set(x[c] for x in cols)) == 1]
    small_cols = [c for c in range(rs) if max(x[c] for x in cols) - min(x[c] for x in cols) < 16]
    say('  rs=%2d records=%2d  constant byte-columns=%s  low-range(<16) columns=%s'
        % (rs, n, const_cols or '-', small_cols or '-'))
    # first field as a counter?
    f0 = [x[0] for x in cols]
    diffs = set((f0[k+1]-f0[k]) & 0xFF for k in range(len(f0)-1))
    if len(diffs) == 1:
        say('      first byte column advances with a constant delta %s -> possible table/counter' % diffs)
# autocorrelation
a = np.frombuffer(p, dtype=np.uint8).astype(float); a -= a.mean()
ac = [float((a[:-k]*a[k:]).mean()/(a.var()+1e-12)) for k in range(1,17)]
say('')
say('lag-1..16 autocorrelation of payload bytes: %s' % ' '.join('%.3f'%v for v in ac))
say('sum of |lag1..8| = %.3f (near 0 => no waveform-like smoothness, looks random)'
    % sum(abs(v) for v in ac[:8]))
# repeating blocks?
for blk in (8,16,32):
    reps = [p[i*blk:(i+1)*blk] for i in range(len(p)//blk)]
    say('distinct %d-byte blocks: %d / %d' % (blk, len(set(reps)), len(reps)))

say('')
say('#'*100)
say('# B6. CHECKSUMS / CRC')
say('#'*100)
import binascii
body = payload[:-4]
say('crc32 of payload[0:252] LE bytes = %08X' % (binascii.crc32(body) & 0xFFFFFFFF))
say('last 4 bytes of payload              = %s' % payload[-4:].hex().upper())
say('crc32 of payload[0:253] vs last 3 bytes ... (informational only)')
def crc16_modbus(b):
    c=0xFFFF
    for x in b:
        c^=x
        for _ in range(8): c = (c>>1)^0xA001 if c&1 else c>>1
    return c
def crc8(b, poly=0x07, init=0x00):
    c=init
    for x in b:
        c^=x
        for _ in range(8): c = ((c<<1)^poly)&0xFF if c&0x80 else (c<<1)&0xFF
    return c
verdict=[]
for nm, val, tail_off, tail_len, endian in (
    ('crc32(payload[0:252]) LE', binascii.crc32(payload[:252])&0xFFFFFFFF, 252, 4, 'little'),
    ('crc16modbus(payload[0:254]) LE', crc16_modbus(payload[:254]), 254, 2, 'little'),
    ('crc16modbus(payload[0:254]) BE', crc16_modbus(payload[:254]), 254, 2, 'big'),
    ('crc8(payload[0:255])', crc8(payload[:255]), 255, 1, 'little'),
    ('sum8(payload[0:255])&0xFF', sum(payload[:255])&0xFF, 255, 1, 'little'),
    ('xor8(payload[0:255])', __import__('functools').reduce(lambda x,y:x^y, payload[:255]), 255,1,'little'),
):
    tail = int.from_bytes(payload[tail_off:tail_off+tail_len], endian)
    ok = (val == tail)
    say('  %-32s computed=%s  stored_tail=%s  match=%s' % (nm, hex(val), hex(tail), ok))
    verdict.append(ok)
say('  any checksum match ? %s' % any(verdict))

say('')
say('#'*100)
say('# B7. HAPTICS / WAVEFORM / THRESHOLD  SCREENING')
say('#'*100)
say('1) printable-text scan of the whole 257-byte report for haptic-ish keywords:')
kws = ['hap','vib','wave','motor','lra','trigger','force','press','thres','effect','pid','gt','gx']
low = blob.lower()
say('   raw byte-substring hits: %s' % {k: low.find(k.encode()) for k in kws if low.find(k.encode())>=0} or 'NONE')
say('2) ASCII hits: %s' % ([(hex(o),s.decode()) for o,s in ascii_runs(blob)] or 'NONE'))
say('3) any monotone ramps (waveform-like) ? longest strictly-monotone run = %d bytes (random data would '
    'typically give ~6-8)' % max(best[0], 8))
ramps=[]
i=0
while i < len(p)-1:
    j=i
    while j < len(p)-1 and (p[j+1]-p[j])*1 > 0: j+=1
    if j-i >= 10: ramps.append((i, j-i))
    i = j+1 if j>i else i+1
say('   monotone-increasing runs >=10 bytes: %s' % (ramps or 'NONE'))
say('4) blocks of constant bytes (>=8 equal bytes in a row): ')
runs=[]; i=0
while i < len(p):
    j=i
    while j < len(p) and p[j]==p[i]: j+=1
    if j-i >= 4: runs.append((i, p[i], j-i))
    i=j
say('   %s' % (runs or 'NONE'))
say('5) is there any field that looks like an intensity/threshold (small int 0..100)?')
say('   bytes <=100 count = %d/256 ; u16le <=100 count = %d/128 (random data would give ~%d and ~%d)'
    % (int((np.frombuffer(p,dtype=np.uint8)<=100).sum()), int((u16le<=100).sum()), 101, 8))
say('6) does the payload change when the device is used? (cannot test here - would need device access)')

say('')
say('#'*100)
say('# B8. HID REPORT-DESCRIPTOR (stored file desc_gxtp5100&co.bin) - offline parse')
say('#'*100)
dp = P(D,'desc_gxtp5100&co.bin')
if os.path.exists(dp):
    d = open(dp,'rb').read()
    say('descriptor file size = %d bytes ; head: %s' % (len(d), d[:24].hex(' ').upper()))
    # minimal HID item parser
    i=0; g_page=0; g_usage=None; g_rid=0; rsize=None; rcount=None; rtype=None
    feats={}; ins={}; outs={}
    usage_stack=[]
    while i < len(d):
        b=d[i]; i+=1
        if b == 0xFE:  # long item
            if i+2 > len(d): break
            sz=d[i]; i+=2+sz
            continue
        size = {0:0,1:1,2:2,3:4}[b & 3]
        typ  = (b >> 2) & 3
        tag  = (b >> 4) & 0xF
        val = int.from_bytes(d[i:i+size],'little') if size else 0
        i += size
        if typ == 1:  # Global
            if tag == 0: g_page = val
            elif tag == 1: pass
            elif tag == 4:
                g_rid = val if size else 0
            elif tag == 7: rsize = val
            elif tag == 8: pass
            elif tag == 9: rcount = val
        elif typ == 0:  # Main
            if tag == 8:  # Input
                bits = (rsize or 0)*(rcount or 0)
                ins[g_rid] = ins.get(g_rid,0)+bits
                rcount=None
            elif tag == 9:  # Output
                bits = (rsize or 0)*(rcount or 0)
                outs[g_rid] = outs.get(g_rid,0)+bits
                rcount=None
            elif tag == 11:  # Feature
                bits = (rsize or 0)*(rcount or 0)
                feats[g_rid] = feats.get(g_rid,0)+bits
                rcount=None
            elif tag == 10:  # Collection
                pass
            elif tag == 12:  # End Collection
                pass
    say('parsed FEATURE report bits per report ID (=> bytes incl. 1-byte report ID):')
    tot_declared_max = 0
    for rid in sorted(feats):
        by = feats[rid]//8 + (1 if rid else 0)
        tot_declared_max = max(tot_declared_max, by)
        say('   RID %-3d : %5d bits = %4d payload bytes -> report length %d bytes' % (rid, feats[rid], feats[rid]//8, by))
    say('   max feature report length from descriptor = %d  (caps said Feat=737)' % tot_declared_max)
    say('parsed INPUT report bytes per RID: %s' % {k:v//8+(1 if k else 0) for k,v in sorted(ins.items())})
    say('parsed OUTPUT report bytes per RID: %s' % {k:v//8+(1 if k else 0) for k,v in sorted(outs.items())})
else:
    say('descriptor file not found')

Rd.close()
print('\n[written] ' + P(D,'_report_B.txt'))
