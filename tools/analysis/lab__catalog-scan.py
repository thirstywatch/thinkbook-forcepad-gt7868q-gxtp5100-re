# -*- coding: utf-8 -*-
"""枚举 MS Update Catalog 里所有 Goodix 触控板/固件类条目，输出候选清单"""
import importlib.util, time, json, os, sys

spec = importlib.util.spec_from_file_location(
    "cf", os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog-fetch.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

QUERIES = ["goodix", "goodix touch", "goodix touchpad", "goodix firmware",
           "goodix input", "tpupdate", "goodix haptic"]
seen = {}
for q in QUERIES:
    for p in range(1, 7):
        try:
            rows, raw = C.search(q, p)
        except Exception as e:
            print("  ERR %s p%d %s" % (q, p, e))
            break
        if not rows:
            break
        for r in rows:
            c = r["cells"]
            t = c[1] if len(c) > 1 else ""
            # cells: [icon, Title, Products, Classification, LastUpdated, Version, Size, Download]
            ver = c[4] if len(c) > 4 else ""
            size = c[6] if len(c) > 6 else (c[5] if len(c) > 5 else "")
            seen.setdefault(r["uid"], {"title": t, "ver": ver, "size": size, "prod": c[2] if len(c) > 2 else ""})
        print("  %-18s p%d rows=%d (cum %d)" % (q, p, len(rows), len(seen)))
        time.sleep(0.8)

json.dump(seen, open("catalog-candidates.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print()
print("=== 全部命中 %d 条 ===" % len(seen))
kw = ("ouch", "irmware", "Input Device")
hits = {u: v for u, v in seen.items() if any(k in v["title"] for k in kw)}
print("=== 其中触控/固件/Input 类 %d 条 ===" % len(hits))
for u, v in sorted(hits.items(), key=lambda x: x[1]["title"]):
    print("%s | %-8s | %-9s | %s" % (u, v["ver"][:8], v["size"][:9], v["title"][:95]))
