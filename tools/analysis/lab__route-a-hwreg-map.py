# route-a-hwreg-map.py —— 用官方固件源码里的 HW 寄存器定义表，交叉读一遍本机实测值
#
# 目的：判断 "0x2218 (HW_REG_SCRAMBLE) 读到 0x00" 到底有没有意义 ——
#       如果 0x2xxx 这一整块寄存器在【应用模式】下都可读且都有合理值，
#       那么 0x2218=0x00 就是【真值】而非"未映射/模式不对"的假象。
#
# 依据：gtx8_driver_linux/goodix_gtx8_update.c:27-48 的 #define 表
#
# ★ 全程零写入。

import sys
import time
from datetime import datetime
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gxhid import GxChannel, hx, asc, health

PACE = 0.6
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "route-a-hwreg-map-log.txt")
_lines = []


def W(s):
    print(s, flush=True)
    _lines.append(s)


# (地址, 官方宏名, 说明)
REGS = [
    (0x2010, "HW_REG_DSP_MCU_POWER", "DSP&MCU 电源（升级流程里写 0x00 使能）"),
    (0x2014, "HW_REG_GIO_YS", "GIO（Yellowstone）"),
    (0x2048, "HW_REG_BANK_SELECT", "bank 选择"),
    (0x204B, "HW_REG_CACHE", "cache（升级流程里写 0x00 清）"),
    (0x204D, "HW_REG_ACCESS_PATCH0", "访问 patch0"),
    (0x204F, "HW_REG_EC_SRM_START", "EC SRM 起始"),
    (0x20B0, "HW_REG_WTD_TIMER", "看门狗定时器（升级流程里写 0x00 关）"),
    (0x2180, "HW_REG_CPU_CTRL", "CPU_CTRL：0x00=PENDING / 0x01=RUNNING"),
    (0x2184, "HW_REG_RESET", "复位"),
    (0x2318, "HW_REG_ESD_KEY(_EN)", "ESD key（非 YS 分支写 0x95/0x27）"),
    (0x2324, "HW_REG_ESD_KEY_DIS", "ESD key 禁用"),
    (0x4000, "HW_REG_CPU_RUN_FROM_YS", "★ CPU 从哪跑（YS）"),
    (0x4506, "HW_REG_CPU_RUN_FROM", "CPU 从哪跑（nor_L 版是 0x4006）"),
    (0x6006, "HW_REG_ISP_RUN_FLAG", "★ ISP 运行标志"),
    (0x6020, "HW_REG_SUBSYS_TYPE", "子系统类型"),
    (0x6022, "HW_REG_FLASH_FLAG", "flash 标志"),
]

ANCHORS = [
    (0x4014, "VER", "版本寄存器（已知 00 87 00 00）"),
    (0x452C, "fw_info", "已知有数据 AE EB 60 90"),
    (0x4160, "CMD", "命令寄存器（空闲应为 FF FF FF FF）"),
]

W("=== 路线 A · HW 寄存器定义表 × 本机实测 :: %s ===" % datetime.now().isoformat(timespec='seconds'))
W("全程只读，零写入。")

ch = GxChannel()
ok, info = ch.open()
W("Col04 open: %s  %s" % (ok, info))
if not ok:
    W("ABORT")
    sys.exit(1)

# ── 健康门 ──
W("")
W("--- ① 健康门 ---")
hok, d = health(ch)
W("  0x4018 :: %s   [%s]" % (hx(d), asc(d)))
if not hok:
    W("  ❌ 健康门未通过 ⇒ ABORT")
    ch.close()
    sys.exit(2)
W("  ✅ YELSTO，通过")
time.sleep(PACE)
d, lg = ch.read(0x4014, 4)
W("  0x4014 :: %s   (版本)" % hx(d))
time.sleep(PACE)

# ── ② ★ 目标：0x2218 ──
W("")
W("--- ② ★ 目标 HW_REG_SCRAMBLE = 0x2218 ---")
d, lg = ch.read(0x2218, 4)
W("  0x2218 :: %s   [%s]   (%s)" % (hx(d), asc(d), lg))
time.sleep(PACE)

# ── ③ 官方 HW 寄存器表 ──
W("")
W("--- ③ 官方 HW 寄存器表实测（gtx8_driver_linux #define 表）---")
W("  地址    实测值              官方宏")
for addr, name, note in REGS:
    d, lg = ch.read(addr, 4)
    val = hx(d) if d else "<读失败>"
    W("  0x%04X  %-18s  %-26s %s" % (addr, val, name, note))
    time.sleep(PACE)

# ── ④ 已知锚点 ──
W("")
W("--- ④ 已知锚点对照（证明通道与地址空间正确）---")
for addr, name, note in ANCHORS:
    d, lg = ch.read(addr, 4)
    W("  0x%04X  %-18s  [%-4s]  %s" % (addr, hx(d), asc(d), note))
    time.sleep(PACE)

# ── ⑤ 收尾健康 ──
W("")
W("--- ⑤ 收尾健康检查 ---")
hok2, d2 = health(ch)
W("  0x4018 :: %s   [%s]" % (hx(d2), asc(d2)))
W("  %s" % ("✅ 与开读前一致" if hok2 else "⚠ 与开读前不一致"))

ch.close()
W("")
W("完成（全程只读，零写入）。")

with open(LOG_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(_lines) + "\n")
print("\n[log] " + LOG_PATH)
