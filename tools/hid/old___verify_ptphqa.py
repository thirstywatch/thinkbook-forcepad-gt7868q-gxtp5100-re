# -*- coding: utf-8 -*-
# Verify: is the returned 256-byte payload byte-identical to Microsoft's published
# default PTP certification (PTPHQA) sample blob from
# https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-windows-precision-touchpad-collection
# READ-ONLY. No device access.
import os
D = r'<WORKSPACE>'
P = os.path.join

DOC = """
fc 28 fe 84 40 cb 9a 87 0d be 57 3c b6 70 09 88 07 97 2d 2b e3 38 34 b6 6c ed b0 f7 e5 9c f6 c2 2e 84
1b e8 b4 51 78 43 1f 28 4b 7c 2d 53 af fc 47 70 1b 59 6f 74 43 c4 f3 47 18 53 1a a2 a1 71 c7 95 0e 31
55 21 d3 b5 1e e9 0c ba ec b8 89 19 3e b3 af 75 81 9d 53 b9 41 57 f4 6d 39 25 29 7c 87 d9 b4 98 45 7d
a7 26 9c 65 3b 85 68 89 d7 3b bd ff 14 67 f2 2b f0 2a 41 54 f0 fd 2c 66 7c f8 c0 8f 33 13 03 f1 d3 c1 0b
89 d9 1b 62 cd 51 b7 80 b8 af 3a 10 c1 8a 5b e8 8a 56 f0 8c aa fa 35 e9 42 c4 d8 55 c3 38 cc 2b 53 5c
69 52 d5 c8 73 02 38 7c 73 b6 41 e7 ff 05 d8 2b 79 9a e2 34 60 8f a3 32 1f 09 78 62 bc 80 e3 0f bd 65
20 08 13 c1 e2 ee 53 2d 86 7e a7 5a c5 d3 7d 98 be 31 48 1f fb da af a2 a8 6a 89 d6 bf f2 d3 32 2a 9a
e4 cf 17 b7 b8 f4 e1 33 08 24 8b c4 43 a5 e5 24 c2
"""
doc = bytes(int(t,16) for t in DOC.split())
f256 = open(P(D,'col02_feature_256B.bin'),'rb').read()
r9   = open(P(D,'col02_feature_rid9_full.bin'),'rb').read()
p6   = open(P(D,'col02-precise','rid06_len257.bin'),'rb').read()
print('MS doc sample blob length =', len(doc))
print('256B file length          =', len(f256))
print('256B file == MS blob      :', f256 == doc)
print('rid9_full[1:257] == MS blob:', r9[1:257] == doc)
print('precise rid06_len257[1:] == MS blob:', p6[1:] == doc)
print('precise rid06_len257[0]   = 0x%02X (report ID byte)' % p6[0])
if f256 != doc:
    for i in range(min(len(f256),len(doc))):
        if f256[i] != doc[i]:
            print('first mismatch at %d: file=%02X doc=%02X' % (i, f256[i], doc[i])); break
# same for other declared vendor RIDs
for r in (7,9,11,12,13):
    p = P(D,'col02-precise','rid%02d_len257.bin'%r)
    if os.path.exists(p):
        b = open(p,'rb').read()
        print('rid%02d_len257 == rid06_len257 : %s' % (r, b == p6))
print()
print('---- the 4-byte RID 13 and 66-byte RID 11 and 736-byte RID 12 contents ----')
print('=> NOT observable: GET_FEATURE for those RIDs returns the RID-6 certification blob;')
print('   see _report_A.txt / _report_B.txt.')
