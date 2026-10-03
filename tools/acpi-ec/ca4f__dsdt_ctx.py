import re, os

D = r"<WORKSPACE>"
b = open(os.path.join(D, "DSDT_LENOVO_CB-01____00000001.bin"), "rb").read()
print("DSDT size", len(b))

def ctx(pat, span=140, limit=12, label=""):
    print("\n" + "=" * 70)
    print("### ", label or pat)
    n = 0
    for m in re.finditer(pat, b):
        n += 1
        if n > limit:
            print("   ... (更多 %d)" % (len(re.findall(pat, b)) - limit))
            break
        seg = b[max(0, m.start() - span): m.start() + span]
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in seg)
        print("  @0x%06X  %s" % (m.start(), txt))

ctx(rb"I2C0", label="I2C0 引用")
ctx(rb"I2C1", label="I2C1 引用")
ctx(rb"trigger", span=200, limit=6, label="trigger（小写）")
ctx(rb"Trigger", span=200, limit=6, label="Trigger")
ctx(rb"GXTP", span=200, limit=6, label="GXTP")
