import re, struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
a=open(BIN,"rb").read()
print("=== 扫 Goodix 子镜像头部 (模式: [串] 00 00 [len] [芯片名]) ===")
# 模式: 可打印串(3-24) 后跟 00 00, 再跟 1 字节长度, 再跟该长度的可打印串
pat=re.compile(rb"([\x21-\x7E]{3,24})\x00\x00([\x01-\x10])([\x20-\x7E]{1,16})")
hits=[]
for m in pat.finditer(a):
    name=m.group(1).decode('ascii','replace'); ln=m.group(2)[0]; chip=m.group(3).decode('ascii','replace')
    if len(chip)==ln and chip.isalnum():
        hits.append((m.start(), name, ln, chip))
for off,name,ln,chip in hits:
    print(f"   0x{off:06X}: 代号='{name}'  len={ln}  芯片='{chip}'")
print(f"   共 {len(hits)} 处")

print("\n=== 我们 BIN 里的所有芯片名候选 (含 7868/7936/GT 字样) ===")
for m in re.finditer(rb"[\x20-\x7E]{4,12}", a):
    s=m.group().decode('ascii')
    if re.search(r"(?i)(7868|7936|gt7|yelst|berlin)", s):
        print(f"   0x{m.start():06X}: {s}")

print("\n=== 容器内 'GXTP' / 'Goodix' 字样 ===")
for kw in (b"Goodix", b"GXTP", b"goodix"):
    occ=[m.start() for m in re.finditer(re.escape(kw), a)]
    print(f"   {kw}: {len(occ)} 处 {[hex(o) for o in occ[:6]]}")
