"""对抗性自检：I2C1 基址是否以【字节/字面量】形式存在于数据里
（若存在，则"只能由那 12 个 movw/movt 物化"的完备性论证需要重审）。

搜索整个容器（不只明文段），34 位小端与大端两种写法。
"""
import struct, os
BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "touchpad_GT7868Q_fw.bin")
d = open(BIN, "rb").read()

targets = {
    "I2C1 基址 0x40005400": 0x40005400,
    "I2C1 DR   0x40005410": 0x40005410,
    "I2C1 SR1  0x40005414": 0x40005414,
    "I2C1 SR2  0x40005418": 0x40005418,
    "I2C2 基址 0x40005800": 0x40005800,
    "SPI1 基址 0x40013000": 0x40013000,
    "GPIOB     0x40010C00": 0x40010C00,
    "USART1    0x40013800": 0x40013800,
}
for name, v in targets.items():
    le = struct.pack("<I", v)
    be = struct.pack(">I", v)
    half = struct.pack("<H", v & 0xFFFF)          # 低半字
    hits_le = [i for i in range(len(d) - 3) if d[i:i+4] == le]
    hits_be = [i for i in range(len(d) - 3) if d[i:i+4] == be]
    print("%-22s  LE32 x%-3d %s   BE32 x%-3d" % (
        name, len(hits_le),
        ("@" + ", ".join("0x%X" % h for h in hits_le[:8])) if hits_le else "",
        len(hits_be)))
    for h in hits_le[:8]:
        print("      fileoff 0x%06X  → 地址 0x%08X" % (h, 0x08005000 + h - 0x19ABC))
