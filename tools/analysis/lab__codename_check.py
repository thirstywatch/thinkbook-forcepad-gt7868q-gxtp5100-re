import re
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
a=open(BIN,"rb").read()
FW=r"<LAB>\touchpad-lab\vendor\goodix-lvfs\GT7936L_16753412.bin"
b=open(FW,"rb").read()
print("=== 参照: GT7936L 固件头部 (BERLIN + 7936L) ===")
print("  前 32 字节:", b[:32].hex(' '))
print("  ASCII:", ''.join(chr(x) if 32<=x<127 else '.' for x in b[:32]))
print("\n=== 我们 BIN 里的 ASCII 串 (长度>=6, 全文件) ===")
for m in re.finditer(rb"[\x20-\x7E]{6,}", a):
    s=m.group().decode('ascii')
    print(f"   0x{m.start():06X}: {s[:60]}")
print("\n=== 我们 BIN 里 YELSTO 附近 64 字节 ===")
for m in re.finditer(rb"YELSTO", a):
    o=m.start()
    lo=max(0,o-32); hi=min(len(a),o+48)
    print(f"   @0x{o:06X}:")
    print("     原始:", a[lo:hi].hex(' '))
    print("     ASCII:", ''.join(chr(x) if 32<=x<127 else '.' for x in a[lo:hi]))
print("\n=== 我们 BIN 尾部 56KB 镜像开头的 ASCII ===")
img=a[0x19ABC:]
for m in re.finditer(rb"[\x20-\x7E]{5,}", img):
    print(f"   +0x{m.start():05X}: {m.group().decode('ascii')[:70]}")
