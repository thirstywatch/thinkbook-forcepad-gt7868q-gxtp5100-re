"""EC 端口协议实测（读 / 同值回写测试 / 选择性写）

协议来源：BIOS 内 IhisiServicesSmm 反汇编实测（2026-09-28）
  读: out 0xD01=地址高 → out 0xD02=地址低 → in al, 0xD03
  写: out 0xD01=高; out 0xD02=低; out 0xD03=数据 → 重设地址 → in 0xD03 校验（不等则重试）
  收尾: 恢复 0xD01/0xD02 原值（固件自己就是这么做的）
EC 地址空间 = 0xC400 + 窗口偏移(0x000-0x2FF)
  签名: 0xC620/0xC621 = 5A/A5   ← 与内存窗口 +0x220/0x221 一致
  窗口: 0xFE0B0400 + 偏移

用法:
  --probe                 只读：签名 + 与内存窗口逐字节交叉比对（零风险）
  --read 0xC4B8           只读：读单个 16 位地址
  --noop-write 0xC4B8     安全测试：读原值 → 回写同值 → 校验 → 再读（不改变状态）
  --fake-lid 1|0          写 LIDF（0xC4B8）—— 真正改变状态，须显式确认
  --restore 0xC4B8:0x00   写回指定值（回退用）
"""
import ctypes, sys, time
from ctypes import wintypes

IOCTL_READ_PHYS = 0x222808
IOCTL_READ_IO8 = 0x222810
IOCTL_WRITE_IO8 = 0x222814
BASE_MEM = 0xFE0B0400
BASE_PORT = 0xC400


class PhysRw(ctypes.Structure):
    _fields_ = [("physicalAddress", ctypes.c_ulonglong), ("size", ctypes.c_uint32),
                ("access", ctypes.c_uint32), ("buffer", ctypes.c_ulonglong)]


class PortIo(ctypes.Structure):
    _fields_ = [("Port", ctypes.c_uint16), ("pad", ctypes.c_uint16), ("Value", ctypes.c_uint32)]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.DeviceIoControl.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]

h = k32.CreateFileW("\\\\.\\RwDrv", 0xC0000000, 0, None, 3, 0x80, None)
if not h or h == 0xFFFFFFFFFFFFFFFF:
    print("RwDrv 打不开 err=%d（先跑 prep-lidf-test.cmd）" % ctypes.get_last_error())
    sys.exit(1)


def mem_read(addr, n):
    b = (ctypes.c_ubyte * n)()
    r = PhysRw(addr, n, 0, ctypes.cast(b, ctypes.c_void_p).value)
    g = wintypes.DWORD(0)
    ok = k32.DeviceIoControl(h, IOCTL_READ_PHYS, ctypes.byref(r), ctypes.sizeof(r), None, 0,
                             ctypes.byref(g), None)
    return bytes(b) if ok else None


def r8(port):
    q = PortIo(port, 0, 0); g = wintypes.DWORD(0)
    k32.DeviceIoControl(h, IOCTL_READ_IO8, ctypes.byref(q), ctypes.sizeof(q),
                        ctypes.byref(q), ctypes.sizeof(q), ctypes.byref(g), None)
    return q.Value & 0xFF


def w8(port, val):
    q = PortIo(port, 0, val & 0xFF); g = wintypes.DWORD(0)
    return bool(k32.DeviceIoControl(h, IOCTL_WRITE_IO8, ctypes.byref(q), ctypes.sizeof(q), None, 0,
                                    ctypes.byref(g), None))


def ec_read(addr16, gap=0.0):
    """addr16 = 0xC400 + 偏移；gap = 读后小睡（防高频轮询 EC 状态机）"""
    s1, s2 = r8(0xD01), r8(0xD02)
    w8(0xD01, (addr16 >> 8) & 0xFF)
    w8(0xD02, addr16 & 0xFF)
    v = r8(0xD03)
    w8(0xD01, s1); w8(0xD02, s2)
    if gap:
        time.sleep(gap)
    return v


def ec_write(addr16, data, retries=8):
    """与固件同序：设地址 → 写数据 → 重设地址 → 回读校验；最多 retries 次；收尾恢复"""
    s1, s2 = r8(0xD01), r8(0xD02)
    ok = False
    for _ in range(retries):
        w8(0xD01, (addr16 >> 8) & 0xFF)
        w8(0xD02, addr16 & 0xFF)
        w8(0xD03, data & 0xFF)
        w8(0xD01, (addr16 >> 8) & 0xFF)
        w8(0xD02, addr16 & 0xFF)
        if r8(0xD03) == (data & 0xFF):
            ok = True
            break
        time.sleep(0.01)
    w8(0xD01, s1); w8(0xD02, s2)
    return ok


def sig_check():
    a = ec_read(0xC620); b = ec_read(0xC621)
    return a, b, (a == 0x5A and b == 0xA5)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return
    mode = args[0]

    if mode == "--probe":
        a, b, ok = sig_check()
        print("签名: 0xC620=0x%02X 0xC621=0x%02X  %s" % (a, b, "✔ 与预期 5A/A5 一致" if ok else "✘ 不符"))
        mem = mem_read(BASE_MEM, 0x300)
        if mem is None:
            print("内存窗口读取失败"); return
        print("\n逐字节交叉比对（端口 0xC400+off  vs  内存 0xFE0B0400+off）：")
        seg = {}          # 高字节 -> [same, diff, zero]
        diffs = []
        for off in range(0x00, 0x300):
            pv = ec_read(BASE_PORT + off, gap=0.001)
            seg.setdefault(off >> 8, [0, 0, 0])
            if pv == mem[off]:
                seg[off >> 8][0] += 1
            else:
                seg[off >> 8][1] += 1
                if len(diffs) < 24:
                    diffs.append((off, pv, mem[off]))
            if pv == 0 and mem[off] == 0:
                seg[off >> 8][2] += 1

        for hi in sorted(seg):
            s, d, z = seg[hi]
            print("   0xC%Xxx : 一致 %3d / 不一致 %3d / 双零 %3d" % (hi, s, d, z))
        if diffs:
            print("\n   前若干不一致点（off / 端口值 / 内存值）：")
            for off, pv, mv in diffs:
                print("     off 0x%03X: 端口=0x%02X 内存=0x%02X" % (off, pv, mv))

        same = sum(v[0] for v in seg.values()); diff = sum(v[1] for v in seg.values())
        zero = sum(v[2] for v in seg.values())
        print("\n   合计：一致 %d / 768   不一致 %d   双方均 0 的字节 %d" % (same, diff, zero))
        print("   结论：%s" % ("端口路径与内存窗口指向同一 EC 空间 ✔" if diff < 40
                              else "存在差异 —— 看上面分段，通常只有一段有效"))

    elif mode == "--read":
        addr = int(args[1], 16)
        print("0x%04X = 0x%02X" % (addr, ec_read(addr)))

    elif mode == "--noop-write":
        addr = int(args[1], 16)
        orig = ec_read(addr)
        ok = ec_write(addr, orig)
        back = ec_read(addr)
        print("地址 0x%04X：原值 0x%02X → 同值回写 %s → 再读 0x%02X  %s"
              % (addr, orig, "成功" if ok else "失败", back,
                 "状态未变 ✔" if back == orig else "★ 值发生变化，需人工确认"))

    elif mode == "--fake-lid":
        val = int(args[1])
        off = 0x0B8
        addr = BASE_PORT + off
        before = ec_read(addr)
        newv = (before & ~0x02) | (0x02 if val else 0x00)
        print("LIDF 字节 0x%04X: 0x%02X (bit1=%d) → 目标 0x%02X (bit1=%d)"
              % (addr, before, (before >> 1) & 1, newv, val))
        ok = ec_write(addr, newv)
        after = ec_read(addr)
        print("写入 %s；读回 0x%02X (bit1=%d)" % ("成功" if ok else "失败", after, (after >> 1) & 1))
        print("⚠️ 若已生效，Windows 会按\"合盖策略\"动作 —— 请确认已把合盖动作设为「不采取任何操作」")
        print("   回退命令： python ec_port_rw.py --restore 0xC4B8:0x%02X" % before)

    elif mode == "--restore":
        spec = args[1]
        addr_s, val_s = spec.split(":")
        addr = int(addr_s, 16); val = int(val_s, 16)
        print("写回 0x%04X = 0x%02X → %s（读回 0x%02X）"
              % (addr, val, "成功" if ec_write(addr, val) else "失败", ec_read(addr)))

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
