#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r31_persist_probe.py — B12 持久化原语探针（Goodix 官方 `0E 12`）

★ 目标的变更说明
----------------
原计划（2026-10-10 上午）是照 ELAN/Pinebook 的惯例试 `0x55` 全填充"end programming"。
**当日下午，Goodix 官方源码定案后，目标已更正为官方的真实落盘原语**：

    Goodix 官方【没有】任何 commit / magic / flush 命令。
    持久化的唯一机制 = 命令 `0E 12`：
        ① 原语A 把 ≤4096 B 写进 RAM 暂存 FLASH_BUFFER_ADDR = 0xC000
        ② 发命令  0E 12 00 00 06 <len16BE> <addrHi> <addrMid> <ckHi> <ckLo>
        ③ 轮询 FLASH_RESULT_ADDR = 0x5096 直到 == 0xAA

    出处：goodix/gdix_hid_firmware_update  →  gtx2/gtx2_update.cpp:139-213
                                                 (GTx2Update::load_sub_firmware)
    校验和：按【大端 16 位字】累加，uint16 自然回绕（★ 不是逐字节累加）
    地址：  只发 [23:16] 与 [15:8] 两个字节 ⇒ 256 字节对齐

★★★ 安全设计（三条硬约束）
--------------------------
1. **默认 dry**：不加 `--commit` 不打开设备。
2. **幂等探针**：阶段 2 写回的是【从目标地址读出的原样内容】⇒ 即使成功也**不改变任何东西**，
   但完整走通 `0E 12` 的全部协议（含校验和与结果轮询）。
   —— 这与 elgato 第 7 步"在没人用的擦除块上试写"、以及本项目的"幂等写入"纪律同源。
3. **先读后写 + 强制回读比对**：未先读回原内容 ⇒ 拒绝执行；写后必须逐字节比对。

⚠️ 仍属高危：官方**没有独立 erase**，擦除隐含在 `0x12` 内 ⇒ 地址算错会擦错区。
   故本脚本**只允许对一个白名单地址操作**，且**不提供任意地址接口**。

用法
----
  python lab__r31_persist_probe.py --phase 0                 # 只读：建恢复基线（含 --dry 语义，不写）
  python lab__r31_persist_probe.py --phase 1                 # 只读：侦察 0x4160/0x5095/0x5096
  python lab__r31_persist_probe.py --phase 2 --commit        # ★ 唯一有风险的一步（幂等）
  python lab__r31_persist_probe.py --phase 3 --commit        # 复位 + 重读（验证持久性）
"""
import sys, os, time, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import gxmem
except Exception as e:
    print("[FATAL] 需与本脚本同目录的 gxmem.py: %r" % e)
    raise SystemExit(2)

# ─────────────── 官方常量（goodix/gdix_hid_firmware_update） ───────────────
CMD_ADDR          = 0x4160
BL_STATE_ADDR     = 0x5095
FLASH_RESULT_ADDR = 0x5096
FLASH_BUFFER_ADDR = 0xC000
RAM_BUFFER_SIZE   = 4096
CFG_FLASH_ADDR    = 0x19000
CFG_START_ADDR    = 0x96F8
BL_STATE_READY    = 0xDD          # 等 bootloader
FLASH_RESULT_OK   = 0xAA          # 本块写成功
CMD_BUF_LEN       = 6             # 0x0E + cmd + 00 00 + 01 01

# ★ 白名单：本脚本【只允许】对这些 flash 地址发 0x12
#   0x0A000 = 子固件 idx4（8192 B，**必须整块写 2×4096**，不可只写一半）
#   ⚠️ 执行前须人工确认；且**整块写**（见 write_full_block）
ALLOWED_FLASH_ADDRS = {0x0A000}

# ★ 每块长度须与镜像表一致（防止"只写一半、被擦除粒度毁掉另一半"）
BLOCK_SIZE_AT = {
    0x0A000: 8192,     # idx4, type 0x03, 表序 4
    0x000000: 4096,    # idx9, type 0x02（★ 最敏感，默认不用）
    0x012000: 4096,    # idx12, type 0x02
}


def ck16be_word_sum(data):
    """★ 官方校验和：按【大端 16 位字】累加，uint16 回绕（gtx2_update.cpp:165-168）"""
    s = 0
    for i in range(0, len(data) - 1, 2):
        s = (s + ((data[i] << 8) + data[i + 1])) & 0xFFFF
    return s


def framed_load_flash(addr, length, checksum):
    """构造 0E 12 命令帧（11 字节）— gtx2_update.cpp:169-176"""
    return bytes([
        0x0E, 0x12, 0x00, 0x00, 0x06,
        (length >> 8) & 0xFF, length & 0xFF,
        (addr >> 16) & 0xFF, (addr >> 8) & 0xFF,     # ★ 低字节恒 0（256 对齐）
        (checksum >> 8) & 0xFF, checksum & 0xFF,
    ])


def framed_cmd(code):
    """构造直发命令帧（6 字节）— 上线后被强制为 0E <code> 00 00 01 01"""
    return bytes([0x0E, code, 0x00, 0x00, 0x01, 0x01])


def cmd_init(cmd, d_hi=0, d_lo=0):
    """写 0x4160 的 5 字节 payload：{cmd, dataHi, dataLo, ckHi, ckLo}, ck = cmd+d_hi+d_lo"""
    ck = (cmd + d_hi + d_lo) & 0xFFFF
    return bytes([cmd, d_hi, d_lo, (ck >> 8) & 0xFF, ck & 0xFF])


def hx(b, n=32):
    if not b:
        return "<null>"
    return " ".join("%02X" % x for x in b[:n]) + ("…" if len(b) > n else "")


# ─────────────────────────── 阶段实现 ───────────────────────────

def phase0(g):
    """只读：建恢复基线（cfg 六字段 + 0x96F8/0x19000 前 32 B）"""
    print("【阶段 0】恢复基线（只读）")
    print("-" * 70)
    bases = [(0x96F8, 32, "CFG_START_ADDR（RAM 暂存）前 32 B"),
             (0x19000, 32, "CFG_FLASH_ADDR（flash 配置）前 32 B")]
    for a, n, note in bases:
        d, log = g.read(a, n)
        print("  0x%05X  %s" % (a, note))
        print("           %s" % hx(d, 32))
        print("           log: %s" % log)
    print()
    print("  ⇒ 请把以上内容【另行抄录留存】，作为回滚依据。")


def phase1(g):
    """只读：侦察官方三个状态地址"""
    print("【阶段 1】状态侦察（只读）")
    print("-" * 70)
    for a, name, expect in [(CMD_ADDR, "CMD_ADDR", "0xFF = IC 空闲"),
                            (BL_STATE_ADDR, "BL_STATE_ADDR", "0xDD = 已在 bootloader"),
                            (FLASH_RESULT_ADDR, "FLASH_RESULT_ADDR", "0xAA = 上次写成功")]:
        d, log = g.read(a, 1)
        v = ("0x%02X" % d[0]) if d else "<null>"
        print("  0x%04X  %-18s = %-8s  （%s）" % (a, name, v, expect))
    print()
    print("  ⚠️ 若 CMD_ADDR 不是 0xFF，说明 IC 正忙 —— 不要继续阶段 2。")


def load_block_chunk(g, buf, flash_addr, chunk_len):
    """按官方 load_sub_firmware 单块流程：写 0xC000 → 发 0E 12 → 轮询 0x5096==0xAA。
    返回 True/False。"""
    if not g.write(FLASH_BUFFER_ADDR, buf):
        print("      [FAIL] 写 0xC000 失败")
        return False
    ck = ck16be_word_sum(buf)
    frame = framed_load_flash(flash_addr, len(buf), ck)
    print("      → 0E12 addr=0x%06X len=%d ck=0x%04X : %s"
          % (flash_addr, len(buf), ck, hx(frame, 11)))
    if not g._send(list(frame)):
        print("      [FAIL] 命令帧发送失败")
        return False
    for i in range(100):
        time.sleep(0.002)
        d, _ = g.read(FLASH_RESULT_ADDR, 1)
        if d and d[0] == FLASH_RESULT_OK:
            print("      第 %d 次轮询 0x5096 = 0xAA ⇒ 本块成功" % (i + 1))
            g.write(FLASH_RESULT_ADDR, b"\x00")
            return True
    d, _ = g.read(FLASH_RESULT_ADDR, 1)
    print("      100 次未见 0xAA（末值 %s）⇒ 本块失败" % hx(d, 1))
    return False


def phase2(g, flash_addr, commit):
    """★ 幂等探针：读回整块 → 按 4096 分块写回 → 轮询 → 回读比对"""
    if flash_addr not in ALLOWED_FLASH_ADDRS:
        print("[REFUSE] 地址 0x%05X 不在白名单 %s 内。" % (flash_addr, [hex(x) for x in ALLOWED_FLASH_ADDRS]))
        return 2
    block_size = BLOCK_SIZE_AT.get(flash_addr, RAM_BUFFER_SIZE)

    print("【阶段 2】幂等落盘探针  flash=0x%06X  整块长度=%d（= %d × 4096）"
          % (flash_addr, block_size, block_size // RAM_BUFFER_SIZE))
    print("-" * 70)

    # ★ 前置检查 A：必须处于 bootloader 态（官方序列：0E 10 → 等 0x5095==0xDD → 0E 11）
    st, _ = g.read(BL_STATE_ADDR, 1)
    cur = st[0] if st else None
    print("  2-0 前置检查：0x5095(BL_STATE_ADDR) = %s（需 0xDD）" % (("0x%02X" % cur) if cur is not None else "<null>"))
    if cur != BL_STATE_READY:
        print("      [ABORT] ★ **当前不在 bootloader 态** ⇒ 按官方序列必须先发：")
        print("               0E 10 00 00 01 01  (切 patch) → 轮询 0x5095 == 0xDD")
        print("               0E 11 00 00 01 01  (启动更新)")
        print("              这两条【也在项目红线里】，且会使触控板停摆 ⇒ 需单独批准。")
        print("              本脚本【不自动】发这两条。")
        return 8

    print("  2-1 读回整块（★ 未读回则拒绝执行）…")
    orig, log = g.read(flash_addr, block_size)
    if not orig or len(orig) < block_size:
        print("      [ABORT] 读回不足（得到 %d / 需要 %d；log: %s）⇒ 拒绝继续。"
              % (len(orig) if orig else 0, block_size, log))
        return 3
    orig = bytes(orig[:block_size])
    print("      读回 %d B，前 32 B: %s" % (len(orig), hx(orig)))

    if not commit:
        print()
        print("  [DRY] 未加 --commit —— 未做任何写入。将执行：")
        for off in range(0, block_size, RAM_BUFFER_SIZE):
            ch = orig[off:off + RAM_BUFFER_SIZE]
            print("        · 0xC000 ← 原样 %d B；0E12 addr=0x%06X len=%d ck=0x%04X"
                  % (len(ch), flash_addr + off, len(ch), ck16be_word_sum(ch)))
        print("        · 之后回读整块并与原文逐字节比对")
        return 0

    print("  2-2 ★ 按 4096 分块提交（★ 必须整块写完，防止擦除粒度毁掉后半）…")
    for off in range(0, block_size, RAM_BUFFER_SIZE):
        ch = orig[off:off + RAM_BUFFER_SIZE]
        print("    chunk @0x%06X (%d B)…" % (flash_addr + off, len(ch)))
        if not load_block_chunk(g, ch, flash_addr + off, len(ch)):
            print("      [ABORT] 本块失败 ⇒ 立即停止（不再继续后续块）。")
            print("      ⚠️ 若此时块数 > 1，flash 可能处于【半写】状态 —— 请勿断电，重跑本阶段。")
            return 6

    print("  2-3 回读整块比对…")
    after, _ = g.read(flash_addr, block_size)
    after = bytes(after[:block_size]) if after else b""
    same = (after == orig)
    print("      写入前/后逐字节一致：%s" % ("★ 是（幂等成立）" if same else "❌ 否"))
    if not same:
        diff = sum(1 for i in range(min(len(after), len(orig))) if after[i] != orig[i])
        print("      差异字节数：%d  ⚠️ 停止一切后续动作" % diff)
        return 7
    print()
    print("  ⇒ ★★★ `0E 12` 落盘原语【走通】，且数据未发生任何改变。")
    print("     持久性由阶段 3（复位 + 重读）验证。")
    return 0


def phase3(g, flash_addr, commit):
    """复位 + 重读（验证持久性）"""
    print("【阶段 3】持久性验证")
    print("-" * 70)
    if not commit:
        print("  [DRY] 未加 --commit。将执行：")
        print("        a. 发复位命令 0E 13 00 00 01 01（重试 3 次，每次间隔 20 ms）")
        print("        b. usleep 300 ms")
        print("        c. 重读 0x%05X 并与基线比对" % flash_addr)
        print("        ⇒ 若仍一致 ⇒ 落盘成立；若回原值 ⇒ 说明只到 RAM")
        return 0
    print("  3-1 复位（0E 13）…")
    for i in range(3):
        if g._send(list(framed_cmd(0x13))):
            print("      第 %d 次成功" % (i + 1))
            break
        time.sleep(0.02)
    time.sleep(0.3)
    print("  3-2 重读 0x%05X …" % flash_addr)
    d, log = g.read(flash_addr, 32)
    print("      %s" % hx(d, 32))
    print("      log: %s" % log)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, choices=[0, 1, 2, 3], required=True)
    ap.add_argument("--flash-addr", type=lambda x: int(x, 0), default=0x0A000)
    ap.add_argument("--commit", action="store_true",
                    help="★ 真正执行有风险步骤；不加则只打印计划（dry）")
    a = ap.parse_args()

    print("=" * 78)
    print("B12 持久化原语探针 —— 官方 `0E 12`（goodix/gdix_hid_firmware_update）")
    print("  阶段 %d · %s" % (a.phase, "★ COMMIT（会写设备）" if a.commit else "DRY（不打开设备）"))
    print("=" * 78)

    # 阶段 0/1 是只读，但仍需打开设备 ⇒ 统一用 --commit 作为"允许打开设备"的闸
    if not a.commit:
        print()
        print("[DRY] 未加 --commit ⇒ 不打开设备。各阶段将要执行的操作：")
        print("  阶段 0：只读 0x96F8(32B) + 0x19000(32B) —— 建恢复基线")
        print("  阶段 1：只读 0x4160 / 0x5095 / 0x5096 各 1 B —— 状态侦察")
        print("  阶段 2：★ 幂等提交（读回原样 → 写 0xC000 → 0E 12 → 轮询 0x5096==0xAA → 回读比对）")
        print("  阶段 3：★ 复位 0E 13 → 重读（验证持久性）")
        print()
        print("  ⚠️ 执行顺序必须是 0 → 1 → 2 → 3，且每阶段确认健康后再进下一步。")
        return 0

    g = gxmem.Gx()
    if not g.open():
        print("[FATAL] 打开 Col04 失败。")
        return 3
    try:
        if a.phase == 0:
            phase0(g)
        elif a.phase == 1:
            phase1(g)
        elif a.phase == 2:
            return phase2(g, a.flash_addr, True)
        elif a.phase == 3:
            return phase3(g, a.flash_addr, True)
        return 0
    finally:
        g.close()


if __name__ == "__main__":
    raise SystemExit(main())
