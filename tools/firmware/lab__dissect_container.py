import re
p = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
b = open(p,"rb").read()
def strs(x, n=4):
    return [m.group().decode("ascii") for m in re.finditer(rb"[\x20-\x7e]{%d,}" % n, x)]
print("== 1) 1084 字节头部/清单 ==")
print("  first128:", b[:128].hex(" "))
print("  BE u32 @0x40..0x50:", [int.from_bytes(b[o:o+4],"big") for o in range(0x40,0x50,4)])
print("  strings:", strs(b[:1084], 4))
print()
print("== 2) 元数据区 (0x43C..0x113C) ==")
print("  head 96:", b[0x43C:0x43C+96].hex(" "))
print("  tail 76 :", b[0x113C-76:0x113C].hex(" "))
print("  strings:", strs(b[0x43C:0x113C], 4)[:20])
print()
print("== 3) ★ 明文载荷 B 自己的 128 字节头 (0x19A3C..0x19ABC) ==")
print("  hex  :", b[0x19A3C:0x19ABC].hex(" "))
print("  str  :", strs(b[0x19A3C:0x19ABC], 3))
print("  BE u32:", [int.from_bytes(b[o:o+4],"big") for o in range(0x19A3C,0x19A3C+32,4)])
print("  LE u32:", [int.from_bytes(b[o:o+4],"little") for o in range(0x19A3C,0x19A3C+32,4)])
print()
print("== 4) 加密载荷 A 头部 64 字节 ==")
print("  ", b[0x113C:0x113C+64].hex(" "))
print()
print("== 5) 全容器里像型号/项目名的字符串 ==")
seen=set()
for s in strs(b, 5):
    if re.search(r"(?i)tf100|gt7|7868|gxtp|tb14|patch|test_?fw|goodix|haptic|motor", s):
        if s not in seen:
            seen.add(s); print("   ", s[:90])
