from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN,"rb").read(); IMG=0x19ABC; BASE=0x08000000
img=data[IMG:]
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.skipdata=True
insns=list(md.disasm(bytes(img), BASE))
def callers(t):
    o=[]
    for i in insns:
        if i.mnemonic.startswith("bl"):
            try: v=int(i.op_str.lstrip("#"),16)
            except: continue
            if v==t: o.append(i.address)
    return o
def fstart(a):
    s=None
    for i in insns:
        if i.address>a: break
        if i.mnemonic=="push" and "lr" in i.op_str: s=i.address
    return s
def show(a0,n=45,title=""):
    print(f"\n===== {title} @0x{a0:08X} =====")
    c=0
    for i in insns:
        if i.address<a0: continue
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")
        c+=1
        if c>=n: break

targets=[0x0800AD80, fstart(0x0800AD80)]
print("=== 0x0800AD80 所在函数:", hex(targets[1]) if targets[1] else None)
for t in dict.fromkeys([x for x in targets if x]):
    print(f"  bl 0x{t:08X} 的位置: {[hex(x) for x in callers(t)]}")
show(fstart(0x0800AD80), 60, "启动震动函数")
cb=0x0800D6F5
print(f"\n=== 回调 0x{cb:08X} 的调用者: {[hex(x) for x in callers(cb)]}")
show(cb, 35, "波形回调")
