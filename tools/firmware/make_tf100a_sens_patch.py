#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TF100A 灵敏度补丁「40 → N」生成器（★ 本项目唯一剩下的可行路径，§19.38.2）

是什么
------
TF100A 的震动判据是两条 Thumb-2 指令里的**立即数 0x28（=40）**：

    0x08005A90 (file 0x1A54C)  28 31      adds r1, #0x28      ; 后随 88 42 = cmp r0,r1
    0x08005ABC (file 0x1A578)  28 39      subs r1, #0x28      ; 后随 88 42 = cmp r0,r1

判据形如 |基线 − 当前| > 40。把 40 改小（例如 8）⇒ 判据变灵敏
⇒ 滑动时手指压力的天然波动会反复跨过判据 ⇒ 反复触发点按链路
⇒ **滑动震动**（设备自发，完全不碰主机协议）。

⚠️ 为什么只改这两处
--------------------
段内 `28 31` 另有 2 处、`28 39` 另有 3 处 —— **都不能动**。本脚本按
【绝对文件偏移 + 后随 2 字节必须为 88 42】双重校验，校验不通过即拒绝写盘。

⚠️ 已知不确定项（抄自 §19.38.2 (3)，刷之前必读）
------------------------------------------------
1. 数值 8 未必一次到位（基线更新速度可能抵消；可用 16 / 24 做梯度）。
2. **副作用预警：假点击** —— 滑动可能被判为点击（判据联动）。
3. 「运行期马达门控未定位」是 09-29 旧悬案，不影响本改动的逻辑。
4. 要让 TF 子系统被重刷，**版本号必须变化**（`GTPCheckTFUpdate` 分别比对版本）。

🔴 红线
--------
本脚本**只做离线字节改写**，不刷写、不碰 HID、不碰 I²C。
刷写走 UEFI capsule + `GoodixTpDxe`（见 `docs/00-软件逆向全书…md` §19.38.4），
且必须先在料板上做「只改版本号、不动代码」的零风险预演。

用法
----
    python make_tf100a_sens_patch.py <原厂 BIN> [--sens 8] [--out 输出.BIN]
    python make_tf100a_sens_patch.py <原厂 BIN> --check          # 只校验不改
"""
import argparse
import hashlib
import os
import sys

# 加载基准：TF100A 运行基址 0x08005000 ↔ 文件偏移 0x19ABC
LOAD_BASE = 0x08005000
FILE_BASE = 0x19ABC

# 两处补丁点（文件绝对偏移）
PATCHES = [
    # (file_offset, 运行地址, 原助记符, 期望原字节, 期望后随字节)
    (0x1A54C, 0x08005A90, "adds r1, #0x28", bytes.fromhex("2831"), bytes.fromhex("8842")),
    (0x1A578, 0x08005ABC, "subs r1, #0x28", bytes.fromhex("2839"), bytes.fromhex("8842")),
]

EXPECTED_SIZE = 161628
KNOWN_ORIG_SHA = "0033d075fae88f0048544696c8941ed7dcca4269beaa84af76323ef5bbdcee72"
KNOWN_PATCH8_SHA = "f39f80e0766f2a6fb9242ed53302c00fd4e6a00313f4abbe94a91492f84fcb02"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def encode(new_val: int):
    """把立即数 N 编进两条 Thumb-2 指令的字节。
    adds r1,#imm  imm8 形式: 31 xx  -> 高 2 位固定，低 8 位 = imm
    subs r1,#imm  imm8 形式: 39 xx
    实测 0x28 -> 28 31 / 28 39，即 (imm<<8)|opcode 的 LE 排布：字节0=imm, 字节1=31/39
    """
    if not 0 <= new_val <= 0xFF:
        raise SystemExit(f"[!] 立即数必须落在 0..255，收到 {new_val}")
    return bytes([new_val, 0x31]), bytes([new_val, 0x39])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("binfile", help="原厂胶囊 BIN（例如 TB14P_GT7868Q_14030522_20240202.BIN）")
    ap.add_argument("--sens", type=int, default=8, help="新灵敏度值（默认 8；梯度可试 16/24）")
    ap.add_argument("--out", default=None, help="输出路径（默认 <原名>-sens40to<N>.BIN）")
    ap.add_argument("--check", action="store_true", help="只校验，不写盘")
    args = ap.parse_args()

    src = args.binfile
    if not os.path.isfile(src):
        sys.exit(f"[!] 找不到文件: {src}")

    raw = open(src, "rb").read()
    print(f"[i] 输入 : {src}")
    print(f"[i] 大小 : {len(raw)} B")
    print(f"[i] sha256: {sha256(raw)}")

    if len(raw) != EXPECTED_SIZE:
        print(f"[!] 大小不是 {EXPECTED_SIZE} B —— 这不是我们验过的那份镜像。")
        if input("    仍要继续？[y/N] ").strip().lower() != "y":
            sys.exit(1)
    if sha256(raw) == KNOWN_ORIG_SHA:
        print("[✓] sha256 与记录的原件一致")
    else:
        print("[!] sha256 与记录的原件不一致 —— 可能是另一个版本，务必人工确认偏移")

    # ── 逐点校验 ──
    out = bytearray(raw)
    enc_adds, enc_subs = encode(args.sens)
    plan = []
    for i, (off, addr, mn, want, tail) in enumerate(PATCHES):
        got = bytes(raw[off:off + 2])
        got_tail = bytes(raw[off + 2:off + 4])
        ok = (got == want) and (got_tail == tail)
        print(f"\n[{i}] file 0x{off:X}  (运行 0x{addr:08X})  {mn}")
        print(f"    原字节 {got.hex()}  后随 {got_tail.hex()}   {'✓ 符合预期' if ok else '✗ 不符合'}")
        if not ok:
            sys.exit(f"[!] 偏移 0x{off:X} 处的内容不是预期的 {want.hex()}{tail.hex()}，拒绝改写。")
        new = enc_adds if mn.startswith("adds") else enc_subs
        plan.append((off, got, new))
        print(f"    将改为 {new.hex()}  (= {mn.split('#')[0].strip()} r1, #0x{args.sens:X})")

    if args.check:
        print("\n[✓] 只校验模式：两处补丁点均符合预期，未写盘。")
        return

    for off, old, new in plan:
        out[off:off + 2] = new

    dst = args.out or (os.path.splitext(src)[0] + f"-sens40to{args.sens}.BIN")
    with open(dst, "wb") as f:
        f.write(bytes(out))

    h = sha256(bytes(out))
    print(f"\n[✓] 已写出: {dst}")
    print(f"[i] 大小  : {len(out)} B  (与原镜像一致: {len(out) == len(raw)})")
    print(f"[i] sha256: {h}")
    if args.sens == 8 and h == KNOWN_PATCH8_SHA:
        print("[✓] 与 §19.38.2 记录的 40→8 补丁 sha256 完全一致")
    print(f"\n[!] 回滚方案：原镜像**从未被改动**（只读）。回滚 = 用原件重刷。")
    print("[!] 刷写前必读本文件顶部「已知不确定项」与 docs/09-safety/RED-LINES.md")


if __name__ == "__main__":
    main()
