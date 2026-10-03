from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct, re
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data=open(BIN,"rb").read(); img=data[0x19ABC:]; BASE=0x08000000
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.skipdata=True
insns=list(md.disasm(bytes(img), BASE))
print("=== 引用版本/测试字符串的代码 ===")
strs = {0x08000410:"TF100A_Test_FW", 0x08000430:"Nov 28 2023", 0x08000450:"19:10:59",
        0x0800CA32:"5.21.01.23007", 0x0800C704:"0123456789abcdef"}
for addr,nm in strs.items():
    pat=struct.pack("<I",addr)
    hits=[m.start() for m in re.finditer(re.escape(pat), img)]
    print(f"  {nm:16s} @0x{addr:08X}: 被引用 {len(hits)} 处 {[hex(BASE+h) for h in hits[:6]]}")
print()
def show(a,n,title):
    print(f"\n===== {title} @0x{a:08X} =====")
    c=0
    for i in insns:
        if i.address<a: continue
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")
        c+=1
        if c>=n: break
# USART1 ISR
show(0x0800DEE8, 30, "USART1 ISR")
# 引用测试字符串的代码
seen=set()
for addr,nm in list(strs.items())[:3]:
    pat=struct.pack("<I",addr)
    for m in re.finditer(re.escape(pat), img):
        site=BASE+m.start()
        if site in seen: continue
        seen.add(site)
        show(site-30, 26, f"引用 {nm} 的代码")
        break
