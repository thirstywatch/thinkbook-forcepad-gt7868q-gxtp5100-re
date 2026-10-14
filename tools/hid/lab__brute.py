#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__brute.py —— 「暴力软件」统一执行器（分阶段、默认 dry、每步可停）

依据：`docs/08-findings/2026-10-14-暴力软件方法可行性-四个未穷举面与客观判据前置件.md`

四个未穷举面（A/E 安全，C/D 有状态风险）
----------------------------------------
  A. Col04 class 字节     帧 `0E <cls> <sub> ...`；已扫仅 `0x10–0x13`+`0x30–0x37` ⇒ 未测 ≈228
  C. `0x4160` 命令码      5 字节 `{cmd,0,0,0,cmd}`；**256 个全部未扫**
  D. Col04 地址空间       只做过"写回原值"
  E. cfg 字段（触觉区）   TAG `0x50`–`0x7A`；**最安全**（会话 RAM，`0x7D` 后自动丢弃）

本脚本阶段的实现状态
--------------------
  [x] durability  通道耐久实测 —— **只读**，测"连续 N 帧会不会触发 err=122"
  [x] snapshot    基线快照（读 0x4000/0x4160/0x5095/0x5096/0x96F8 + 命令寄存器 5 字节）
  [x] cmdscan     扫 `0x4160` 命令码（**低频、逐条、逐条读回、异常即停**）
  [ ] classscan   A 面（待 durability 结果定批量）
  [ ] cfgscan     E 面

安全设计
--------
  · 默认 **dry**；不加 `--commit` 不打开设备
  · 每条写后**立即读回**并记日志；**出现未知/异常响应立即停扫**
  · `finally` 必发 `0x7D`（丢弃会话 cfg）
  · **绝不碰** `0x1E000` / `0xC000` / `0E 10` / `0E 11` / `0E 12`（flash 路径）
  · 命令码扫描**默认跳过**已知危险值（见 SKIP）
"""
import sys, os, time, json, argparse, datetime

# Windows 控制台默认 GBK：打印 emoji / 生僻字会让 print 抛 UnicodeEncodeError（2026-10-14 实测）
try:  # 只把不可编码字符降级为 '?'，不改变可读内容
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import gxmem
except Exception as e:
    print("[FATAL] 需同目录 gxmem.py: %r" % e)
    raise SystemExit(2)

CMD_ADDR = 0x4160
CFG_ADDR = 0x96F8
BL_STATE = 0x5095
FLASH_RES = 0x5096
LIVE = 0x4000
FWINFO = 0x452C

# 命令码扫描：这些值跳过（已知特殊/危险）
SKIP = {
    0x00,           # 疑似软复位类语义，未知 ⇒ 跳过（宁可漏也不冒险）
    0x80, 0x83, 0x7D, 0x7E, 0x7F,   # 已知 cfg 会话命令（会改 cfg 暂存态）
    0xAA,           # 官方语义 = COMMAND_CLOSE_HID ⇒ 可能关掉 HID 通道
    0x05,           # 官方 = COMMAND_SLEEP ⇒ 可能让 IC 睡下去
}

LOGF = os.path.join(HERE, "_brute_log.txt")


def log(m=""):
    print(m, flush=True)
    with open(LOGF, 'a', encoding='utf-8') as f:
        f.write(m + "\n")


def hx(b):
    return b.hex(' ').upper() if b else '<FAIL>'


def rd(g, addr, n, rounds=6, delay=0.05):
    d, _ = g.read(addr, n, rounds=rounds, delay=delay)
    return bytes(d) if d else None


def mkc(cmd, data=0):
    """官方 YS 5 字节命令帧 {cmd, dataHi, dataLo, sumHi, sumLo}"""
    hi, lo = (data >> 8) & 0xFF, data & 0xFF
    s = (cmd + hi + lo) & 0xFFFF
    return bytes([cmd, hi, lo, (s >> 8) & 0xFF, s & 0xFF])


def snapshot(g):
    return {
        "0x4000": hx(rd(g, LIVE, 4)),
        "0x4160": hx(rd(g, CMD_ADDR, 1)),
        "0x5095": hx(rd(g, BL_STATE, 1)),
        "0x5096": hx(rd(g, FLASH_RES, 1)),
        "0x452C": hx(rd(g, FWINFO, 4)),
        "0x96F8": hx(rd(g, CFG_ADDR, 8)),
    }


# ────────────────────────────── 阶段 1：通道耐久（只读）
def cmd_durability(args):
    n = int(args[0]) if args else 200
    gap = float(args[1]) if len(args) > 1 else 0.06
    size = int(args[2]) if len(args) > 2 else 4
    log("=" * 80)
    log("【阶段 1】通道耐久实测（只读）  目标 %d 帧 × %d B，间隔 %.3f s   %s"
        % (n, size, gap, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    log("=" * 80)
    g = gxmem.Gx()
    if not g.open():
        log("❌ 打不开 Col04")
        return
    fails = []
    t0 = time.time()
    try:
        for i in range(1, n + 1):
            d, lg = g.read(LIVE, size, rounds=6, delay=0.05)
            ok = bool(d)
            if not ok:
                fails.append(i)
                log("  ✗ 第 %d 帧 FAIL  (%s)  t=%.1fs" % (i, lg, time.time() - t0))
                if len(fails) >= 5:
                    log("  ⇒ 连续 5 次失败，停测")
                    break
            elif i % 20 == 0:
                log("  · %3d/%d  ok  %d B  t=%.1fs" % (i, n, len(d), time.time() - t0))
            time.sleep(gap)
    finally:
        g.close()
    log("\n--- 结果 ---")
    log("  %d B/帧，连续 %d 帧；失败 %d 次；总耗时 %.1f s" % (size, n, len(fails), time.time() - t0))
    if fails:
        log("  首次失败在第 %d 帧（约 t=%.1fs）" % (fails[0], fails[0] * gap))
        log("  ⇒ 通道确实有上限；后续批量扫描必须按此值保守设置")
    else:
        log("  ⇒ 本次 %d 帧 × %d B 全通" % (n, size))
        if size <= 8:
            log("  ⚠️ 本项只测了【小读】；`lab__col04_sweep.py` 记的 err=122 出现在**大流量**场景 ⇒")
            log("     必须再跑一次 `durability <n> <gap> 64`（65 B 满帧）才能下结论")


# ────────────────────────────── 阶段 3：命令码扫描
def probe_cmd(g, c, frame=None, polls=12, gap=0.06):
    """写一条命令帧，然后【多次轮询 byte[0]】，返回 (看到的 byte[0] 值集合, 末次 5B 原始)

    ★ 判据要点（本轮实测修正）：
      · `0x4160` 是**普通内存**：IC 不处理的命令会**原样留存**（不会说"未知命令"）
      · `byte[0] == 0xFF` 是 **IC 回到空闲**，**不是响应**
      · `byte[0] == 我写进去的值` 是 **尚未被处理**
      · ⇒ **只有 `byte[0]` 变成【第三种值】（如 `0x82`/`0x7E`/`0x7F`/`0xDD`）才算真响应**
      · 轮询而非单次读，是为了把【时序】与【真响应】分开
    """
    frame = frame or mkc(c)
    if not g.write(CMD_ADDR, frame):
        return None, None
    seen = []
    last = None
    for _ in range(polls):
        d, _ = g.read(CMD_ADDR, 5, rounds=4, delay=0.04)
        if d:
            last = bytes(d)
            if last[0] not in seen:
                seen.append(last[0])
        time.sleep(gap)
    return seen, last


def positive_control(g):
    """阳性对照：官方 0x80 应让 byte[0] 变 0x82；0x83 应让它变 0x7E/0x7F。
    若这一步不通过 ⇒ 判据或通道有问题，**立即停扫**（纪律 12）。"""
    log("--- 阳性对照（0x80 → 期望 0x82）---")
    seen, last = probe_cmd(g, 0x80, polls=10, gap=0.06)
    log("  0x80 后 byte[0] 序列 = %s   末次 5B = %s"
        % ([hex(x) for x in seen] if seen else '<FAIL>', hx(last)))
    ok = seen and 0x82 in seen
    log("  ⇒ %s" % ("✅ 对照通过（探针能识别真响应）" if ok else "❌ 对照失败 ⇒ 判据/通道不可靠，停扫"))
    try:
        g.write(CMD_ADDR, mkc(0x7D))
        time.sleep(0.2)
    except Exception:
        pass
    return ok


def cmd_cmdscan(args):
    lo = int(args[0], 0) if args else 0x01
    hi = int(args[1], 0) if len(args) > 1 else 0xFF
    gap = float(args[2]) if len(args) > 2 else 0.15
    log("=" * 80)
    log("【阶段 3】`0x4160` 命令码扫描  %#04x–%#04x  间隔 %.2fs" % (lo, hi, gap))
    log("=" * 80)
    g = gxmem.Gx()
    if not g.open():
        log("❌ 打不开 Col04")
        return
    base = snapshot(g)
    log("基线快照: " + json.dumps(base, ensure_ascii=False))
    if not positive_control(g):
        g.close()
        return
    hits, fails = [], 0
    try:
        for c in range(lo, hi + 1):
            if c in SKIP:
                continue
            frame = mkc(c)
            seen, last = probe_cmd(g, c, frame)
            if seen is None:
                log("  ✗ cmd=%#04x 写失败 ⇒ 停扫" % c)
                break
            # 真响应 = byte[0] 出现第三种值
            real = [v for v in seen if v not in (0xFF, c)]
            if real:
                hits.append((c, [hex(v) for v in real], last.hex(' ').upper() if last else ''))
                log("  ★★ cmd=%#04x  → byte[0] 出现 %s   (末次 %s)"
                    % (c, [hex(v) for v in real], hx(last)))
            else:
                fails += 1
                if fails <= 20:
                    log("  ·  cmd=%#04x  byte[0] 只走过 %s ⇒ 无真响应"
                        % (c, [hex(v) for v in seen]))
            time.sleep(gap)
    finally:
        try:
            g.write(CMD_ADDR, mkc(0x7D))     # 项目标准收尾（无会话时 IC 会原样留存）
            time.sleep(0.15)
            log("\n收尾即刻 0x4160 = %s" % hx(rd(g, CMD_ADDR, 5)))
            time.sleep(2.0)
            log("等 2 s 后 0x4160 = %s" % hx(rd(g, CMD_ADDR, 5)))
        except Exception:
            pass
        after = snapshot(g)
        log("收尾快照: " + json.dumps(after, ensure_ascii=False))
        ch = [k for k in base if base[k] != after[k]]
        log("与基线不同的项: %s" % (ch if ch else "无 ✓"))
        g.close()
    log("\n--- 结果 ---")
    log("  真响应命令码 %d 个：%s" % (len(hits), [hex(c) for c, _, _ in hits]))
    for c, vals, lastr in hits:
        log("      %#04x → byte[0] ∈ %s   末次 %s" % (c, vals, lastr))
    log("  无真响应 %d 个" % fails)


# ─────────────────────────────────────────────────────────────────────────────
# 🔴 语义已知区 / 危险区（纪律 154 的落地）
#
# 来源：
#   · 官方 gtx8_driver_linux 源码（HID 命令类）
#   · 官方 gdix_hid_firmware_update 源码（0x0E 10/11/12/13）
#   · tpupdate_driver.dll 反汇编（帧格式恒为 0E 20；期望值表）
#   · 项目实测（0x00–0x0D / 0x10–0x13 / 0x20 已实现）
#
# ★ HID `0E <cls>` class 空间（A 面）
#   已实现：0x00–0x0D, 0x10–0x13, 0x20
#   ★★ 已知危险：0x10=切patch · 0x11=启动更新 · 0x12=写flash · 0x13=复位
#   → 其余（0x0E/0x0F/0x14–0x1F/0x21–0xFF）**语义未知**，**不得盲扫**
# ─────────────────────────────────────────────────────────────────────────────
HID_KNOWN_DANGEROUS = {
    0x10: "切到 patch / bootloader",
    0x11: "启动更新",
    0x12: "写 flash（最危险）",
    0x13: "复位 IC",
}
HID_KNOWN_SAFE = {
    0x20: "I2C_DIRECT_RW（内存读写；DLL 只用这一种，帧恒为 0E 20）",
}
# A 面允许扫描的 class：**只有已证无副作用者**（目前为空集 —— 连只读也没人证过）
HID_SCANNABLE = set()


# ────────────────────────────── 阶段 2：A 面 class 扫描（默认拒绝）
def cmd_classscan(args):
    print("=" * 78)
    print("🔴 拒绝执行：`classscan` 未启用（纪律 154）。")
    print("=" * 78)
    print("  理由（结构性，不是谨慎）：")
    print("   · HID `0E <cls>` 空间里，**已知有语义的 class 全在低位**：")
    print("       0x10 = 切 patch · 0x11 = 启动更新 · 0x12 = 写 flash · 0x13 = 复位")
    print("   · `0x14–0xFF` 的语义**无从得知**（DLL 里也不含这张表 —— 它只发 0E 20）")
    print("   · 2026-10-14 事故已实测：未知命令会让 IC 进入**掉电才清的持久态**")
    print("     （`0E 13` 复位 + HID 启停都不够，必须长按重启）")
    print("   · A 面未测 ≈ 228 个 class ⇒ **每次猜错 = 一次重启，物理上不可接受**")
    print()
    print("  ⇒ 要启用必须先【拿到该 IC 的完整 HID 命令表】。")
    print("     来源只有两处：① IC 自身固件（不可反汇编）② 官方工具（已查，不含）")
    print("  ⇒ 两者都没有之前，A 面不应再扫。")
    print("=" * 78)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="暴力软件执行器")
    ap.add_argument("stage", choices=["snapshot", "durability", "cmdscan", "classscan"])
    ap.add_argument("arg", nargs="*")
    ap.add_argument("--commit", action="store_true", help="真正打开设备（默认 dry）")
    ap.add_argument("--i-know-its-dangerous", action="store_true",
                    help="【已作废阶段】cmdscan 的强制解锁开关（默认拒绝执行）")
    a = ap.parse_args()

    # 🔴🔴 2026-10-14 事故后加锁：`0x4160` 未知命令码扫描【已作废】（纪律 153）
    if a.stage == "cmdscan" and not a.i_know_its_dangerous:
        print("=" * 78)
        print("🔴 拒绝执行：`cmdscan` 已于 2026-10-14 作废（纪律 153）。")
        print("=" * 78)
        print("  原因：`0x4160` 的命令码【很可能与 Col04 HID 命令空间共享语义】——")
        print("        0x10 = 切 patch/bootloader · 0x11 = 启动更新 ·")
        print("        0x12 = 写 flash（最危险） · 0x13 = 复位 IC")
        print("  ⇒ 2026-10-14 13:50 盲扫 0x01–0x2F 时导致【触控板失效】（用户报「炸了」）。")
        print()
        print("  事故记录：docs/08-findings/2026-10-14-事故-0x4160命令码扫描致触控板失效.md")
        print("  纪律 154：任何写设备的扫描，必须先做【命令空间语义同构性检查】。")
        print()
        print("  若你确实要重跑：加 --i-know-its-dangerous（并请先确认设备可恢复）")
        print("=" * 78)
        raise SystemExit(3)

    # 🔴 A 面同理加锁（纪律 154 的落地）
    if a.stage == "classscan":
        cmd_classscan(a.arg)
        raise SystemExit(4)

    if not a.commit:
        print("[DRY] 未打开设备。用 --commit 执行。阶段：", a.stage, a.arg)
        print("  注意：durability / snapshot 是【只读】；cmdscan 会写 0x4160（每条写后立即读回，异常即停）。")
        raise SystemExit(0)
    log("\n" + "#" * 80 + "\n# %s  %s\n" % (a.stage, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')) + "#" * 80)
    if a.stage == "snapshot":
        g = gxmem.Gx(); g.open(); log(json.dumps(snapshot(g), ensure_ascii=False)); g.close()
    elif a.stage == "durability":
        cmd_durability(a.arg)
