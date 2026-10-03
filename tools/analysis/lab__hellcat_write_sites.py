# hellcat_write_sites.py —— 解码 Dell/Goodix 工具里所有 hid_write 调用点，找出写序列
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

TOOL = r"<LAB>\touchpad-lab\vendor\dup\DellTouchpadUpdate_Hellcat_v0.2.2.100.exe"
data = open(TOOL, "rb").read()
print(f"文件大小: {len(data)}")

# --- 解析 PE 头与节表，建立 VA->文件偏移 映射 ---
e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
assert data[e_lfanew:e_lfanew + 4] == b"PE\0\0"
coff = e_lfanew + 4
nsec, = struct.unpack_from("<H", data, coff + 2)
opt_size, = struct.unpack_from("<H", data, coff + 16)
opt = coff + 20
magic, = struct.unpack_from("<H", data, opt)
image_base, = struct.unpack_from("<I", data, opt + 28)
print(f"节数={nsec} 可选头={opt_size} magic=0x{magic:X} ImageBase=0x{image_base:X}")
secs = []
sec_off = opt + opt_size
for i in range(nsec):
    o = sec_off + i * 40
    name = data[o:o + 8].rstrip(b"\0").decode("latin1")
    vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
    secs.append((name, vaddr, vsize, rawptr, rawsize))
    print(f"  {name:8s} VA=0x{image_base+vaddr:08X} vsize=0x{vsize:X} raw=0x{rawptr:X} size=0x{rawsize:X}")

def va2off(va):
    rva = va - image_base
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawptr + (rva - vaddr)
    return None

md = Cs(CS_ARCH_X86, CS_MODE_32)
md.skipdata = True
# 反汇编 .text
text = next(s for s in secs if s[0] == ".text")
code_off, code_va, code_size = text[3], image_base + text[1], text[4]
code = data[code_off:code_off + code_size]
insns = list(md.disasm(code, code_va))
print(f"\n.text 反汇编指令数: {len(insns)}")

HID_WRITE = 0x411560
HID_READ = 0x4113B0
sites = [(i.address, i.op_str) for i in insns if i.mnemonic == "call" and f"0x{HID_WRITE:x}" in i.op_str]
print(f"\n=== 调用 hid_write (0x{HID_WRITE:X}) 的位置: {len(sites)} 处 ===")
for a, op in sites:
    print(f"  0x{a:08X}")

def show(a, n=26, title=""):
    print(f"\n----- {title} @0x{a:08X} -----")
    idx = next((k for k, i in enumerate(insns) if i.address >= a), None)
    if idx is None:
        print("   (超出范围)")
        return
    for i in insns[max(0, idx - n):idx + 8]:
        mark = "   <<< hid_write" if i.mnemonic == "call" and f"0x{HID_WRITE:x}" in i.op_str else ""
        print(f"  {i.address:08X}: {i.bytes.hex():20s} {i.mnemonic:7s} {i.op_str}{mark}")

for a, _ in sites[:6]:
    show(a, 22, "写调用点上文")
