import fitz, re

p = r"<LAB>\ca4f-hunt\AW86927FCR.pdf"
doc = fitz.open(p)
print("pages:", doc.page_count, "| title:", doc.metadata.get("title"))

for i in (0, 1):
    print("=" * 30, "PAGE", i + 1, "=" * 30)
    print(doc[i].get_text())

# 渲染第 2 页看 Top Mark 图
pix = doc[1].get_pixmap(dpi=200)
out = r"<LAB>\ca4f-hunt\aw86927_p2.png"
pix.save(out)
print("saved", out)

full = "\n".join(doc[i].get_text() for i in range(doc.page_count))
print("\n=== 含 'TRIG' 的说明行（去重前 25 条）===")
seen = []
for line in full.splitlines():
    s = line.strip()
    if "TRIG" in s and s not in seen:
        seen.append(s)
print("\n".join(seen[:25]))

print("\n=== 含 'address' / 'I2C' 的说明行（前 20 条）===")
seen2 = []
for line in full.splitlines():
    s = line.strip()
    if re.search(r"address|I2C address|slave address", s, re.I) and s not in seen2:
        seen2.append(s)
print("\n".join(seen2[:20]))
