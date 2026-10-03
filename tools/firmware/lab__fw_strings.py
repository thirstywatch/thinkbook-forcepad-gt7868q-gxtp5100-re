# fw_strings.py - dump 固件里的可打印字符串 (ASCII + UTF-16)
import re, struct
BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
img = data[0x19ABC:]
BASE = 0x08000000

print("=== ASCII 字符串 (len>=4) ===")
seen = set()
for m in re.finditer(rb"[\x20-\x7e]{4,}", img):
    s = m.group().decode("ascii")
    a = BASE + m.start()
    key = (a, s)
    if key in seen: continue
    seen.add(key)
    print("  0x%08X  %s" % (a, s))

print("\n=== UTF-16LE 字符串 (len>=4) ===")
n = 0
for m in re.finditer(rb"(?:[\x20-\x7e]\x00){4,}", img):
    s = m.group().decode("utf-16-le")
    a = BASE + m.start()
    print("  0x%08X  %s" % (a, s))
    n += 1
    if n > 40: break
if n == 0:
    print("  (无)")

print("\n=== 关键词过滤 (motor/vib/haptic/test/cmd/uart/at+) ===")
kw = ["motor", "vib", "haptic", "lra", "test", "cmd", "uart", "AT+", "fw", "ver", "click", "force"]
for m in re.finditer(rb"[\x20-\x7e]{3,}", img):
    s = m.group().decode("ascii")
    low = s.lower()
    if any(k.lower() in low for k in kw):
        print("  0x%08X  %s" % (BASE + m.start(), s))
