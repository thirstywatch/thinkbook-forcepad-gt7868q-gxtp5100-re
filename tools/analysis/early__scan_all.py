import struct, os, math, subprocess, sys, glob

CAND = r"<WORKSPACE>"
TMP = os.path.join(CAND, "_extract")

def shannon(data):
    if not data:
        return 0.0
    cnt = [0]*256
    for b in data:
        cnt[b] += 1
    n = len(data)
    e = 0.0
    for c in cnt:
        if c:
            p = c/n
            e -= p*math.log2(p)
    return e

def find_vtable(data, base=0x08000000):
    hits = []
    n = len(data)
    for i in range(0, n-8, 4):
        sp = struct.unpack_from("<I", data, i)[0]
        rst = struct.unpack_from("<I", data, i+4)[0]
        if (0x20000000 <= sp <= 0x20010000) and (rst & 0xFF000000 == 0x08000000) and (rst & 1):
            cnt = 0
            for k in range(2, 16):
                v = struct.unpack_from("<I", data, i+k*4)[0]
                if v == 0 or (v & 0xFF000000 == 0x08000000 and v & 1):
                    cnt += 1
            if cnt >= 8:
                hits.append((i, sp, rst, cnt))
    return hits

def entropy_profile(data, win=2048, step=2048):
    prof = []
    for off in range(0, len(data)-win, step):
        prof.append((off, shannon(data[off:off+win])))
    return prof

def analyze(path):
    data = open(path, "rb").read()
    n = len(data)
    print("="*70)
    print("FILE:", os.path.basename(path), "SIZE", n, hex(n))
    prof = entropy_profile(data)
    if prof:
        hi = max(p[1] for p in prof)
        lo = min(p[1] for p in prof)
        # 找高熵->低熵边界
        boundary = None
        for i in range(1, len(prof)):
            if prof[i-1][1] > 7.3 and prof[i][1] < 6.0:
                boundary = prof[i][0]
                break
        print("  entropy range: %.2f..%.2f" % (lo, hi))
        if boundary is not None:
            print("  high->low entropy boundary ~ offset", hex(boundary))
        else:
            print("  no clear high->low boundary (单一熵区)")
    vt = find_vtable(data)
    if vt:
        for (o, sp, rst, c) in vt[:3]:
            print("  VTABLE @%s SP=%s Reset=%s goodvec=%d" % (hex(o), hex(sp), hex(rst), c))
    else:
        print("  no Cortex-M vector table found")

def main():
    files = []
    for f in os.listdir(CAND):
        fp = os.path.join(CAND, f)
        if f.lower().endswith(".cab"):
            # 解包 cab
            sub = os.path.join(TMP, f[:-4])
            os.makedirs(sub, exist_ok=True)
            try:
                subprocess.run(["expand.exe", fp, "-F:*", sub], capture_output=True, timeout=120)
            except Exception as e:
                print("expand failed", fp, e)
            for root, _, fs in os.walk(sub):
                for x in fs:
                    files.append(os.path.join(root, x))
        elif f.lower().endswith((".bin", ".fw", ".image")):
            files.append(fp)
    print("candidate binaries:", len(files))
    for fp in files:
        ext = os.path.splitext(fp)[1].lower()
        try:
            analyze(fp)
        except Exception as e:
            print("ERR", fp, e)

if __name__ == "__main__":
    main()
