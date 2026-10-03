#!/usr/bin/env python3
"""aw86927_bus_decode.py - 把逻辑分析仪抓到的 I²C 波形，变成"可重放的写表"。

定位
----
蓝莓手上的关键成果是一份 (地址, 数据) 写序列（SurfaceGetCS40L25 的 167 块）。
本机那份等价物不在固件里，而在【上电时 GT7868Q → AW86927 的私有 I²C 总线】上。
这个脚本的唯一职责：把逻辑分析仪导出的 I²C 解码结果，变成同样形态的东西。

它做四件事
----------
1. 地址普查      —— 一次抓包里出现过哪些 7 位从地址，各多少事务多少字节
                    ★ 只要看有没有 0x5A/0x5B，就能判"触觉链路当前是否启用"
2. 大块连续写    —— payload 长、寄存器地址连续的事务段 = 波形下载候选
3. 初始化表      —— 连续短写（reg,val）序列 = 寄存器初始化表候选（形态同 Surface 那 71 项）
4. 可重放表      —— 导出 aw86927_replay.json / .h（seq, addr7, reg, data, crc16）

用法
----
  python aw86927_bus_decode.py --in capture.csv
  python aw86927_bus_decode.py --in capture.csv --sniff      # 只打印解析诊断，不做分析
  python aw86927_bus_decode.py --selftest                    # 合成阳性对照，验证工具本身

支持的输入
----------
  A) Saleae Logic 2 / DSView 等导出的 I²C 解码 CSV（按表头关键字自动识别列）
  B) 简易 CSV：t,addr,rw,data   （addr 形如 0x5A，rw 为 W/R 或 0/1，data 为空格分隔的十六进制）
  C) 只有一列十六进制字节的原始导出（会走保守解析）
  若识别不准：先跑 --sniff 看工具读成了什么，再按 B 的格式自己转一遍（最稳）。

★ 纪律：本工具必须在【已知样本】上先通过自检（--selftest），
  才允许用它去判未知抓包 —— 否则会把解析器的 bug 当成"设备没反应"。
"""

from __future__ import annotations

import argparse
import binascii
import csv
import json
import math
import re
import struct
import sys
from collections import Counter, OrderedDict
from pathlib import Path

# ----------------------------------------------------------------- 器件常量

AW86927_ADDRS = {0x5A, 0x5B}          # 7 位从地址，由 AD 脚决定
TF100A_ADDR = 0x2C                    # 私有总线上的另一个从机（干扰源，要排除）
HOST_TPAD_ADDR = 0x01                 # 主机总线上的触控板（另一条总线，正常不该出现）

# 来自 AW86927FCR.pdf 数据手册的寄存器名（page 24/25 抽出）
AW86927_REGS = {
    0x00: "SRST(RO,CHIP_ID)", 0x01: "SYSST", 0x02: "SYSINT", 0x03: "SYSINTM",
    0x06: "PLAYCFG1(BST_MODE,BST_VOUT_VREFSET)", 0x07: "PLAYCFG2(GAIN)",
    0x08: "PLAYCFG3(AUTO_BST,STOP_MODE,BRK_EN,PLAY_MODE)", 0x09: "PLAYCFG4(STOP,GO)",
    0x0A: "WAVCFG1", 0x0B: "WAVCFG2", 0x0C: "WAVCFG3", 0x0D: "WAVCFG4", 0x0E: "WAVCFG5",
    0x0F: "WAVCFG6",
    0x1D: "CONTCFG6", 0x1E: "CONTCFG7", 0x1F: "CONTCFG8", 0x20: "CONTCFG9",
    0x21: "CONTCFG10", 0x22: "CONTCFG11",
    0x25: "CONTRD14", 0x26: "CONTRD15", 0x27: "CONTRD16", 0x28: "CONTRD17",
    0x2D: "RTPCFG1", 0x2E: "RTPCFG2", 0x2F: "RTPCFG3", 0x30: "RTPCFG4", 0x31: "RTPCFG5",
    0x32: "RTPDATA", 0x33: "TRGCFG1", 0x34: "TRGCFG2", 0x35: "TRGCFG3", 0x36: "TRGCFG4",
    0x37: "TRGCFG5", 0x38: "TRGCFG6", 0x39: "TRGCFG7", 0x3A: "TRGCFG8",
    0x3E: "GLBCFG4(TRIG_PRIO,TRIG_x_STOP/BRK/BST/ONEWIRE)", 0x3F: "GLBRD5(GLB_STATE[3:0])",
    0x45: "SYSCTRL3", 0x46: "SYSCTRL4",
    0x48: "PWMCFG1", 0x49: "PWMCFG3", 0x4A: "PWMCFG4", 0x4C: "VBAT_CTRL",
    0x4D: "DETCFG1", 0x4E: "DETCFG2", 0x4F: "DET_RD1", 0x50: "DET_RD2", 0x51: "DET_RD3",
    0x57: "IDH", 0x58: "IDL",
}

GLB_STATE = {
    0x0: "STANDBY", 0x6: "CONT", 0x7: "RAM", 0x8: "RTP", 0x9: "TRIG", 0xB: "BRAKE",
}


def reg_name(reg: int) -> str:
    return AW86927_REGS.get(reg, "")


# ----------------------------------------------------------------- 抓包解析

class Txn:
    """一次 I²C 事务：从地址 + 方向 + 字节流。"""

    __slots__ = ("t", "addr", "write", "data")

    def __init__(self, t, addr, write, data):
        self.t, self.addr, self.write, self.data = t, addr, write, data

    @property
    def n(self):
        return len(self.data)

    def __repr__(self):
        d = self.data
        head = d[:12].hex(" ")
        more = f" …(+{len(d)-12})" if len(d) > 12 else ""
        return (f"t={self.t:9.6f} addr=0x{self.addr:02X} "
                f"{'W' if self.write else 'R'} n={len(d):5}  {head}{more}")


HEXTOK = re.compile(r"^(?:0x)?([0-9A-Fa-f]{1,4})$")
ADDRTOK = re.compile(r"^(?:0x)?([0-9A-Fa-f]{2})$")


def _hexbytes(s: str):
    """把 '0x01 0x02' / '01 02' / '0102' 解析成 bytes；失败返回 None。"""
    s = s.strip()
    if not s:
        return None
    toks = re.findall(r"0x[0-9A-Fa-f]{1,2}|[0-9A-Fa-f]{2}(?![0-9A-Fa-f])", s)
    if not toks:
        return None
    try:
        return bytes(int(t, 16) for t in toks)
    except ValueError:
        return None


def parse_capture(path: Path, sniff: bool = False):
    """宽容解析。返回 (txns, notes)。"""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    notes = []
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return [], ["空文件"]

    # 找表头行
    hdr_i = None
    for i, r in enumerate(rows[:20]):
        joined = " ".join(r).lower()
        if ("address" in joined or "addr" in joined) and ("data" in joined or "value" in joined):
            hdr_i = i
            break
        if "time" in joined and ("data" in joined or "packet" in joined):
            hdr_i = i
            break

    if hdr_i is not None:
        hdr = [c.strip().lower() for c in rows[hdr_i]]
        def col(*keys):
            for k in keys:
                for j, h in enumerate(hdr):
                    if k in h:
                        return j
            return None
        ci_time = col("time", "t [", "timestamp")
        ci_addr = col("address", "addr")
        ci_data = col("data", "value", "byte")
        ci_type = col("packet", "type", "packet type", "direction", "rw")
        notes.append(f"表头@{hdr_i}: time={ci_time} addr={ci_addr} data={ci_data} type={ci_type}")
        body = rows[hdr_i + 1:]
    else:
        notes.append("无表头 ⇒ 按简易格式 t,addr,rw,data 解析")
        ci_time, ci_addr, ci_data, ci_type = 0, 1, 2, 3
        body = rows

    txns, notes_out = _assemble(body, ci_time, ci_addr, ci_data, ci_type, sniff)
    return txns, notes + notes_out


def _cell(row, idx):
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def _assemble(body, ci_time, ci_addr, ci_data, ci_type, sniff):
    """状态机：遇到「地址行」就开新事务，后续「数据行」并入其中。"""
    txns = []
    notes = []
    cur_addr = None
    cur_write = True
    cur_data = bytearray()
    cur_t = 0.0
    sniffed = 0

    def flush():
        nonlocal cur_addr, cur_data
        if cur_addr is not None and cur_data:
            txns.append(Txn(cur_t, cur_addr, cur_write, bytes(cur_data)))
        cur_addr = None
        cur_data = bytearray()

    for row in body:
        if not row or not any(c.strip() for c in row):
            continue
        tcell = _cell(row, ci_time)
        try:
            t = float(re.sub(r"[^\d.eE+-]", "", tcell) or 0)
        except ValueError:
            t = 0.0

        acell = _cell(row, ci_addr)
        dcell = _cell(row, ci_data)
        ycell = _cell(row, ci_type)

        # 地址单元：形如 0x5A / 5A / "0x5A Write" / "0x5A, Read"
        addr = None
        m = re.search(r"(?:0x)?([0-9A-Fa-f]{2})\b", acell)
        if m and acell and not re.fullmatch(r"\s*", acell):
            addr = int(m.group(1), 16)

        # 简易格式：地址在“地址列”，数据在“数据列”
        if addr is None and ci_addr is not None and ci_data is not None and dcell and not acell:
            pass

        if sniff and sniffed < 30:
            notes.append(f"ROW t={tcell!r} addr={acell!r} data={dcell!r} type={ycell!r}")
            sniffed += 1

        if addr is not None:
            flush()
            cur_addr = addr
            low = ycell.lower() + " " + acell.lower()
            cur_write = not ("read" in low or low.strip().endswith(" r"))
            if "r" == ycell.lower().strip():
                cur_write = False
            cur_t = t
            # 同一行里可能直接带数据
            dd = _hexbytes(dcell)
            if dd:
                cur_data += dd
            continue

        # 非地址行 ⇒ 数据
        for cell in (dcell, acell):
            if not cell:
                continue
            dd = _hexbytes(cell)
            if dd:
                cur_data += dd
                if cur_t == 0.0:
                    cur_t = t
                break
        else:
            # 兼容：地址与数据写在同一行（简易格式）
            low = (acell + " " + ycell).lower()
            m2 = re.search(r"(?:0x)?([0-9A-Fa-f]{2})", acell)
            if m2 and dcell:
                flush()
                cur_addr = int(m2.group(1), 16)
                cur_write = not ("r" == ycell.lower().strip() or "read" in low)
                cur_t = t
                dd = _hexbytes(dcell)
                if dd:
                    cur_data += dd

    flush()
    return txns, notes


# ----------------------------------------------------------------- 分析

def analyse(txns):
    rep = OrderedDict()
    byaddr = OrderedDict()
    for t in txns:
        a = byaddr.setdefault(t.addr, {"w": 0, "r": 0, "wr_bytes": 0, "rd_bytes": 0, "max": 0})
        if t.write:
            a["w"] += 1
            a["wr_bytes"] += t.n
            a["max"] = max(a["max"], t.n)
        else:
            a["r"] += 1
            a["rd_bytes"] += t.n

    rep["地址普查"] = [
        {"addr7": f"0x{k:02X}", "写": v["w"], "读": v["r"],
         "写字节": v["wr_bytes"], "读字节": v["rd_bytes"], "单次最长写": v["max"],
         "note": ("★ 目标器件 AW86927" if k in AW86927_ADDRS
                  else "TF100A（私有总线上的另一个从机，属噪声）" if k == TF100A_ADDR
                  else "主机总线触控板（正常不该出现在私有总线上）" if k == HOST_TPAD_ADDR
                  else "")}
        for k, v in sorted(byaddr.items())
    ]

    hits = sorted(set(byaddr) & AW86927_ADDRS)
    rep["AW86927_是否出现"] = {
        "出现": bool(hits),
        "地址": [f"0x{h:02X}" for h in hits],
        "判读": ("有名有姓 ⇒ 触觉链路被用过，继续往下解" if hits else
                 "★ 完全没有对 0x5A/0x5B 的访问 ⇒ 触觉链路当前未启用（这本身就是结论）"),
    }

    # 大块写 → 波形下载候选
    big = [t for t in txns if t.addr in AW86927_ADDRS and t.write and t.n >= 32]
    runs = []
    if big:
        cur = [big[0]]
        for t in big[1:]:
            if t.addr == cur[-1].addr and (t.t - cur[-1].t) < 0.5:
                cur.append(t)
            else:
                runs.append(cur)
                cur = [t]
        runs.append(cur)
    rep["大块写_波形下载候选"] = [
        {"addr7": f"0x{r[0].addr:02X}", "事务数": len(r),
         "总字节": sum(x.n for x in r),
         "净载荷": sum(x.n - 1 for x in r),      # 扣掉每个事务首字节的寄存器地址
         "事务长度": sorted({x.n for x in r}),
         "t0": round(r[0].t, 6), "t1": round(r[-1].t, 6)}
        for r in runs
    ]

    # 初始化表 → 连续短写 (reg,val)
    init = []
    for t in txns:
        if t.addr in AW86927_ADDRS and t.write and 1 <= t.n <= 3:
            init.append((t.data[0], t.data[1] if t.n > 1 else None))
    rep["初始化表候选"] = {
        "条数": len(init),
        "前40条": [{"reg": f"0x{r:02X}", "name": reg_name(r),
                    "val": (None if v is None else f"0x{v:02X}")} for r, v in init[:40]],
    }

    # GLB_STATE
    glb = []
    for t in txns:
        if t.addr in AW86927_ADDRS:
            if t.write and t.n >= 2 and t.data[0] == 0x3F:
                glb.append({"方向": "写", "值": f"0x{t.data[1]:02X}",
                            "GLB_STATE": GLB_STATE.get(t.data[1] & 0x0F, "?")})
            elif (not t.write) and t.n >= 1 and t.data[0] == 0x3F and t.n >= 2:
                glb.append({"方向": "读", "值": f"0x{t.data[1]:02X}",
                            "GLB_STATE": GLB_STATE.get(t.data[1] & 0x0F, "?")})
    rep["GLB_STATE_0x3F"] = glb or "未出现（没读到/写到 0x3F）"

    return rep


def build_replay(txns, origin=0.0):
    table = []
    for t in txns:
        if t.addr not in AW86927_ADDRS or not t.write:
            continue
        table.append({
            "seq": len(table),
            "t_rel_ms": round((t.t - origin) * 1000, 3),
            "addr7": t.addr,
            "reg": t.data[0] if t.n else None,
            "reg_name": reg_name(t.data[0]) if t.n else "",
            "data": t.data.hex(),
            "len": t.n,
            "crc16": f"{binascii.crc_hqx(t.data, 0xFFFF):04X}",
        })
    return table


def write_replay(table, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "aw86927_replay.json").write_text(
        json.dumps(table, indent=1, ensure_ascii=False), encoding="utf-8")

    lines = ["/* aw86927_replay.h - 由抓包自动生成的可重放写表",
             " * 用法：按 seq 顺序，把 data 的 len 个字节整体写到 addr7（data[0] 即寄存器地址）。",
             " * 这是本机版的\"167 块\"：拿到它，就等于拿到了蓝莓手里的那份东西。 */",
             "#pragma once", "#include <stdint.h>", "",
             "typedef struct { uint8_t addr7; uint8_t reg; uint8_t len; const uint8_t *data; } aw_step_t;", ""]
    for e in table:
        b = bytes.fromhex(e["data"])
        arr = ", ".join(f"0x{x:02X}" for x in b)
        lines.append(f"static const uint8_t s{e['seq']:04d}[{e['len']}] = {{ {arr} }};")
    lines += ["", f"#define AW_REPLAY_STEPS {len(table)}", "",
              "static const aw_step_t g_replay[] = {"]
    for e in table:
        lines.append(f"    {{ 0x{e['addr7']:02X}, 0x{(e['reg'] or 0):02X}, {e['len']}, s{e['seq']:04d} }},  /* {e['reg_name']} */")
    lines += ["};", ""]
    (outdir / "aw86927_replay.h").write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------- 自检

def selftest():
    """合成一段"阳性对照"抓包，验证解析 + 识别全链路。
    合成的成分（都能被脚本自己复述出来才算通过）：
      0x2C 的噪声事务（TF100A）
      0x5A 的 12 条初始化短写（含 0x08 PLAYCFG3、0x3F GLB_STATE=TRIG）
      0x5A 的 8 KB 分页大块写（32 × 256 B），reg 逐页递增
      0x5B 的少量写（验证两个地址都认）
    """
    rows = ["time,addr,rw,data"]
    t = 0.0

    def add(addr, w, data, dt=0.0002):
        nonlocal t
        t += dt
        rows.append(f"{t:.6f},0x{addr:02X},{'W' if w else 'R'},"
                    + " ".join(f"{b:02X}" for b in data))

    for _ in range(3):
        add(0x2C, True, [0xA2, 0x11, 0x22])
    add(0x2C, False, [0xA2, 0x00])

    init = [(0x00, 0x00), (0x06, 0x58), (0x07, 0x80), (0x08, 0x14), (0x09, 0x00),
            (0x0A, 0x01), (0x0B, 0x00), (0x0C, 0x00), (0x3E, 0x00), (0x45, 0x00),
            (0x46, 0x00), (0x3F, 0x09)]
    for r, v in init:
        add(0x5A, True, [r, v])

    WAV = bytes((i * 37 + 11) & 0xFF for i in range(8192))
    for p in range(32):
        add(0x5A, True, [0x32] + list(WAV[p * 256:(p + 1) * 256]), dt=0.002)

    for r, v in [(0x06, 0x58), (0x3F, 0x09)]:
        add(0x5B, True, [r, v])

    csv_path = Path("selftest_capture.csv")
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    txns, notes = parse_capture(csv_path, sniff=False)
    rep = analyse(txns)
    aw = rep["AW86927_是否出现"]
    big = rep["大块写_波形下载候选"]
    ini = rep["初始化表候选"]

    print(f"[自检] 解析出事务 {len(txns)} 个")
    print(f"[自检] AW86927 出现 = {aw['出现']} {aw['地址']}")
    print(f"[自检] 大块写段 = {len(big)}  明细 = {big}")
    print(f"[自检] 初始化候选条数 = {ini['条数']}（期望 12 条 0x5A + 2 条 0x5B = 14）")
    print(f"[自检] GLB_STATE 记录 = {rep['GLB_STATE_0x3F']}")

    # 期望：AW86927 出现；识别出 1 段大块写且净载荷正好 8192（= 8 KB 波形 SRAM）；
    #       初始化候选 14 条；GLB_STATE 解出 TRIG
    ok = (aw["出现"]
          and len(big) == 1
          and big[0]["净载荷"] == 8192
          and big[0]["事务数"] == 32
          and ini["条数"] == 14
          and rep["GLB_STATE_0x3F"] and rep["GLB_STATE_0x3F"][0]["GLB_STATE"] == "TRIG")
    print("[自检]", "PASS ✅ 解析器可信，可用它去判真实抓包" if ok else "FAIL ❌ 先修工具，别用它下结论")
    return 0 if ok else 1


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp")
    ap.add_argument("--sniff", action="store_true", help="只打印解析诊断")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if not a.inp:
        ap.print_help()
        return 2

    txns, notes = parse_capture(Path(a.inp), sniff=a.sniff)
    print("== 解析诊断 ==")
    for n in notes:
        print("   ", n)
    print(f"== 解析出 {len(txns)} 个事务 ==")
    for t in txns[:20]:
        print("   ", t)

    if a.sniff:
        return 0
    if not txns:
        print("\n!! 没能解析出任何事务 —— 先解决格式问题，不要据此下任何结论")
        return 1

    rep = analyse(txns)
    print("\n== 分析 ==")
    print(json.dumps(rep, indent=1, ensure_ascii=False))

    table = build_replay(txns)
    write_replay(table, Path(a.outdir))
    print(f"\n== 可重放表：{len(table)} 条 -> {a.outdir}/aw86927_replay.json · .h ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
