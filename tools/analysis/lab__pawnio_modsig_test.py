#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pawnio_modsig_test.py -- PawnIO 模块签名策略判据（W2 路线的唯一门槛）

背景（《全书》§19.33.6）：
  W2 路线 = 自写一个 PawnIO 模块，用驱动原语
      pci_config_read_dword -> io_space_map -> virtual_read/write_dword
  直接驱动 Intel Serial IO I2C 控制器（0:15.0 = 8086:7E78）的 MMIO，
  从而在不关 HVCI、不改 ACPI、不用自己签驱动的前提下，把 I2C 事务发到 0x5A。

  唯一未知：PawnIO 驱动是否只接受"官方签名"的模块 blob。
  本脚本用最小模块 Echo.bin（2,284 B）做三组对照，2 分钟给出答案。

判据：
  A 原版 Echo.bin        加载成功  -> 环境正常（基线，必须成功）
  B 翻 1 bit 的副本      加载成功  -> ★ 不校验签名 => W2 立刻可行
                         加载失败  -> 需要走 PawnIO 官方模块提交流程
  C 随机字节 blob        加载失败  -> 说明失败原因确实是"格式/签名"而非权限

需要管理员运行（pawnio_open 无管理员会返回 0x80070005）。
用法:  python pawnio_modsig_test.py
"""
import ctypes
import os
import shutil
import sys
import tempfile

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "pawnio-modsig-result.txt")
_LOG_FH = None


def print(*a, **kw):  # noqa: A001  -- tee to file
    global _LOG_FH
    s = " ".join(str(x) for x in a)
    sys.__stdout__.write(s + kw.get("end", "\n"))
    sys.__stdout__.flush()
    if _LOG_FH is None:
        try:
            _LOG_FH = open(LOG_PATH, "w", encoding="utf-8", errors="replace")
        except OSError:
            return
    _LOG_FH.write(s + kw.get("end", "\n"))
    _LOG_FH.flush()

DLL_CANDIDATES = [
    r"C:\Program Files\PawnIO\PawnIOLib.dll",
    r"C:\Program Files (x86)\PawnIO\PawnIOLib.dll",
]
MOD_DIR_CANDIDATES = [
    r"<LAB>\touchpad-lab\pawnio\mod011",
    r"<LAB>\touchpad-lab",
]

FMT = "0x{:08X}"


def find(paths, name=None):
    for p in paths:
        if name:
            cand = os.path.join(p, name)
            if os.path.isfile(cand):
                return cand
        elif os.path.isfile(p):
            return p
    return None


def main():
    print("=" * 68)
    print(" PawnIO 模块签名策略判据  (W2 门槛测试)")
    print("=" * 68)

    dll = find(DLL_CANDIDATES)
    if not dll:
        print("[X] 找不到 PawnIOLib.dll")
        return 1
    echo = find(MOD_DIR_CANDIDATES, "Echo.bin")
    if not echo:
        print("[X] 找不到 Echo.bin")
        return 1
    print(f"  DLL : {dll}")
    print(f"  MOD : {echo}  ({os.path.getsize(echo)} B)")

    lib = ctypes.WinDLL(dll)
    lib.pawnio_open.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    lib.pawnio_open.restype = ctypes.c_long
    lib.pawnio_load.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.pawnio_load.restype = ctypes.c_long
    lib.pawnio_execute.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    lib.pawnio_execute.restype = ctypes.c_long
    lib.pawnio_close.argtypes = [ctypes.c_void_p]
    lib.pawnio_close.restype = ctypes.c_long

    ver = ctypes.c_ulong(0)
    lib.pawnio_version.argtypes = [ctypes.POINTER(ctypes.c_ulong)]
    lib.pawnio_version.restype = ctypes.c_long
    hr = lib.pawnio_version(ctypes.byref(ver))
    print(f"  pawnio_version -> {FMT.format(hr & 0xFFFFFFFF)}  "
          f"v{(ver.value >> 16) & 0xFF}.{(ver.value >> 8) & 0xFF}.{ver.value & 0xFF}")

    h = ctypes.c_void_p()
    hr = lib.pawnio_open(ctypes.byref(h))
    print()
    print(f"[0] pawnio_open -> {FMT.format(hr & 0xFFFFFFFF)}")
    if hr != 0:
        print("    [!] 打开失败。0x80070005 = 权限不足 => 请用【管理员】身份重跑本脚本。")
        return 2
    print("    ok（驱动已在跑，说明本机 PawnIO 环境正常）")

    src = open(echo, "rb").read()

    def try_load(tag, blob):
        hh = ctypes.c_void_p()
        if lib.pawnio_open(ctypes.byref(hh)) != 0:
            print(f"    {tag}: 无法新建 executor")
            return None
        buf = ctypes.create_string_buffer(blob, len(blob))
        r = lib.pawnio_load(hh, ctypes.cast(buf, ctypes.c_char_p), len(blob))
        lib.pawnio_close(hh)
        return r

    print()
    print("-" * 68)
    print(" A) 原版 Echo.bin（基线）")
    ra = try_load("A", src)
    print(f"    pawnio_load -> {FMT.format(ra & 0xFFFFFFFF)}   "
          f"{'加载成功' if ra == 0 else '加载失败'}")

    # B) 翻 1 bit
    b = bytearray(src)
    flipped = len(b) // 2
    b[flipped] ^= 0x01
    print("-" * 68)
    print(f" B) 翻 1 bit 的副本（offset {flipped}: "
          f"{src[flipped]:02X} -> {b[flipped]:02X}）")
    rb = try_load("B", bytes(b))
    print(f"    pawnio_load -> {FMT.format(rb & 0xFFFFFFFF)}   "
          f"{'加载成功' if rb == 0 else '加载失败'}")

    # B2) 只改尾部（避开可能的签名区）
    b2 = bytearray(src)
    b2[-1] ^= 0xFF
    print("-" * 68)
    print(f" B2) 只改最后一字节（offset {len(b2)-1}: "
          f"{src[-1]:02X} -> {b2[-1]:02X}）")
    rb2 = try_load("B2", bytes(b2))
    print(f"    pawnio_load -> {FMT.format(rb2 & 0xFFFFFFFF)}   "
          f"{'加载成功' if rb2 == 0 else '加载失败'}")

    # C) 随机 blob（对照）
    print("-" * 68)
    print(" C) 纯随机字节（对照，理应失败）")
    rc = try_load("C", bytes(len(src)))
    print(f"    pawnio_load -> {FMT.format(rc & 0xFFFFFFFF)}   "
          f"{'加载成功(意外!)' if rc == 0 else '加载失败(符合预期)'}")

    lib.pawnio_close(h)

    print()
    print("=" * 68)
    print(" 结论")
    print("=" * 68)
    if ra != 0:
        print("  基线失败 => 不是签名问题，是环境/权限问题，先解决 A。")
    elif rb == 0 or rb2 == 0:
        print("  ★★★ A 成功 且 B/B2 成功 => PawnIO 【不校验】模块签名")
        print("      => W2 路线立刻可行：可以自己写 IntelSerialIOI2C 模块。")
    else:
        print("  A 成功但 B/B2 失败 => PawnIO 【校验】模块（签名或完整性）")
        print("      => W2 需走官方模块提交流程（或先查驱动是否有开发模式）。")
        print(f"      B 的返回码 = {FMT.format(rb & 0xFFFFFFFF)}（可据此查 PawnIO 错误码表）")
    print()
    print(" 请把上面全部输出发回。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
