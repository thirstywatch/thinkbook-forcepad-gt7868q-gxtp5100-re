# container_layout.py -- what is ACTUALLY in TB14P_GT7868Q_14030522_20240202.BIN?
#
# Motivated by an apparent contradiction in the project docs:
#   HANDOVER.md:110        -> "161,628 B = 97 x 1084 records + 56,480 B image @0x19ABC"
#   FORENSICS-2.md:274-276 -> "1084 + 3328 + 100608 + 56608 = 161,628"
#
# RESULT (2026-09-13): they were never contradictory -- it was a false dilemma.
#   97*1084            = 105,148 = 0x19ABC   (= the image offset)
#   1084+3252+76+100608+128 = 105,148       (the same point, reached the long way)
# Both tile the file exactly. The 128-byte block is PAYLOAD B'S OWN HEADER, and
# 128 + 56,480 = 56,608 = exactly what the container header declares at 0x48.
# So there is NO missing tail *in the file*. Record 4 of the first reading is the
# one block that straddles the boundary of the second -- that is the whole story.
#
# THE TRAP: both sums equal the file size, which makes them look like competing
# hypotheses. They aren't. Check for identity before arguing about which is right.
#
# READ ONLY.
import struct, collections

BIN = (r'C:\Windows\System32\DriverStore\FileRepository'
       r'\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN')
d = open(BIN, 'rb').read()
print(f"file size: {len(d):,} B")
print()

for name, rec in [("97x1084", 1084), ("1084+3328+100608+56608", None)]:
    pass

# --- does 1084 tile the first 105,148 bytes cleanly? -------------------------
print("=== is the file 97 x 1084 + tail? ===")
print(f"  97 * 1084 = {97*1084:,}   + 56,480 = {97*1084+56480:,}   (file = {len(d):,})")
print(f"  105,020 = 1084+3328+100608 ; 97*1084 = 105,148 ; difference = {105148-105020}")
print()

# look for structure: are bytes 0..1084 and 1084..2168 similar?
h0 = d[0:1084]; h1 = d[1084:2168]; h2 = d[2168:3252]
def diffscore(a, b):
    n = sum(1 for x, y in zip(a, b) if x == y)
    return n / len(a)
print(f"  byte-identity  rec0 vs rec1 : {diffscore(h0,h1):.3f}")
print(f"  byte-identity  rec0 vs rec2 : {diffscore(h0,h2):.3f}")
print(f"  byte-identity  rec1 vs rec2 : {diffscore(h1,h2):.3f}")
print()

# --- header field dump: first 1084 bytes as BE u32 ---------------------------
print("=== first 1084 B as big-endian u32 (first 32 words) ===")
w = struct.unpack('>271I', d[0:1084])
for i in range(0, 32):
    print(f"  +0x{i*4:04X}  0x{w[i]:08X}  {w[i]:>12,}")
print()

# --- where does the plaintext payload actually start? -----------------------
print("=== searching for the payload start ===")
for cand in (0x19ABC, 0x19A3C, 105020, 105148, 97*1084):
    if cand + 16 <= len(d):
        print(f"  @0x{cand:06X} ({cand:>7,}): {' '.join(f'{b:02X}' for b in d[cand:cand+16])}")
        print(f"                 ascii: {d[cand:cand+24]!r}")
print()

# --- the documented 'payload length' field at 0x0048 ------------------------
print(f"=== header BE u32 @0x0048 = 0x{struct.unpack('>I', d[0x48:0x4C])[0]:X} "
      f"({struct.unpack('>I', d[0x48:0x4C])[0]:,}) ===")
print()

# --- does the SP/Reset vector at each candidate make sense? -----------------
print("=== ARM vector table candidates (SP must be 0x2000xxxx, Reset 0x0800xxxx) ===")
for cand in (0x19ABC, 0x19A3C, 105020, 105148, 97*1084):
    if cand + 8 > len(d): continue
    sp, rst = struct.unpack('<II', d[cand:cand+8])
    ok = (0x20000000 <= sp < 0x20020000) and (0x08000000 <= rst < 0x08100000)
    print(f"  @0x{cand:06X}  SP=0x{sp:08X}  Reset=0x{rst:08X}   {'<-- VALID vector table' if ok else ''}")
print()

# --- the tail: last 64 bytes of file and of the claimed image ---------------
print("=== tail ===")
print(f"  file last 32 B     : {' '.join(f'{b:02X}' for b in d[-32:])}")
print(f"  image last 32 B     : {' '.join(f'{b:02X}' for b in d[0x19ABC+56480-32:0x19ABC+56480])}")
print()

# --- what is between the records and the payload? ---------------------------
print("=== the region 105,020 .. 105,148 (the 128-byte discrepancy) ===")
print(' '.join(f'{b:02X}' for b in d[105020:105148]))
