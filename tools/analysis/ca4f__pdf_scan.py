import fitz, re, sys

doc = fitz.open(r"<LAB>\ca4f-hunt\aw_haptic.pdf")
print("pages:", doc.page_count)
full = []
for i in range(min(doc.page_count, 40)):
    t = doc[i].get_text()
    full.append((i, t))

joined = "\n".join(t for _, t in full)
# 找出芯片型号
for m in sorted(set(re.findall(r"AW\d{4,6}[A-Z]{0,4}", joined))):
    print("PART:", m)

print("\n--- 含 marking / 丝印 / top mark 的页 ---")
for i, t in full:
    if re.search(r"marking|Marking|top mark|Top Mark|丝印|MARK", t):
        print(f"  page {i+1}")
        for line in t.splitlines():
            if re.search(r"marking|Marking|top mark|Top Mark|丝印|MARK", line):
                print("     ", line.strip())
