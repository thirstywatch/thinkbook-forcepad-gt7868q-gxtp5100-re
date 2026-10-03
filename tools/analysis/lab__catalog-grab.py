# -*- coding: utf-8 -*-
"""按 updateID 抓取 MS Update Catalog 的 cab 到 _cabs/"""
import importlib.util, os, sys, time, json, re

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("cf", os.path.join(here, "catalog-fetch.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

OUT = os.path.join(here, "_cabs")
os.makedirs(OUT, exist_ok=True)

uids = sys.argv[1:]
if not uids:
    print("usage: catalog-grab.py <uid> [uid...]")
    sys.exit(2)

manifest = os.path.join(here, "_cabs", "_manifest.txt")
for uid in uids:
    try:
        ls, raw = C.links(uid)
    except Exception as e:
        print("ERR links %s %s" % (uid, e)); continue
    print("%s -> %d links" % (uid, len(ls)))
    for u in ls:
        name = u.rsplit("/", 1)[-1]
        dest = os.path.join(OUT, name)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            print("   skip (exists) %s" % name); continue
        try:
            data = C.get(u)
            open(dest, "wb").write(data)
            print("   saved %s (%d B)" % (name, len(data)))
            with open(manifest, "a", encoding="utf-8") as f:
                f.write("%s\t%s\t%s\n" % (uid, name, len(data)))
        except Exception as e:
            print("   ERR dl %s %s" % (u, e))
        time.sleep(0.6)
