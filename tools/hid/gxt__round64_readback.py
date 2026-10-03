#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND64 - 用官方 HID 协议【只读】回读 GT7868Q 参数区
====================================================
协议完全复刻 gdix_hid_firmware_update (Apache-2.0):
  GTx5Device::ReadPkg()  ->  发 [0e 20 00 00 05 01 addrH addrL lenH lenL]
                          ->  GetReport(0x0e) 取回 [.. .. .. pkgidx .. datalen data...]
  GTx5Device::Write(buf, len) 前置 0x0E, HIDIOCSFEATURE(=Windows: HidD_SetFeature)

安全等级: ★ 纯只读。不发任何 0x00 0x10 / 0x00 0x11 / 0x0E 0x12 命令。
"""
import hid
import struct
import sys
import time

GOODIX_VID = 0x27C6
GOODIX_PID = 0x01E9

_I2C_DIRECT_RW = 0x20
GDIX_RETRY_TIMES = 6
REPORT_ID = 0x0E
OUT_REPORT_SIZE = 65

# 官方常量
CFG_FLASH_ADDR = 0x19000
CFG_START_ADDR = 0x96F8
VER_ADDR = 0x4014

# 我们逆向得出的参数区布局 (ROUND47-59)
PARAM_REGIONS = [
    (0x0444, 1, "标定/属性字节"),
    (0x1800, 27, "★ 触觉参数区 (27B)"),
    (0x2000, 1092, "配置块 A"),
    (0x2444, 1, "标定/属性字节"),
    (0x2C00, 1092, "配置块 B"),
    (0x3044, 1, "标定/属性字节"),
    (0x3800, 8, "★ 触觉参数区 (8B)"),
]


def hexdump(b, base=0, width=16):
    out = []
    for i in range(0, len(b), width):
        chunk = b[i:i + width]
        hx = " ".join(f"{x:02X}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        out.append(f"    {base+i:04X}: {hx:<{width*3}} |{asc}|")
    return "\n".join(out)


class Dev:
    def __init__(self, path):
        self.h = hid.device()
        self.h.open_path(path)
        self.h.set_nonblocking(0)
        # 先尝试拿 feature report 数量信息
        self.ok = True

    def close(self):
        try:
            self.h.close()
        except Exception:
            pass

    def send_feature(self, buf, size=OUT_REPORT_SIZE):
        """对应 GTx5Device::Write(const unsigned char*, len) ：首字节强制 0x0E"""
        tmp = bytearray(size)
        tmp[0] = 0x0E
        tmp[1:1 + len(buf)] = buf
        # Windows 下 HidD_SetFeature 需要带 report id
        payload = bytes(tmp)
        self.h.send_feature_report(payload)
        return 0

    def get_report(self, report_id=REPORT_ID, size=OUT_REPORT_SIZE):
        try:
            return self.h.get_feature_report(report_id, size)
        except Exception as e:
            return None

    def read_pkg(self, addr, length):
        """复刻 GTx5Device::ReadPkg"""
        HidBuf = bytearray(OUT_REPORT_SIZE)
        HidBuf[0] = 0x0E
        HidBuf[1] = _I2C_DIRECT_RW
        HidBuf[2] = 0
        HidBuf[3] = 0
        HidBuf[4] = 5
        HidBuf[5] = 1          # read operation flag
        HidBuf[6] = (addr >> 8) & 0xFF
        HidBuf[7] = addr & 0xFF
        HidBuf[8] = (length >> 8) & 0xFF
        HidBuf[9] = length & 0xFF
        self.h.send_feature_report(bytes(HidBuf[:10]) + bytes(OUT_REPORT_SIZE - 10))

        out = bytearray()
        retry = 0
        pkg_index = 0
        read_len = 0
        deadline = time.time() + 2.0
        while read_len != length and retry < GDIX_RETRY_TIMES and time.time() < deadline:
            r = self.get_report()
            if r is None:
                return None
            if len(r) < 6:
                return None
            if r[3] != pkg_index:
                retry += 1
                time.sleep(0.002)
                continue
            if r[4] == length - read_len:
                out += bytes(r[5:5 + r[4]])
                read_len += r[4]
                pkg_index += 1
            else:
                retry += 1
                time.sleep(0.001)
        if read_len != length:
            return None
        return bytes(out)


def main():
    print("=" * 82)
    print("ROUND64 GT7868Q 参数区【只读】回读  (官方 I2C_DIRECT_RW 协议)")
    print("=" * 82)

    devs = [d for d in hid.enumerate() if d.get("vendor_id") == GOODIX_VID
            and d.get("product_id") == GOODIX_PID]
    col04 = [d for d in devs if d.get("usage_page") == 0xFF00]
    if not col04:
        print("!! 找不到 COL04"); return 1
    path = col04[0]["path"]
    print(f"目标: {path}\n")

    dev = Dev(path)
    results = {}

    # --- 1. 读 CFG_START_ADDR (0x96F8) 3 字节 = config 版本 ---
    print("[1] CFG_START_ADDR = 0x96F8, 读 3B (config 版本)")
    v = dev.read_pkg(CFG_START_ADDR, 3)
    if v:
        print(f"    -> {v.hex(' ').upper()}")
        results["cfg_ver"] = v
    else:
        print("    -> 读取失败/超时")
    print()

    # --- 2. 读 VER_ADDR (0x4014) 32 字节 = 固件信息 ---
    print("[2] VER_ADDR = 0x4014, 读 32B (固件信息, 官方含校验和)")
    v = dev.read_pkg(VER_ADDR, 32)
    if v:
        print(hexdump(v, VER_ADDR))
        cs = sum(v[:-2]) & 0xFFFF
        stored = (v[-2] << 8) | v[-1]
        print(f"    校验和: 计算={cs:#06x} 存储={stored:#06x} "
              f"{'✅ 匹配' if cs == stored else '❌ 不匹配'}")
        pid = bytes(x for x in v[14:18] if x).decode("latin1")
        print(f"    PID@[14:18] = '{pid}'   sensorID@[27] = {v[27]}")
        print(f"    fw版本 major@[23]={v[23]}  minor@[24:26]={v[24]},{v[25]}")
        results["fw_info"] = v
    else:
        print("    -> 读取失败/超时")
    print()

    # --- 3. 读参数区 ---
    print("[3] 参数区回读 (★ = 触觉相关)")
    for off, ln, desc in PARAM_REGIONS:
        r = dev.read_pkg(off, ln)
        tag = "★" if "触觉" in desc else " "
        if r:
            print(f"  {tag} 0x{off:04X} ({ln}B) {desc}")
            print(hexdump(r, off))
            results[off] = r
        else:
            print(f"  {tag} 0x{off:04X} ({ln}B) {desc}  -> 读取失败/超时")
        print()

    dev.close()

    # --- 汇总 ---
    print("=" * 82)
    print("汇总")
    print("=" * 82)
    for k, v in results.items():
        if isinstance(k, int):
            print(f"  0x{k:04X} = {v.hex(' ').upper()}")
        else:
            print(f"  {k} = {v.hex(' ').upper()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
