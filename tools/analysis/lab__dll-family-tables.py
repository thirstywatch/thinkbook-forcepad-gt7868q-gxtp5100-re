#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__dll-family-tables.py —— N4：还原 `tpupdate_driver.dll` 里【全部家族分支】的寄存器表

已知（§19.62）：DLL 的某个 init 函数用 `mov dword [rip+disp32], imm32` 在运行时填充
一张「寄存器地址 + 期望值 + 命令帧」表（基址 `.data:0x18B04`，该区是 BSS ⇒ 静态全零）。
**§19.62 认为只有 2 张表（icType 1/2）；本工具做全局扫描后发现是【5 个家族分支】。**

做法：线性反汇编 → 跟踪 `cmp eax, N` 作为分支标记 → 把每个 `mov [rip+d], imm` 归到当前分支
→ 按目标 RVA 排序输出 ⇒ 每个家族的完整参数表。

⚠️ capstone 未编译 detail 时不能用 ins.operands ⇒ 本工具用 `op_str` 正则解析。

用法：python lab__dll-family-tables.py <dll> [--lo 0x1028] [--hi 0x1E60]
"""
import re, sys, os, argparse
import capstone

# Windows 控制台默认 GBK：打印 emoji / 生僻字会让 print 抛 UnicodeEncodeError（2026-10-14 实测）
try:  # 只把不可编码字符降级为 '?'，不改变可读内容
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

LBL = {
    0x18B00: "家族选择子 [0x18B00]", 0x18B04: "内部索引(写入值)", 0x18B08: "fw_ver_addr",
    0x18B0C: "w=4", 0x18B10: "vid_addr", 0x18B14: "w=4", 0x18B18: "sensor_id_addr", 0x18B1C: "w=1",
    0x18B20: "P1", 0x18B24: "P2", 0x18B28: "★cfg_addr", 0x18B2C: "flash_buf", 0x18B30: "flash_res_addr",
    0x18B34: "flash_res_exp", 0x18B38: "sentinel", 0x18B3C: "BL_state_addr", 0x18B40: "BL_exp",
    0x18B44: "★command_addr", 0x18B48: "cmd_exp", 0x18B58: "★cfg_ok_exp", 0x18B5C: "★cmd_frame_len",
    0x18B60: "F1", 0x18B64: "coor_addr", 0x18B68: "start_send_cfg", 0x18B6C: "A1", 0x18B70: "A2", 0x18B74: "A3",
    0x18C0C: "命令区长度", 0x18C10: "command_addr#2", 0x18C14: "cmd1(4B写)", 0x18C18: "★★命令1",
    0x18C1E: "帧长1", 0x18C2F: "cmd2(4B写)", 0x18C33: "★★命令2", 0x18C39: "帧长2",
    0x18C3B: "cmd3(4B写)", 0x18C3E: "★★命令3", 0x18C44: "帧长3",
    0x18C46: "cmd4(4B写)", 0x18C49: "★★命令4", 0x18C4F: "帧长4",
    0x18C50: "分区大小?",
}
PAT = re.compile(r'\[rip \+ (0x[0-9a-f]+)\](?:, (0x[0-9a-f]+))?')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dll")
    ap.add_argument("--lo", type=lambda x: int(x, 0), default=0x1028)
    ap.add_argument("--hi", type=lambda x: int(x, 0), default=0x1E60)
    ap.add_argument("--base", type=lambda x: int(x, 0), default=0x18B00,
                    help="表基址（各版本不同：x_108e1f62=0x18B00, x_driver_e=0x17B00, x_ee49202f=0x17B00）")
    args = ap.parse_args()
    tlo, thi = args.base, args.base + 0x160

    d = open(args.dll, 'rb').read()
    # 简化：整个文件按 VA=0x1000 ↔ off=0x400 线性映射（本 DLL 的 .text 覆盖 0x1000..0xC000）
    code = d[0x400:0x400 + 0xC000]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)

    cur = None
    res = {}
    nc = 0
    for ins in md.disasm(code, 0x1000):
        if ins.address < args.lo or ins.address > args.hi:
            continue
        if ins.mnemonic == "cmp" and ins.op_str.startswith("eax"):
            m = re.search(r',\s*(0x[0-9a-f]+|\d+)\s*$', ins.op_str)
            if m:
                cur = int(m.group(1), 16) if m.group(1).startswith('0x') else int(m.group(1)); nc += 1
        if ins.mnemonic != "mov":
            continue
        m = PAT.search(ins.op_str)
        if not m or not m.group(2):
            continue
        tgt = ins.address + ins.size + int(m.group(1), 16)
        if not (tlo <= tgt <= thi):
            continue
        # ⚠️ 注意顺序：'dword' 里含 'word' ⇒ 必须先判 dword
        w = 4 if 'dword' in ins.op_str else (2 if 'word' in ins.op_str else 1)
        res.setdefault(cur, {}).setdefault(tgt, (int(m.group(2), 16), w, ins.address))

    print("=" * 92)
    print("家族分支表 —— %s" % os.path.basename(args.dll))
    print("扫描窗口 0x%X–0x%X，识别到 %d 个 cmp 分支标记、%d 个分支有表写入" % (
        args.lo, args.hi, nc, len([k for k in res if isinstance(k, int)])))
    print("=" * 92)
    for k in sorted(x for x in res if isinstance(x, int)):
        v = res[k]
        print("\n### 分支 [0x18B00] == %s      字段 %d 个" % (k, len(v)))
        for tgt in sorted(v):
            imm, w, ia = v[tgt]
            print("   %-22s 0x%06X = 0x%0*X   (宽%d  @0x%06X)" % (
                LBL.get(tgt, "0x%06X" % tgt), tgt, w * 2, imm, w, ia))
    if not [k for k in res if isinstance(k, int)]:
        print("\n（未命中。检查 cmp 解析与窗口。）")


if __name__ == "__main__":
    main()
