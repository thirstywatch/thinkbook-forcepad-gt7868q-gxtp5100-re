"""LIDF 连拍验证：在时间窗口内高频快照 EC 窗口，找出随盖子开合变化的字节。
用法: python lidf_capture.py [总秒数=40] [间隔秒=0.5]
纯只读（RwDrv 读物理内存 0xFE0B0400），无任何写操作。
用法约定：启动后立即执行【合上盖子 -> 默数3秒 -> 打开盖子】。
"""
import ctypes, sys, time, os, struct
from ctypes import wintypes

IOCTL_READ_PHYS = 0x222808
BASE, N = 0xFE0B0400, 0x300

class PhysRw(ctypes.Structure):
    _fields_ = [("physicalAddress", ctypes.c_ulonglong), ("size", ctypes.c_uint32),
                ("access", ctypes.c_uint32), ("buffer", ctypes.c_ulonglong)]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.DeviceIoControl.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]

h = k32.CreateFileW("\\\\.\\RwDrv", 0xC0000000, 0, None, 3, 0x80, None)
if not h or h == 0xFFFFFFFFFFFFFFFF:
    print("RwDrv 打不开 err=%d —— 先跑 prep-lidf-test.cmd" % ctypes.get_last_error()); sys.exit(1)

def rd():
    b = (ctypes.c_ubyte * N)()
    r = PhysRw(BASE, N, 0, ctypes.cast(b, ctypes.c_void_p).value)
    g = wintypes.DWORD(0)
    ok = k32.DeviceIoControl(h, IOCTL_READ_PHYS, ctypes.byref(r), ctypes.sizeof(r),
                             None, 0, ctypes.byref(g), None)
    return bytes(b) if ok else None

TOTAL = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
IV = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
frames = []
t0 = time.time()
print("开始连拍 %.0f 秒 / 间隔 %.1f 秒 —— 现在执行：合上盖子(等3秒) -> 打开盖子" % (TOTAL, IV))
while time.time() - t0 < TOTAL:
    d = rd()
    if d is None:
        print("  第%d帧 读取失败" % len(frames))
    else:
        frames.append(d)
    time.sleep(IV)
k32.CloseHandle(h)
NF = len(frames)
print("完成：%d 帧" % NF)
if NF < 8:
    print("帧太少，实验作废"); sys.exit(1)

# 存档
ts = time.strftime("%Y%m%d-%H%M%S")
outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ec-lid-snaps", "capture-" + ts)
os.makedirs(outdir, exist_ok=True)
for i, f in enumerate(frames):
    open(os.path.join(outdir, "frame_%03d.bin" % i), "wb").write(f)
print("帧已存档 -> %s" % os.path.normpath(outdir))

# ---- LIDF 专项 ----
print("\n=== LIDF (0x0B8 bit1) 时间线 ===")
seq = [(f[0x0B8] >> 1) & 1 for f in frames]
print("  " + "".join(str(x) for x in seq))
b8 = [f[0x0B8] for f in frames]
print("  字节0x0B8: " + " ".join("%02X" % v for v in b8))

# ---- 全字节扫描：开->合->开 单段模式 ----
first, last = frames[0], frames[-1]
cands = []
for off in range(N):
    v0, vL = first[off], last[off]
    if v0 != vL:
        continue  # 漂移字节（温度类），跳过
    # 找 与基线不同的 连续段
    runs = []
    cur = None
    for i in range(NF):
        if frames[i][off] != v0:
            if cur is None: cur = [i, i]
            else: cur[1] = i
        else:
            if cur is not None: runs.append(cur); cur = None
    if cur is not None: runs.append(cur)
    good = [r for r in runs if r[1] - r[0] + 1 >= 2]   # 至少持续 2 帧
    if 1 <= len(good) <= 2 and good[0][0] >= 1 and good[-1][1] <= NF - 2:
        cands.append((off, v0, frames[good[0][0]][off], good[0], len(good)))

print("\n=== 『开->合->开』模式候选字节：%d 个 ===" % len(cands))
for off, v0, vm, (s, e), nep in sorted(cands, key=lambda x: -(x[3][1] - x[3][0])):
    flips = [j for j in range(8) if (v0 ^ vm) >> j & 1]
    note = "  <<< LIDF!" if off == 0x0B8 else ""
    print("  0x%03X: 0x%02X -> 0x%02X -> 0x%02X  首段: 帧%d..%d/%d  段数=%d  位翻转:%s%s"
          % (off, v0, vm, v0, s, e, NF, nep, flips, note))
if not cands:
    print("  （无 —— 盖子动作可能发生在窗口之外，或状态位在别处）")

# ---- 漂移字节（首尾不同）----
drift = [(off, first[off], last[off]) for off in range(N) if first[off] != last[off]]
print("\n=== 漂移字节（首尾不同，温度/计时类）：%d 个 ===" % len(drift))
for off, a, b in drift[:30]:
    print("  0x%03X: 0x%02X -> ... -> 0x%02X" % (off, a, b))
