import fitz, re

p = r"<LAB>\ca4f-hunt\AW86927FCR.pdf"
doc = fitz.open(p)
for i in range(doc.page_count):
    t = doc[i].get_text()
    if "Address Selection" in t or "AD pin" in t:
        print("=" * 25, "PAGE", i + 1, "=" * 25)
        print(t[:2200])
        pix = doc[i].get_pixmap(dpi=170)
        out = r"<LAB>\ca4f-hunt\aw86927_addr_p%d.png" % (i + 1)
        pix.save(out)
        print("[saved]", out)
        break
