"""厂商内存窗口抽样 vs 容器镜像：判断 16 位地址窗口里是不是 flash 内容。
零写入。抽 64 个 32 字节样本（步长 0x400），每个样本在容器里搜精确匹配。"""
import os, sys, time, collections, math

sys.path.insert(0, r"<LAB>\touchpad-lab\poc")
from gxhid import GxChannel, hx, asc, health

D = r"<WORKSPACE>"
cont = open(os.path.join(D, "touchpad_GT7868Q_fw.bin"), "rb").read()
LOG = r"<LAB>\touchpad-lab\poc\window-vs-container-log.txt"

def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())

_lines = []
def W(s):
    print(s, flush=True)
    _lines.append(s)

W("=== 厂商内存窗口抽样 vs 容器 :: 零写入 ===")
ch = GxChannel()
ok, info = ch.open()
W("Col04 open: %s" % ok)
if not ok:
    sys.exit(1)
hok, d = health(ch)
W("健康门 0x4018 :: %s [%s]" % (hx(d), asc(d)))
if not hok:
    W("ABORT"); ch.close(); sys.exit(2)

hits = []
samples = []
for k, addr in enumerate(range(0x0000, 0x10000, 0x400)):
    d, lg = ch.read(addr, 32)
    time.sleep(0.6)
    if d is None or len(d) < 32:
        samples.append((addr, None))
        W("  0x%04X  <读失败> %s" % (addr, lg))
        continue
    samples.append((addr, d))
    # 精确匹配（跳过平凡样本）
    uniq = len(set(d))
    m = []
    if uniq > 2:
        i = cont.find(d)
        while i >= 0:
            m.append(i)
            i = cont.find(d, i + 1)
    flag = ("★ 容器偏移 " + ",".join("0x%X" % x for x in m[:4])) if m else ""
    if m:
        hits.append((addr, m))
    W("  0x%04X  %s  H=%.2f %s" % (addr, hx(d), ent(d), flag))
    if (k + 1) % 16 == 0:
        hok2, d2 = health(ch)
        W("    [健康 @%d] 0x4018=%s %s" % (k + 1, hx(d2), "OK" if hok2 else "★FAIL"))
        if not hok2:
            W("    ❌ 健康检查失败，终止")
            break

W("")
W("--- 汇总 ---")
W("  抽样 %d 个地址，命中容器 %d 个" % (len(samples), len(hits)))
if hits:
    for addr, offs in hits:
        W("    0x%04X -> 容器偏移 %s" % (addr, ", ".join("0x%X" % o for o in offs[:6])))
    # 偏移差是否恒定
    base = hits[0]
    W("  与首个命中比较地址-偏移差：")
    for addr, offs in hits:
        W("    0x%04X  差 = %s" % (addr, ", ".join("%d" % (addr - o) for o in offs[:4])))
else:
    W("  ⇒ 窗口里没有容器镜像的任何字面数据（该窗口不是容器镜像的映射）")

hok3, d3 = health(ch)
W("")
W("收尾健康 0x4018 :: %s [%s]  %s" % (hx(d3), asc(d3), "✅" if hok3 else "⚠"))
ch.close()
W("完成（全程只读，零写入）。")

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(_lines) + "\n")
print("\n[log] " + LOG)
