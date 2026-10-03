from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN,"rb").read(); IMG=0x19ABC; BASE=0x08000000
img = data[IMG:]
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.skipdata=True
insns = list(md.disasm(bytes(img), BASE))
by = {i.address:i for i in insns}
def show(a0, n=70, title=""):
    print(f"\n===== {title} @0x{a0:08X} =====")
    c=0
    for i in insns:
        if i.address < a0: continue
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")
        c+=1
        if c>=n: break
# 找含 0x08009784 的函数起点
s=None
for i in insns:
    if i.address > 0x08009784: break
    if i.mnemonic=="push" and "lr" in i.op_str: s=i.address
print("含运行时调用的函数起点:", hex(s) if s else None)
show(s, 95, "LRA 运行时函数")
# 谁 bl 这个函数
def callers(t):
    out=[]
    for i in insns:
        if i.mnemonic.startswith("bl"):
            try: v=int(i.op_str.lstrip("#"),16)
            except: continue
            if v==t: out.append(i.address)
    return out
print("\n调用者:", [hex(x) for x in callers(s)])
# 顺带：全部对 0x200040B8 及邻近的立即数载入
import re
print("\n=== 载入 0x200040xx 附近的 movw/movt 位置 (含 0x40B8/0x40BC/0x40C0) ===")
for i in insns:
    if i.mnemonic=="movw" and i.op_str.startswith("r") and "#0x40" in i.op_str:
        try: imm=int(i.op_str.split("#")[1],16)
        except: continue
        if 0x40A0 <= imm <= 0x40E0:
            print(f"  0x{i.address:08X}: {i.mnemonic} {i.op_str}")
