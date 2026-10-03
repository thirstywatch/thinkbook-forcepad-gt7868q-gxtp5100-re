import fitz, re

p = r"<LAB>\ca4f-hunt\AW86927FCR.pdf"
doc = fitz.open(p)
full = "\n".join(doc[i].get_text() for i in range(doc.page_count))

pat = re.compile(r"[^\n]*(?:I2C\s*(?:slave\s*)?address|SLAVE.?ADDR|AD pin|address select|0x5[0-9A-Fa-f]|0x3[0-9A-Fa-f]|7.?bit address)[^\n]*", re.I)
seen = []
for line in full.splitlines():
    s = line.strip()
    if re.search(r"address", s, re.I) and re.search(r"0x|AD|slave|7.?bit|select", s, re.I):
        if s not in seen:
            seen.append(s)
print("=== 含 address 的行 ===")
for s in seen[:40]:
    print("  ", s)

print("\n=== 专门找 'Slave Address' / 'I2C Address' 段落 ===")
for m in re.finditer(r"(?:Slave Address|I2C Address|IIC Address|ADDRESS)", full):
    seg = full[m.start(): m.start() + 500].replace("\n", " | ")
    print("  ---", seg[:460])
