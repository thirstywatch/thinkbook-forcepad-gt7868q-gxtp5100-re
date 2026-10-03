import fitz, re

p = r"<LAB>\ca4f-hunt\AW86927FCR.pdf"
doc = fitz.open(p)
for i in range(doc.page_count):
    t = doc[i].get_text()
    if re.search(r"Table\s*3", t) and re.search(r"address", t, re.I):
        print("=" * 25, "PAGE", i + 1, "=" * 25)
        # 只打印含 address/AD/Table 3 的邻近段落
        idx = t.find("Table 3")
        if idx < 0:
            idx = t.lower().find("address selection")
        print(t[max(0, idx - 900): idx + 700])
        pix = doc[i].get_pixmap(dpi=170)
        out = r"<LAB>\ca4f-hunt\aw86927_tbl3_p%d.png" % (i + 1)
        pix.save(out)
        print("[saved]", out)
        break
else:
    print("没有单独找到 Table 3；列出所有含 'Address Selection' 的页")
    for i in range(doc.page_count):
        if "Address Selection" in doc[i].get_text():
            print("  page", i + 1)
