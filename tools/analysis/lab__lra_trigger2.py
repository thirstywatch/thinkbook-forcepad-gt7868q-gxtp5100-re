from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data=open(BIN,"rb").read(); img=data[0x19ABC:]; BASE=0x08000000
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
def show(a0,n,title,ctx=0):
    print(f"\n===== {title} @0x{a0:08X} =====")
    c=0
    for i in insns:
        if i.address<a0: continue
        mark=" <<< 调用震动" if abs(i.address-ctx)<=2 and ctx else ""
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}{mark}")
        c+=1
        if c>=n: break
f=fstart(0x08003B98)
show(f, 70, "触发点所在函数 (含 bl 到震动函数)", ctx=0x08003B98)
print("\n=== 逐级上溯 ===")
lv=[f]
for depth in range(4):
    nxt=[]
    for t in lv:
        cs=callers(t)
        print(f"  第{depth+1}级: 函数 0x{t:08X} 的调用者 {[hex(x) for x in cs]}")
        nxt += [fstart(x) for x in cs if fstart(x)]
    lv=list(dict.fromkeys(nxt))
    if not lv: break
print("\n=== 修正回调地址(Thumb 位) ===")
print("  回调真实地址 = 0x0800D6F4")
show(0x0800D6F4, 30, "波形回调 0x0800D6F4")
