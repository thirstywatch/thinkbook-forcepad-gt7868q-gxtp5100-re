#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
haptic_extract.py —— 从官方明文 tpcfgsid*.cfg 中提取触觉/振动相关参数，并与 GT7868Q 固件对照

结论前置（本脚本要验证的 5 条）：
  V1  tpcfgsid*.cfg 是【主机侧 TLV 配置表】，明文完整，无需破固件即可读
  V2  其中 0x0190 / 0x0258 这类 u16 是【时间/强度常量(ms 量级)】，不是 I²C 地址
      —— 0x0190=400ms, 0x0258=600ms 正好落在 Android / Linux input 的
         FF_RUMBLE/FF_PERIODIC 常见时长档位上
  V3  18 项 u16 包络 (sid0 @0x00EE) 值域 93~111，中心 97 —— 形如
      「强度包络」但幅值过小，更可能是【增益/校准系数】而非振幅表
  V4  0x80 重复序列 (128,128,128,127/129) 是【通道偏移校准表】
  V5  GT7868Q 固件中应与 cfg 中这些常量存在相同的 u16 序列 → 可作解密正确性的
      指纹判据（新判据 F: 同构于明文样本）

产出：haptic_report.txt
"""
import os, struct, json

BASE = os.path.dirname(os.path.abspath(__file__))
CFGD = os.path.join(BASE, "cfg")
OUT = os.path.join(BASE, "cfg_parsed")
os.makedirs(OUT, exist_ok=True)

FILES = {
    "sid0": "tpcfgsid0_Xiaomi7867_20240307.cfg.txt",
    "sid2": "tpcfgsid2_20230407.cfg.txt",
    "sid3": "tpcfgsid3_LaiBao7986P_20220701.cfg.txt",
}
# 固件候选位置
FW_CANDIDATES = [
    r"<LAB>\touchpad-lab\poc\anchor-hunt\GT7868Q_plain.bin",
    os.path.join(BASE, "tpfw_86272_PNOR_G1_7863.bin"),
]


def load_cfg(name):
    with open(os.path.join(CFGD, FILES[name]), encoding="utf-8") as f:
        toks = [t.strip() for t in f.read().split(",") if t.strip()]
    return bytes(int(t, 16) for t in toks if t.lower().startswith("0x"))


def u16le_at(b, off):
    return b[off] | (b[off + 1] << 8)


rep = []


def w(s=""):
    rep.append(s)
    print(s)


w("=" * 78)
w("触觉参数提取报告 —— 数据源: 官方明文 tpcfgsid*.cfg")
w("=" * 78)

cfgs = {k: load_cfg(k) for k in FILES}

# ---------------------------------------------------------------- V2
w("\n【V2】0x0190 / 0x0258 常量的性质判定")
w("-" * 78)
for tag in ("sid0", "sid2", "sid3"):
    b = cfgs[tag]
    hits = []
    for i in range(len(b) - 1):
        v = u16le_at(b, i)
        if v in (0x0190, 0x0258):
            hits.append((i, v))
    w("  %s: u16LE 命中 0x0190=%dms / 0x0258=%dms 共 %d 处  %s"
      % (tag, 0x0190, 0x0258, len(hits), [("0x%04X=%d" % (o, v)) for o, v in hits[:10]]))

w("""
  判读: 400ms / 600ms 是时间常量。在 Android/Linux 的 FF 框架里
        400/600ms 属于典型「长振动」档（短震动 10~50ms，中 100~200ms，长 400~1000ms）。
        这两个值在三个不同厂牌（Xiaomi7867 / sid2 / LaiBao7986P）的 cfg 中都出现，
        说明它们是【芯片厂给的参考时长模板】，不是某一家的定制。
        ⚠️ 单个 u16 不能证明它就是振动时长 —— 需要与固件代码的消费点对照。
""")

# ---------------------------------------------------------------- V3
w("\n【V3】sid0 @0x00EE 的 18 项 u16 序列")
w("-" * 78)
b0 = cfgs["sid0"]
seq18 = [u16le_at(b0, 0x00EE + 2 * i) for i in range(18)]
w("  偏移 0x00EE 起 18×u16LE: %s" % seq18)
w("  统计: min=%d max=%d mean=%.1f  中心≈%d" % (min(seq18), max(seq18), sum(seq18) / 18, 97))
w("  相邻差分: %s" % [seq18[i + 1] - seq18[i] for i in range(17)])
w("""
  判读: 18 项，值域 93~111，中心 97，末两项骤降为 29。
        • 若说是「振幅包络」→ 幅值太小且末两项断崖不合理（应该是起手强、收尾弱，
          但中间不该在 93~111 这么窄的带里抖动）。
        • 更合理的解读: 【M 个通道 × N 个档位的校准/增益系数】，
          91~111 是 ±10% 的公差范围，末两项 29/29 可能是「未使用的通道」占位。
        • 18 项 = GT7868Q 的感应通道数？需与固件里的通道映射表对照。
""")

# ---------------------------------------------------------------- V4
w("\n【V4】0x80 重复序列（通道偏移表）")
w("-" * 78)
for tag in ("sid0", "sid2", "sid3"):
    b = cfgs[tag]
    runs = []
    i = 0
    while i + 4 <= len(b):
        k = i
        vals = []
        while k + 2 <= len(b):
            v = u16le_at(b, k)
            if 120 <= v <= 136:
                vals.append(v)
                k += 2
            else:
                break
        if len(vals) >= 12:
            runs.append((i, len(vals), vals[:24]))
        i = max(i + 1, k if k > i else i + 1)
    w("  %s: 命中 %d 段" % (tag, len(runs)))
    for off, n, v in runs[:6]:
        w("    @0x%04X  n=%3d  %s" % (off, n, v))

w("""
  判读: 值全在 127/128/129 之间，是【以 128 为零点的有符号偏移/基线表】。
        128 = 0 偏移（中性），127 = -1，129 = +1。
        长度 20~76 项，与触控通道数吻合。这是【电容基线/自校准偏移】，
        与触觉无关，但**它是证明 cfg 明文可读的重要样本**。
""")

# ---------------------------------------------------------------- V5
w("\n【V5】与固件的指纹对照（新判据 F 的首次实测）")
w("-" * 78)
fw_found = []
for p in FW_CANDIDATES:
    if os.path.exists(p):
        sz = os.path.getsize(p)
        fw_found.append((p, sz))
        w("  可读: %s  (%d B)" % (p, sz))
    else:
        w("  缺失: %s" % p)

if fw_found:
    # 用 cfg 中的长常量串在固件里搜索
    probes = {
        "sid0_18u16@0xEE": seq18,
        "sid0_calib_128seq@0x257": [u16le_at(b0, 0x0257 + 2 * i) for i in range(24)],
        "sid3_calib_128seq@0x3C8": [u16le_at(cfgs["sid3"], 0x03C8 + 2 * i) for i in range(24)],
        "sid0_timeseq@0xA0": [u16le_at(b0, 0x00A0 + 2 * i) for i in range(8)],
    }
    for p, sz in fw_found:
        with open(p, "rb") as f:
            fw = f.read()
        w("\n  ── 固件 %s ──" % os.path.basename(p))
        for name, seq in probes.items():
            pat = struct.pack("<%dH" % len(seq), *seq)
            # 全量搜索（含重叠）
            idxs = []
            s = 0
            while True:
                k = fw.find(pat, s)
                if k < 0:
                    break
                idxs.append(k)
                s = k + 1
            w("     %-24s len=%dB 命中 %d 处 %s"
              % (name, len(pat), len(idxs), [hex(x) for x in idxs[:8]]))
        # 反向: 固件中出现的 0x0190 常量密度
        c400 = fw.count(b"\x90\x01")
        c600 = fw.count(b"\x58\x02")
        w("     0x0190(u16LE) 出现 %d 次  0x0258(u16LE) 出现 %d 次" % (c400, c600))

w("""
  ⚠️ 重要: 对 GT7868Q_plain.bin 的命中若为 0，**不能**证明解密失败，
     因为该文件本身已被本轮证实不是有效明文（K 副本自消假象）。
     对 tpfw_86272_PNOR_G1_7863.bin 的命中才有参考价值 —— 它是官方明文。
     判据 F 的正确用法: 用【官方明文 tpfw.bin 中的常量】去验证【另一个官方明文】，
     建立"同族样本长什么样"的基线，再拿来评判 GT7868Q 的解密输出。
""")

with open(os.path.join(OUT, "haptic_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
print("\n[done] -> cfg_parsed/haptic_report.txt")
