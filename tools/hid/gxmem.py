# -*- coding: utf-8 -*-
"""gxmem.py — Python 版 Gx.cs（厂商内存通道）+ 动态测绘

为什么重写：
  aligned-read-log.txt 证明 C# 版 Gx.Read 在本机 11/11 成功。
  而 poc/col04_io.py 用 ReadFile(重叠) 收响应 -> 全部 timeout。
  => 响应【不是】异步输入报文，而是对 IOCTL_HID_GET_INPUT_REPORT 的同步应答。
  => 必须用 HidD_GetInputReport 收（照抄 Gx.cs 的 Recv()）。

协议（与 poc/Gx.cs 完全一致）：
  读: 0E 20 00 00 05 01 <addr16BE> <size16BE>        -> HidD_SetOutputReport(h, buf, 65)
  写: 0E 20 00 00 <len+5> 00 <addr16BE> <len16BE> <data...>
  响应: 0E 20 <cont> <seq> <len> <data...>          <- HidD_GetInputReport(h, buf, 65)

用法：
  python gxmem.py selftest               # 验证通道（读 0x4000，期望 A7 E0 ED B1）
  python gxmem.py read <addr> [size]     # 单次读
  python gxmem.py snap <start> <end> <step> <outfile>   # 快照一段（step 字节一跳）
  python gxmem.py diff <a.bin> <b.bin> <base_addr> <step>  # 比对两份快照
"""
import ctypes, sys, os, time, json
from ctypes import wintypes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID = ctypes.c_void_p(-1).value
COL04 = ("\\\\?\\HID#GXTP5100&Col04#5&52a7aed&0&0003#"
         "{4d1e55b2-f16f-11cf-88cb-001111000030}")

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
hid = ctypes.WinDLL('hid', use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
hid.HidD_SetOutputReport.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_SetOutputReport.restype = wintypes.BOOLEAN
hid.HidD_GetInputReport.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_GetInputReport.restype = wintypes.BOOLEAN


class Gx:
    def __init__(self):
        self.h = None

    def open(self):
        self.h = k32.CreateFileW(COL04, GENERIC_READ | GENERIC_WRITE,
                                 FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                                 OPEN_EXISTING, 0, None)
        return bool(self.h) and self.h != INVALID

    def close(self):
        if self.h:
            k32.CloseHandle(self.h)
            self.h = None

    def _send(self, pkt):
        b = ctypes.create_string_buffer(65)
        n = min(len(pkt), 65)
        ctypes.memmove(b, bytes(pkt[:n]), n)
        ctypes.memmove(b, bytes([0x0E]), 1)      # b[0] = RID
        return bool(hid.HidD_SetOutputReport(self.h, ctypes.cast(b, ctypes.c_void_p), 65))

    def _recv(self):
        r = ctypes.create_string_buffer(65)
        ctypes.memmove(r, bytes([0x0E]), 1)
        ok = hid.HidD_GetInputReport(self.h, ctypes.cast(r, ctypes.c_void_p), 65)
        return bytes(r.raw) if ok else None

    def read(self, addr, size, rounds=12, delay=0.06):
        """16 位地址读。返回 (data|None, log)"""
        pkt = [0x0E, 0x20, 0x00, 0x00, 0x05, 0x01,
               (addr >> 8) & 0xFF, addr & 0xFF,
               (size >> 8) & 0xFF, size & 0xFF]
        if not self._send(pkt):
            return None, "send-fail"
        acc = bytearray()
        log = []
        for _ in range(rounds):
            time.sleep(delay)
            r = self._recv()
            if r is None:
                log.append("recv-fail")
                break
            cont, seq, ln = r[2], r[3], r[4]
            log.append("[c%d st%d len%d]" % (cont, seq, ln))
            ln = min(ln, 60)
            acc += r[5:5 + ln]
            if cont == 0:
                break
        if not acc:
            return None, " ".join(log)
        out = bytes(acc[:size]) if size else bytes(acc)
        return out, " ".join(log)

    def write(self, addr, data):
        """★ 危险：写设备内存。len 字段官方是 len+5（2026-09-29 修正）"""
        data = bytes(data)
        pkt = [0x0E, 0x20, 0x00, 0x00, (len(data) + 5) & 0xFF, 0x00,
               (addr >> 8) & 0xFF, addr & 0xFF,
               (len(data) >> 8) & 0xFF, len(data) & 0xFF] + list(data)
        ok = self._send(pkt)
        return ok


def hx(d, per=32):
    if not d:
        return "<null>"
    return " ".join("%02X" % b for b in d)


def cmd_selftest():
    g = Gx()
    if not g.open():
        print("Col04 open FAILED err=%d" % ctypes.get_last_error())
        return 1
    print("Col04 open ok\n")
    tests = [
        (0x4000, 4, "liveness (期望 A7 E0 ED B1)"),
        (0x452C, 4, "fw_info (期望 AE EB 22 90)"),
        (0x96F8, 4, "配置区 (期望 22 01 1B 00)"),
        (0x4000, 16, "liveness 16B"),
        (0x4000, 64, "liveness 64B"),
        (0x96F8, 256, "配置区 256B"),
    ]
    ok = 0
    for addr, sz, lbl in tests:
        d, log = g.read(addr, sz)
        print("  0x%05X x%-4d %-28s :: %s" % (addr, sz, lbl, hx(d[:16]) if d else "<FAIL>"))
        print("        log=%s" % log)
        if d:
            ok += 1
        time.sleep(0.05)
    print("\n成功 %d / %d" % (ok, len(tests)))
    g.close()
    return 0


def cmd_read(addr, size):
    g = Gx()
    if not g.open():
        print("open FAILED err=%d" % ctypes.get_last_error())
        return 1
    d, log = g.read(addr, size)
    print("read(0x%04X, %d) -> %s" % (addr, size, hx(d) if d else "<FAIL>"))
    print("log=%s" % log)
    g.close()
    return 0


def cmd_snap(start, end, step, outfile):
    g = Gx()
    if not g.open():
        print("open FAILED err=%d" % ctypes.get_last_error())
        return 1
    addrs = list(range(start, end, step))
    print("snapshot %d 个地址 (0x%X..0x%X step=%d) ..." % (len(addrs), start, end, step))
    data = {}
    bad = 0
    t0 = time.time()
    for i, a in enumerate(addrs):
        d, _ = g.read(a, step)
        if d:
            data[a] = d.hex()
        else:
            bad += 1
            data[a] = None
        if (i + 1) % 64 == 0:
            print("  %d/%d  (%.1fs, fail=%d)" % (i + 1, len(addrs), time.time() - t0, bad))
    g.close()
    with open(outfile, "w") as f:
        json.dump({"start": start, "end": end, "step": step,
                   "t": time.time(), "data": {str(k): v for k, v in data.items()}}, f)
    print("saved %s  (%.1fs, fail=%d/%d)" % (outfile, time.time() - t0, bad, len(addrs)))
    return 0


def cmd_diff(a, b, base, step):
    with open(a) as f:
        A = json.load(f)
    with open(b) as f:
        B = json.load(f)
    da, db = A["data"], B["data"]
    common = [k for k in da if k in db and da[k] and db[k]]
    diffs = []
    for k in sorted(common, key=lambda x: int(x)):
        if da[k] != db[k]:
            diffs.append((int(k), da[k], db[k]))
    print("共同可比地址 %d 个，其中 %d 个发生变化" % (len(common), len(diffs)))
    for addr, x, y in diffs[:80]:
        print("  0x%05X  A=%s  B=%s" % (addr, x, y))
    if len(diffs) > 80:
        print("  ... 还有 %d 个" % (len(diffs) - 80))
    return 0


def cmd_dump(start, length, outfile, chunk=256, delay=0.05, retries=4):
    """大块连续 dump。★ 实测：256B/次连读太快会让设备卡住(读失败)，
       必须加 delay + 失败重试；失败块位置记到 <outfile>.bad"""
    g = Gx()
    if not g.open():
        print("open FAILED err=%d" % ctypes.get_last_error())
        return 1
    buf = bytearray()
    bad = []
    t0 = time.time()
    for base in range(start, start + length, chunk):
        d = None
        for att in range(retries):
            d, _ = g.read(base, chunk)
            if d and len(d) == chunk:
                break
            time.sleep(0.2)
            d = None
        if d:
            buf += d
        else:
            bad.append(base)
            buf += b'\x00' * chunk
        time.sleep(delay)
    g.close()
    with open(outfile, "wb") as f:
        f.write(buf)
    if bad:
        with open(outfile + ".bad", "w") as f:
            f.write("\n".join("0x%05X" % b for b in bad))
    print("dump 0x%05X .. 0x%05X  -> %s  (%d B, %.1fs, 失败块 %d)"
          % (start, start + length, outfile, len(buf), time.time() - t0, len(bad)))
    if bad:
        print("  失败块: %s" % " ".join("0x%05X" % b for b in bad[:20]))
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 0
    mode = sys.argv[1]
    if mode == "selftest":
        return cmd_selftest()
    if mode == "read":
        addr = int(sys.argv[2], 0)
        size = int(sys.argv[3], 0) if len(sys.argv) > 3 else 4
        return cmd_read(addr, size)
    if mode == "snap":
        start = int(sys.argv[2], 0); end = int(sys.argv[3], 0)
        step = int(sys.argv[4], 0); out = sys.argv[5]
        return cmd_snap(start, end, step, out)
    if mode == "diff":
        return cmd_diff(sys.argv[2], sys.argv[3],
                        int(sys.argv[4], 0) if len(sys.argv) > 4 else 0,
                        int(sys.argv[5], 0) if len(sys.argv) > 5 else 4)
    if mode == "dump":
        start = int(sys.argv[2], 0)
        length = int(sys.argv[3], 0)
        out = sys.argv[4]
        return cmd_dump(start, length, out)
    print("unknown mode")
    return 1


if __name__ == "__main__":
    sys.exit(main())
