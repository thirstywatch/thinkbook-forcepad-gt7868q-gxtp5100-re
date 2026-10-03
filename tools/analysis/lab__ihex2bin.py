"""把 Goodix GT9896 ihex 固件转为二进制，并用 A③ 强判据测试其作为明文锚点的价值。"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, "goodix_gt9896_fw.bin.ihex")

mem = bytearray()
base = 0
maxaddr = 0
lines = 0
with open(src, "r") as f:
    for ln in f:
        ln = ln.strip()
        if not ln.startswith(":"):
            continue
        lines += 1
        b = bytes.fromhex(ln[1:])
        n = b[0]
        addr = (b[1] << 8) | b[2]
        typ = b[3]
        data = b[4:4 + n]
        if typ == 0x00:      # data
            a = base + addr
            if a + n > len(mem):
                mem.extend(b"\x00" * (a + n - len(mem)))
            mem[a:a + n] = data
            maxaddr = max(maxaddr, a + n)
        elif typ == 0x04:    # extended linear address
            base = ((data[0] << 8) | data[1]) << 16
        elif typ == 0x02:
            base = ((data[0] << 8) | data[1]) << 4
        elif typ == 0x01:
            break

out = os.path.join(HERE, "goodix_gt9896_fw.bin")
open(out, "wb").write(bytes(mem[:maxaddr]))
print("ihex 行数 %d，解出 %d B -> %s" % (lines, maxaddr, out))

d = bytes(mem[:maxaddr])
print("前 64 B:", " ".join("%02X" % x for x in d[:64]))
print("ASCII   :", "".join(chr(x) if 32 <= x < 127 else "." for x in d[:64]))
print("YELSTO 出现 %d 次，YELS %d 次" % (d.count(b"YELSTO"), d.count(b"YELS")))
