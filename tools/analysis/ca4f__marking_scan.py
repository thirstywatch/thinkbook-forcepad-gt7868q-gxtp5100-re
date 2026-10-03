import fitz, re, os, glob

D = r"<LAB>\ca4f-hunt"

for path in sorted(glob.glob(os.path.join(D, "*.pdf"))):
    doc = fitz.open(path)
    joined = "\n".join(doc[i].get_text() for i in range(doc.page_count))
    parts = sorted(set(re.findall(r"AW\d{4,6}[A-Z]{0,4}", joined)))
    print("=" * 70)
    print(os.path.basename(path), "| pages:", doc.page_count, "| parts:", parts)
    # 直接搜 CA4F
    hits = [m.start() for m in re.finditer(r"CA4F", joined)]
    print("  字面量 'CA4F' 命中:", len(hits))
    # 找 Ordering Information 附近的 Marking 表
    for m in re.finditer(r"Ordering Information", joined):
        seg = joined[m.start():m.start() + 900]
        print("  --- Ordering Information 片段 ---")
        print("   " + seg.replace("\n", " | ")[:800])
        break
