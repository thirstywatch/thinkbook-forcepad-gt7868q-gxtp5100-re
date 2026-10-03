# hellcat_seq.py —— 汇总官方工具 11 个 hid_write 调用点的参数与前置时序
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

TOOL = r"<LAB>\touchpad-lab\vendor\dup\DellTouchpadUpdate_Hellcat_v0.2.2.100.exe"
data = open(TOOL, "rb").read()
e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
coff = e_lfanew + 4
nsec, = struct.unpack_from("<H", data, coff + 2)
opt_size, = struct.unpack_from("<H", data, coff + 16)
opt = coff + 20
image_base, = struct.unpack_from("<I", data, opt + 28)
secs = []
sec_off = opt + opt_size
for i in range(nsec):
    o = sec_off + i * 40
    name = data[o:o + 8].rstrip(b"\0").decode("latin1")
    vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
    secs.append((name, vaddr, vsize, rawptr, rawsize))

md = Cs(CS_ARCH_X86, CS_MODE_32)
md.skipdata = True
text = next(s for s in secs if s[0] == ".text")
code = data[text[3]:text[3] + text[4]]
insns = list(md.disasm(code, image_base + text[1]))
addr_of = {i.address: k for k, i in enumerate(insns)}

HID_WRITE, HID_READ = 0x411560, 0x4113B0
sites = [i.address for i in insns if i.mnemonic == "call" and f"0x{HID_WRITE:x}" in i.op_str]

print(f"共 {len(sites)} 个 hid_write 调用点\n")
for a in sites:
    k = addr_of[a]
    # 向上找 push 立即数（最多 40 条）
    line = []
    pushed = []
    for j in range(k - 1, max(0, k - 40), -1):
        i = insns[j]
        if i.mnemonic == "push":
            pushed.append(i.op_str)
            if len(pushed) >= 4:
                break
        if i.mnemonic in ("call",) or (i.mnemonic == "ret"):
            break
    pushed = pushed[::-1]   # 恢复从左到右
    # 更早是否调用过 hid_read
    had_read = False
    cmps = []
    for j in range(k - 1, max(0, k - 120), -1):
        i = insns[j]
        if i.mnemonic == "call" and f"0x{HID_READ:x}" in i.op_str:
            had_read = True
        if i.mnemonic == "cmp" and ("eax" in i.op_str or "al" in i.op_str):
            cmps.append(i.op_str)
        if i.mnemonic == "ret":
            break
    print(f"--- 0x{a:08X} ---")
    print(f"    参数push(左→右): {pushed}")
    print(f"    之前有 hid_read: {had_read}   对返回值的比较: {[c for c in reversed(cmps)][:4]}")
