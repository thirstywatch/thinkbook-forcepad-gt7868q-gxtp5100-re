import fitz

doc = fitz.open(r"<LAB>\ca4f-hunt\aw_haptic.pdf")
for p in (0, 1, 3):
    print("=" * 30, "PAGE", p + 1, "=" * 30)
    print(doc[p].get_text()[:2500])

# 渲染 page2 / page4 为图片，便于直接看 Top Mark 与 Marking 列
for p in (1, 3):
    pix = doc[p].get_pixmap(dpi=180)
    out = r"<LAB>\ca4f-hunt\aw_p%d.png" % (p + 1)
    pix.save(out)
    print("saved", out, pix.width, pix.height)
