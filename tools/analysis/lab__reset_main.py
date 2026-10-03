from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data=open(BIN,"rb").read(); img=data[0x19ABC:]; BASE=0x08000000
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.skipdata=True
insns=list(md.disasm(bytes(img), BASE))
def show(a,n,title,marks=()):
    print(f"\n===== {title} @0x{a:08X} =====")
    c=0
    for i in insns:
        if i.address<a: continue
        mk = "   <<<" if i.address in marks else ""
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}{mk}")
        c+=1
        if c>=n: break
def calls(a,n):
    out=[];c=0
    for i in insns:
        if i.address<a: continue
        if i.mnemonic.startswith("bl"):
            try: out.append((i.address,int(i.op_str.lstrip("#"),16)))
            except: pass
        c+=1
        if c>=n: break
    return out
show(0x08005164, 40, "Reset_Handler")
print("\n=== Reset 中的调用 ===")
cs = calls(0x08005164, 120)
for s,t in cs: print(f"  0x{s:08X} -> 0x{t:08X}")
# 追一层
if cs:
    t0 = cs[0][1]
    show(t0, 45, f"Reset 第一个调用 0x{t0:08X}")
    cs2 = calls(t0, 200)
    print(f"\n=== 0x{t0:08X} 里的调用 ===")
    for s,t in cs2[:25]: print(f"  0x{s:08X} -> 0x{t:08X}")
# TIM3 ISR
show(0x0800D628, 40, "TIM3 ISR (波形引擎)")
