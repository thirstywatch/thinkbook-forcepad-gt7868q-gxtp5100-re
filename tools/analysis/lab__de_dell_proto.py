# de_dell_proto.py —— 反汇编 Dell Goodix 刷写器里的 HID 协议实现（v1/v2 帧格式 + 读回复方式）
# 用法: python de_dell_proto.py <exe> [关键字...]
import struct, re, sys
from capstone import *

path = sys.argv[1]
keys = sys.argv[2:] or ['use hid proto', 'readV1', 'readV2', 'Valid data length',
                        'write0', 'getCfgVer', 'subFwType', 'initVid', 'initPid']
b = open(path, 'rb').read()

pe = struct.unpack('<I', b[0x3C:0x40])[0]
nsec = struct.unpack('<H', b[pe + 6:pe + 8])[0]
optsz = struct.unpack('<H', b[pe + 20:pe + 22])[0]
sectab = pe + 24 + optsz
secs = []
for i in range(nsec):
    o = sectab + 40 * i
    nm = b[o:o + 8].rstrip(b'\x00').decode('latin1')
    vs, va, rs, ro = struct.unpack('<IIII', b[o + 8:o + 24])
    secs.append((nm, va, vs, ro, rs))
image_base = struct.unpack('<Q', b[pe + 24 + 24:pe + 24 + 32])[0]
magic = struct.unpack('<H', b[pe + 24:pe + 26])[0]
if magic == 0x20B:
    image_base = struct.unpack('<Q', b[pe + 24 + 24:pe + 24 + 32])[0]
else:
    image_base = struct.unpack('<I', b[pe + 24 + 28:pe + 24 + 32])[0]
print('ImageBase 0x%X  节: %s' % (image_base, ', '.join('%s@0x%X' % (s[0], s[1]) for s in secs)))

def va2off(va):
    for nm, sva, vsz, ro, rs in secs:
        base = image_base + sva
        if base <= va < base + max(vsz, rs):
            d = ro + (va - base)
            return d if 0 <= d < len(b) else None
    return None

def off2va(off):
    for nm, sva, vsz, ro, rs in secs:
        if ro <= off < ro + rs:
            return image_base + sva + (off - ro)
    return None

# ---- 找字符串 VA ----
text = next(s for s in secs if s[0] == '.text')
rdata = next(s for s in secs if s[0] == '.rdata')
text_bytes = b[text[3]:text[3] + text[4]]
text_va = image_base + text[1]

strvas = {}
for k in keys:
    for enc, tag in ((k.encode(), 'A'), (k.encode('utf-16-le'), 'U')):
        m = re.search(re.escape(enc), b)
        if not m: continue
        # ★ 回退到"整串开头"（LEA 引用串首，不是我们搜到的中段）
        s = m.start()
        while s > 0 and b[s - 1] > 0x1F:
            s -= 1
        va = off2va(s)
        if va is None: continue
        whole = b[s:s + 96].split(b'\x00')[0].decode('latin1', 'replace')
        strvas.setdefault(va, []).append('%s' % whole[:74])

# ---- 扫 .text 找引用（按位宽选方法） ----
magic = struct.unpack('<H', b[pe + 24:pe + 26])[0]
is64 = (magic == 0x20B)
print('PE magic=0x%X ⇒ %s' % (magic, 'PE32+ (x64, RIP 相对 LEA)' if is64 else 'PE32 (x86, 绝对地址立即数)'))
MODRM = {0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D}
xrefs = {}
n = len(text_bytes)
if is64:
    for i in range(n - 7):
        if text_bytes[i] in (0x48, 0x4C) and text_bytes[i + 1] == 0x8D and text_bytes[i + 2] in MODRM:
            disp = struct.unpack('<i', text_bytes[i + 3:i + 7])[0]
            insn_va = text_va + i
            tgt = insn_va + 7 + disp
            if tgt in strvas:
                xrefs.setdefault(tgt, []).append(insn_va)
else:
    for va in strvas:
        pat = struct.pack('<I', va)
        for m in re.finditer(re.escape(pat), text_bytes):
            xrefs.setdefault(va, []).append(text_va + m.start())
print('共找到引用点 %d 个' % sum(len(v) for v in xrefs.values()))

print('\n字符串 VA 与 xref 数:')
for va in sorted(strvas):
    print('  0x%X %-28s xref=%s' % (va, ','.join(strvas[va]), [hex(x) for x in xrefs.get(va, [])][:6]))

# ---- 反汇编每个 xref 附近 ----
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = False
for va in sorted(xrefs):
    for x in xrefs[va][:2]:
        start_off = va2off(x - 0x120)
        if start_off is None: start_off = va2off(x)
        code = b[start_off:start_off + 0x150]
        print('\n===== 引用 0x%X (%s) 的代码 @0x%X =====' % (va, ','.join(strvas[va]), x))
        for ins in md.disasm(code, image_base + text[1] + (start_off - text[3])):
            print('  %08X  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))
