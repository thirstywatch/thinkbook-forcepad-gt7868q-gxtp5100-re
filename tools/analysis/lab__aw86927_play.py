#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aw86927_play.py -- 让本机触控板震起来：最小风险寄存器序列 + 操作卡生成器

背景（《全书》§19.33 / §19.32.2）：
  本机触觉执行器 = 艾为 AW86927FCR（丝印 CA4F），I2C 从地址 0x5A 或 0x5B，
  寄存器 0x57/0x58 应为 0x92/0x70（CHIPID = 0x9270）。
  播放模式由 0x08 的 PLAY_MODE[1:0] 选择：0=RAM(上传波形) 1=RTP(流式) 2=CONT(连续方波)
  位定义来自 Linux 主线驱动 aw86927.c（逐行可查）：
     0x08 PLAYCFG3 : AUTO_BST=BIT4, PLAY_MODE=GENMASK(1,0)   RAM=0
     0x09 PLAYCFG4 : STOP=BIT1, GO=BIT0
     0x32 RTPDATA  : RTP_DATA（写它就播）
     0x3F GLBRD5   : GLB_STATE=GENMASK(3,0)  (0=STANDBY 6=CONT 7=RAM 8=RTP 9=TRIG)
     0x09 bit0=GO 触发；bit1=STOP 停止

★ 设计原则 = **只碰"触发"寄存器（0x08/0x09，必要时 0x32）**。
  本机触控板**现在就在震**（点按自震）⇒ LRA、功放、供电、F0 标定**全部已就绪**。
  所以不要动 0x00(软复位) / 0x06(BST 供电) / 0x45 / 0x4D / 0x4E（那些是"别人配好的"），
  只加一个"播放触发"，随时能停、能还原。

三种模式：
  --mode cont   ★ 最短：2 次写（0x08←0x02, 0x09←0x01），不需要上传任何波形
  --mode rtp    最适合"滑动反馈"：0x08←0x01 + GO，然后持续往 0x32 写幅度字节
  --mode ram    厂商保真：上传 102 B 正弦到 SRAM 后按 RAM 模式播（步骤最多）

用法：
  python aw86927_play.py --dry-run                 # 生成操作卡（RWEverything 手动照打）
  python aw86927_play.py --backend linuxtest --addr 0x5a --mode cont   # Linux live USB
  python aw86927_play.py --backend linuxtest --addr 0x5a --mode stop   # 停止
  python aw86927_play.py --backend linuxtest --addr 0x5a --mode restore# 还原原值
"""
import argparse
import datetime
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "aw86927-play.log")

# Linux 主线驱动内嵌波形：round(84 * sin(x / 16.25))，二进制补码，102 字节
WAVE = bytes.fromhex(
    "00 05 0A 0F 14 1A 1F 23 28 2D 31 35 39 3D 41 44 47 4A 4C 4F 51 52 53 54 55"
    "55 55 55 55 54 52 51 4F 4D 4A 47 44 41 3D 3A 36 31 2D 28 24 1F 1A 15 10 0A"
    "05 00 FC F6 F1 EC E7 E2 DD D8 D4 CF CB C7 C3 BF BC B9 B6 B4 B1 B0 AE AD AC"
    "AB AB AB AB AB AC AE AF B1 B3 B6 B8 BC BF C2 C6 CA CE D3 D7 DC E1 E6 EB F0"
    "F5 FB".replace(" ", "")
)

# ---- 寄存器 ---------------------------------------------------------------
R_RSTCFG = 0x00        # 软复位：写 0xAA。★ 禁用（会清掉模组的配置）
R_PLAYCFG1 = 0x06      # BST 供电。★ 禁用
R_PLAYCFG2 = 0x07      # GAIN
R_PLAYCFG3 = 0x08      # AUTO_BST(BIT4) / PLAY_MODE[1:0]
R_PLAYCFG4 = 0x09      # STOP(BIT1) / GO(BIT0)
R_WAVCFG1 = 0x0A       # WAVSEQ1
R_WAVCFG2 = 0x0B       # WAVSEQ2
R_WAVCFG9 = 0x12       # SEQ1LOOP[7:4]
R_BASEADDRH = 0x2D
R_BASEADDRL = 0x2E
R_GLBRD5 = 0x3F        # GLB_STATE (RO)
R_RAMADDRH = 0x40
R_RAMADDRL = 0x41
R_RAMDATA = 0x42       # 连续写入口（地址自增）
R_SYSCTRL3 = 0x45      # EN_RAMINIT(BIT2)。★ 仅 RAM 模式需要
R_DETCFG1 = 0x4D       # DET_GO。★ RAM 模式需要，默认禁用
R_DETCFG2 = 0x4E       # DET_SEQ0。★ 同上
R_RTPDATA = 0x32       # RTP 幅度
R_CHIPIDH = 0x57
R_CHIPIDL = 0x58

MODE_RAM, MODE_RTP, MODE_CONT = 0, 1, 2

FORBIDDEN_DEFAULT = {R_RSTCFG, R_PLAYCFG1, R_SYSCTRL3, R_DETCFG1, R_DETCFG2}


class Journal:
    def __init__(self):
        self.fh = open(LOG, "a", encoding="utf-8")
        self.lines = []

    def __call__(self, *a):
        s = " ".join(str(x) for x in a)
        print(s)
        self.fh.write(s + "\n")
        self.fh.flush()
        self.lines.append(s)

    def close(self):
        self.fh.close()


class Backend:
    """I2C 后端。所有写操作都记 journal，并支持还原。"""

    name = "abstract"

    def read_u8(self, addr, reg):
        raise NotImplementedError

    def write_u8(self, addr, reg, val):
        raise NotImplementedError

    def write_block(self, addr, reg, data):
        raise NotImplementedError

    def probe(self, addr):
        return self.read_u8(addr, R_CHIPIDH) is not None


class DryBackend(Backend):
    """不出手：只生成操作卡。"""
    name = "dryrun"

    def __init__(self, j):
        self.j = j

    def read_u8(self, addr, reg):
        self.j(f"        读 {reg:#04x}  -> (待你在 RWEverything 里读)")
        return None

    def write_u8(self, addr, reg, val):
        self.j(f"        写 {reg:#04x} <- {val:#04x}")

    def write_block(self, addr, reg, data):
        self.j(f"        写 {reg:#04x} <- {len(data)} 字节: {data.hex(' ').upper()}")


class LinuxBackend(Backend):
    """Linux live USB：用 i2c-tools 的 i2cget/i2cset。
    ⚠️ 必须先解绑 i2c_hid（见 linux/probe2.sh），否则 0x2C 被占、总线行为异常。
    """
    name = "linuxtest"

    def __init__(self, j, bus):
        self.j = j
        self.bus = str(bus)
        for t in ("i2cget", "i2cset"):
            if subprocess.run(["which", t], capture_output=True).returncode != 0:
                raise RuntimeError(f"{t} 不可用：apt-get install -y i2c-tools")

    def read_u8(self, addr, reg):
        p = subprocess.run(["i2cget", "-y", self.bus, f"{addr:#04x}", f"{reg:#04x}"],
                           capture_output=True, text=True)
        if p.returncode != 0:
            return None
        try:
            return int(p.stdout.strip(), 0)
        except ValueError:
            return None

    def write_u8(self, addr, reg, val):
        p = subprocess.run(["i2cset", "-y", self.bus, f"{addr:#04x}", f"{reg:#04x}",
                            f"{val:#04x}"], capture_output=True, text=True)
        return p.returncode == 0

    def write_block(self, addr, reg, data):
        # i2cset 的 i2cset ... <reg> <val> ... 一次最多给少量字节；
        # 对 0x42 连续写用 i2ctransfer 更合适
        p = subprocess.run(["i2ctransfer", "-y", self.bus, "w" + str(len(data) + 1) +
                            f"@{addr:#04x}", f"{reg:#04x}"] +
                           [f"{b:#04x}" for b in data], capture_output=True, text=True)
        return p.returncode == 0


class PawnIOBackend(Backend):
    """Windows + PawnIO 模块（W2 路线）。模块尚未编写，此处只留接口。
    模块需要：pci_config_read_dword(0,0x15,0,0x10) 取 BAR0 -> io_space_map
              -> virtual_write_dword 按 DW_apb_i2c 寄存器做 I2C 事务。
    见《全书》§19.33.6 与原语清单。
    """
    name = "pawnio"

    def __init__(self, *a, **kw):
        raise RuntimeError(
            "PawnIO 后端尚未实现：需先通过 poc\\run-pawnio-modsig-test.bat 确认\n"
            "  PawnIO 接受第三方模块（见《全书》§19.33.6）。\n"
            "  现在请改用 --dry-run 生成操作卡，或用 RWEverything 手动照打。"
        )


def build_plan(mode, j, addr):
    """返回 [(reg, value, 说明)] —— 一个有序的"写"列表；只碰允许的寄存器。

    value 可以是：
      int              -> 整字节写
      bytes            -> 块写（0x42 连续写）
      ("RMW", mask, v) -> ★ 读-改-写：只改 (value & mask) 位，保留其余位
    """
    plan = []
    if mode == "observe":
        # 只读：不产生任何写操作。由 main() 打印观测指引。
        return plan
    if mode == "cont":
        # ★ 关键修正：0x08 里还有 AUTO_BST(bit4) / STOP_MODE / BRK_EN。
        #   整字节写 0x02 会把 AUTO_BST 清 0 —— 那等于把升压关掉，很可能就不震了。
        #   必须读-改-写。
        plan.append((R_PLAYCFG3, ("RMW", 0x03, MODE_CONT),
                     "PLAY_MODE=2 (CONT) —— ★ 只改低 2 位，保留 AUTO_BST/STOP_MODE/BRK_EN"))
        plan.append((R_PLAYCFG4, 0x01, "GO=1 -> 开始震（会持续，直到 STOP）"))
    elif mode == "rtp":
        plan.append((R_PLAYCFG3, ("RMW", 0x03, MODE_RTP),
                     "PLAY_MODE=1 (RTP) —— 只改低 2 位"))
        plan.append((R_PLAYCFG4, 0x01, "GO=1"))
        plan.append(("RTP-STREAM", None,
                     "随后持续往 0x32 写幅度字节（正弦查表）即为播放；"
                     "停止时把 0x08 的 PLAY_MODE 换成 CONT/RAM 或写 STOP"))
    elif mode == "ram":
        plan.append((R_SYSCTRL3, None, "0x45 |= BIT2 (EN_RAMINIT) —— ★ 需要 --allow-power-regs"))
        plan.append((R_BASEADDRH, 0x08, "SRAM 基址高"))
        plan.append((R_BASEADDRL, 0x00, "SRAM 基址低 (0x0800)"))
        plan.append((R_RAMADDRH, 0x08, "写指针高"))
        plan.append((R_RAMADDRL, 0x00, "写指针低"))
        hdr = bytes([0x01, 0x08, 0x05]) + (0x0805 + len(WAVE) - 1).to_bytes(2, "big")
        plan.append((R_RAMDATA, hdr, f"波形头 5B: {hdr.hex(' ').upper()}"))
        plan.append((R_RAMDATA, WAVE, f"波形 {len(WAVE)}B"))
        plan.append((R_DETCFG2, 0x00, "DET_SEQ0=VBAT —— ★ 需要 --allow-power-regs"))
        plan.append((R_DETCFG1, 0x01, "DET_GO —— ★ 需要 --allow-power-regs"))
        plan.append((R_PLAYCFG2, 0x7C, "增益（防失真）"))
        plan.append((R_PLAYCFG3, MODE_RAM | 0x10, "PLAY_MODE=0 (RAM) + AUTO_BST=1"))
        plan.append((R_WAVCFG1, 0x01, "WAVSEQ1=1"))
        plan.append((R_WAVCFG2, 0x00, "WAVSEQ2=0"))
        plan.append((R_WAVCFG9, 0x0F, "SEQ1LOOP=0x0F (无限循环)"))
        plan.append((R_PLAYCFG4, 0x01, "GO=1 -> ★ 开始震"))
    elif mode == "stop":
        plan.append((R_PLAYCFG4, 0x02, "STOP=1 -> 停止"))
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="dryrun",
                    choices=["dryrun", "linuxtest", "pawnio"])
    ap.add_argument("--bus", default=None, help="Linux 下的 I2C 总线号（如 0）")
    ap.add_argument("--addr", default="0x5a", help="AW86927 从地址，0x5a 或 0x5b")
    ap.add_argument("--mode", default="observe",
                    choices=["observe", "cont", "rtp", "ram", "stop", "restore"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-power-regs", action="store_true",
                    help="允许触碰 0x00/0x06/0x45/0x4D/0x4E（默认禁止）")
    args = ap.parse_args()
    if args.dry_run:
        args.backend = "dryrun"

    addr = int(args.addr, 16)
    j = Journal()
    j("=" * 70)
    j(f" AW86927 播放序列  {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    j(f" backend={args.backend}  addr={addr:#04x}  mode={args.mode}")
    j("=" * 70)

    if args.backend == "dryrun":
        be = DryBackend(j)
    elif args.backend == "linuxtest":
        if args.bus is None:
            j("[X] --backend linuxtest 需要 --bus <N>")
            return 1
        be = LinuxBackend(j, args.bus)
    else:
        be = PawnIOBackend()

    # --- 0. 身份 ---
    j("\n[0] 身份确认（唯一判据）")
    hi = be.read_u8(addr, R_CHIPIDH)
    lo = be.read_u8(addr, R_CHIPIDL)
    if args.backend == "dryrun":
        j("     期望 0x57=0x92、0x58=0x70（AW86927, CHIPID=0x9270）")
    elif hi is None or lo is None:
        j(f"     [X] {addr:#04x} 无应答 => 它不在这条总线上（见《全书》§19.33 三条路）")
        j.close()
        return 2
    elif hi == 0x92 and lo == 0x70:
        j(f"     ★★★ 确认 AW86927：0x57={hi:#04x} 0x58={lo:#04x}")
    else:
        j(f"     [!] 有应答但不是 AW86927：0x57={hi:#04x} 0x58={lo:#04x} —— 建议 --addr 0x5b 复核")
        j.close()
        return 3

    # --- 1. 存原值 ---
    j("\n[1] 先读并存下原值（用于还原）")
    saved = {}
    for reg, why in ((R_PLAYCFG3, "PLAYCFG3"), (R_PLAYCFG4, "PLAYCFG4"),
                     (R_GLBRD5, "GLB_STATE(RO)"),
                     (R_PLAYCFG2, "GAIN"), (R_WAVCFG1, "WAVSEQ1"),
                     (R_WAVCFG9, "SEQ1LOOP"), (R_SYSCTRL3, "SYSCTRL3")):
        v = be.read_u8(addr, reg)
        saved[reg] = v
        j(f"     {reg:#04x} {why:12s} = " + ("?" if v is None else f"{v:#04x}"))
    sv = os.path.join(HERE, "aw86927-saved.json")
    import json
    json.dump({f"{k:#04x}": v for k, v in saved.items()}, open(sv, "w"), indent=1)
    j(f"     已存 {sv}")

    # --- 2. 计划 ---
    if args.mode == "restore":
        j("\n[2] 还原：把存下的值写回")
        for k, v in saved.items():
            if v is not None:
                be.write_u8(addr, k, v)
        be.write_u8(addr, R_PLAYCFG4, 0x02)
        j("     done")
        j.close()
        return 0

    plan = build_plan(args.mode, j, addr)
    j(f"\n[2] {args.mode} 计划（{len(plan)} 步）")
    if args.mode == "observe":
        j("     ★ 只读观测：不产生任何写操作。")
        j("     目标 = 看厂商自己是怎么让它震的（哪种 PLAY_MODE），然后照抄。")
        j("     做法：GUI 里对 0x3F / 0x08 / 0x09 开自动刷新，然后在触控板上点按。")
        j("     判读：")
        j("       0x3F 从 0(STANDBY) 跳到 6/7/8/9 —— 记下是哪一个：")
        j("         6=CONT  7=RAM  8=RTP  9=TRIG   => 我们就照抄那个 PLAY_MODE")
        j("       0x3F 全程不动、0x08 也全程为 0 —— ⚠️ 说明点按震动【不经过 AW86927 的播放引擎】")
        j("         => 那我们写 GO 大概率也不会有反应，需要换思路（查 TRIG 引脚 / 别的执行路径）")
    blocked = []
    for i, item in enumerate(plan, 1):
        reg, val, why = item
        if reg in FORBIDDEN_DEFAULT and not args.allow_power_regs:
            blocked.append((i, reg, why))
            j(f"     {i:2d}. ★跳过 {reg:#04x} —— {why}")
            continue
        if reg == "RTP-STREAM":
            j(f"     {i:2d}. {why}")
            continue
        # 读-改-写：只改 mask 位，保留其它位（关键：别把 AUTO_BST 清掉）
        if isinstance(val, tuple) and val and val[0] == "RMW":
            _, mask, newbits = val
            cur = be.read_u8(addr, reg)
            if cur is None:
                j(f"     {i:2d}. [RMW] {reg:#04x} 读原值失败，跳过（避免整字节写清掉别的位）")
                continue
            nv = (cur & ~mask & 0xFF) | (newbits & mask)
            if args.backend == "dryrun":
                j(f"     {i:2d}. [RMW] {reg:#04x} <- (读值 & ~{mask:#04x}) | {newbits:#04x}   {why}")
                j(f"          例：若原值 0x{cur:02x} -> 新值 0x{nv:02x}")
                j(f"          ⇒ GUI 里请：先读 0x{reg:02x}，再「只改相应位」写入，别整字节覆盖")
                continue
            ok = be.write_u8(addr, reg, nv)
            j(f"     {i:2d}. [RMW] {reg:#04x}: 0x{cur:02x} -> 0x{nv:02x}   {why}   [{'ok' if ok else 'FAIL'}]")
            saved.setdefault(reg, cur)
            continue
        if args.backend == "dryrun":
            if isinstance(val, int):
                j(f"     {i:2d}. {reg:#04x} <- {val:#04x}   {why}")
            else:
                j(f"     {i:2d}. {reg:#04x} <- blk    {why}")
        else:
            if isinstance(val, int):
                ok = be.write_u8(addr, reg, val)
                j(f"     {i:2d}. {reg:#04x} <- {val:#04x}   {why}   [{'ok' if ok else 'FAIL'}]")
            else:
                ok = be.write_block(addr, reg, val)
                j(f"     {i:2d}. {reg:#04x} <- {len(val)}B  {why}   [{'ok' if ok else 'FAIL'}]")
    if blocked:
        j(f"\n     ⚠️ {len(blocked)} 步被安全闸拦下（涉及供电/检测/复位寄存器）。")
        j("        确认无误后加 --allow-power-regs 重跑。")

    # --- 2.5 原值诊断（★ 只读信息，决定第 4 步值不值得做） ---
    p3 = saved.get(R_PLAYCFG3)
    gs = saved.get(R_GLBRD5)
    j("\n[2.5] 原值诊断（这比第 4 步更能预测「能不能震」）")
    if p3 is None and gs is None:
        j("     （dryrun 或读失败，无原值可判）")
    else:
        j(f"     PLAYCFG3(0x08) = {p3!r}   GLB_STATE(0x3F) = {gs!r}")
        if isinstance(p3, int) and p3 == 0 and gs == 0:
            j("     ⚠️ 0x08=0 且 0x3F=0(STANDBY)：芯片处于【未配置/待机】状态。")
            j("        两种可能：① 模块每次点按时临时配置它；② 点按震动根本不走它的播放引擎。")
            j("        ⇒ 先用 --mode observe 看「点按瞬间 0x3F 会不会跳」，再决定要不要写。")
        elif isinstance(p3, int) and (p3 & 0x10):
            j("     ✅ 0x08 的 AUTO_BST(bit4) = 1 ⇒ 模块确实配置过它，且自动升压已开。")
            j("        ⇒ 我们的写入更可能生效（但仍不能保证，见操作卡「为什么可能不震」）。")
        elif isinstance(p3, int) and p3 != 0:
            j("     🟡 0x08 非 0 但 AUTO_BST=0 ⇒ 升压可能由外部/其它路径提供，保守观察。")

    # --- 3. 状态 ---
    if args.backend != "dryrun":
        j("\n[3] 读回 GLB_STATE(0x3F) —— 0=STANDBY 6=CONT 7=RAM 8=RTP 9=TRIG")
        j(f"     0x3F = {be.read_u8(addr, R_GLBRD5)!r}")
        j("\n[4] 停止： --mode stop ；完全还原： --mode restore")

    j("\n日志：" + LOG)
    j.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
