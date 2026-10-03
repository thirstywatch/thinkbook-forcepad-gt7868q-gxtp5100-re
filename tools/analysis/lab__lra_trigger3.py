from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct
BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data=open(BIN,"rb").read(); img=data[0x19ABC:]; BASE=0x08000000
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.skipdata=True
insns=list(md.disasm(bytes(img), BASE))
def fstart(a):
    s=None
    for i in insns:
        if i.address>a: break
        if i.mnemonic=="push" and "lr" in i.op_str: s=i.address
    return s
def callers(t):
    o=[]
    for i in insns:
        if i.mnemonic.startswith("bl"):
            try: v=int(i.op_str.lstrip("#"),16)
            except: continue
            if v==t: o.append(i.address)
    return o
def find_thumb_ptr(fn):
    pat=struct.pack("<I", fn|1)
    out=[]; s=0
    while True:
        j=img.find(pat,s)
        if j<0: break
        out.append(BASE+j); s=j+1
    return out
def show(a0,n,title):
    print(f"\n===== {title} @0x{a0:08X} =====")
    c=0
    for i in insns:
        if i.address<a0: continue
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")
        c+=1
        if c>=n: break

for name, fn in (("LRA TIM3 配置 0x08009750", 0x08009750),
                 ("波形回调 0x0800D6F4", 0x0800D6F4)):
    print(f"\n### {name}")
    print(f"   bl 调用者: {[hex(x) for x in callers(fn)]}")
    ptrs = find_thumb_ptr(fn)
    print(f"   作为函数指针(Thumb)出现在: {[hex(x) for x in ptrs]}")

fA = fstart(0x0800AD80)
print(f"\n### 含 0x0800AD80 的函数 = 0x{fA:08X}")
print(f"   bl 调用者: {[hex(x) for x in callers(fA)]}")
print(f"   函数指针出现处: {[hex(x) for x in find_thumb_ptr(fA)]}")
show(fA, 55, "震动启动函数(上游)")
for p in find_thumb_ptr(fA)[:3]:
    show(p-24, 20, f"指针注册点 0x{p:08X} 附近")
