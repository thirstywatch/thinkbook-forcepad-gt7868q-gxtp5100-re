from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data=open(BIN,"rb").read(); img=data[0x19ABC:]; BASE=0x08000000
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.skipdata=True
insns=list(md.disasm(bytes(img), BASE))
def show(a,n,title):
    print(f"\n===== {title} @0x{a:08X} =====")
    c=0
    for i in insns:
        if i.address<a: continue
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")
        c+=1
        if c>=n: break
def calls_from(a, n=40):
    out=[]; c=0
    for i in insns:
        if i.address<a: continue
        if i.mnemonic.startswith("bl"):
            try: out.append((i.address,int(i.op_str.lstrip("#"),16)))
            except: pass
        c+=1
        if c>=n: break
    return out
show(0x08008948, 34, "I2C1_ER 处理")
show(0x08008978, 60, "I2C1_EV 处理 (HID 报文入口)")
print("\n=== I2C1_EV 里的调用 ===")
for site,tgt in calls_from(0x08008978, 120):
    print(f"  0x{site:08X} -> 0x{tgt:08X}")
