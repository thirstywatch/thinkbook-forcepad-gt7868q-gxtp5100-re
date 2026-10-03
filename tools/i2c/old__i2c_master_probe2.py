"""§五 判据 · 第二步：全镜像枚举 I2C1 相关访问与 HAL 调用点。

只读分析，不改动任何文件。
"""
import os, re, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
BIN  = os.path.join(HERE, "touchpad_GT7868Q_fw.bin")
ASM  = os.path.join(HERE, "touchpad_TF100A_thumb.asm.txt")
REGION_OFF, REGION_ADDR = 0x19ABC, 0x08005000

def addr2off(a): return a - REGION_ADDR + REGION_OFF

data = open(BIN, "rb").read()

# ---------- 完整向量表 ----------
VT = 0x08005000
words = struct.unpack_from("<80I", data, addr2off(VT))
NAMES = {1:"Reset",2:"NMI",3:"HardFault",4:"MemManage",5:"BusFault",6:"UsageFault",
         11:"SVC",12:"DebugMon",14:"PendSV",15:"SysTick"}
# STM32F1 IRQ 名称（仅列与本判据相关的）
IRQN = {11:"DMA1_Channel1",18:"ADC1_2",28:"TIM2",29:"TIM3",30:"TIM4",
        31:"I2C1_EV",32:"I2C1_ER",33:"I2C2_EV",34:"I2C2_ER",
        37:"USART1",38:"USART2",39:"USART3"}
print("=== 向量表（只列非默认项）===")
for i in range(1, 80):
    a = words[i]
    name = NAMES.get(i) or ("IRQ%d%s" % (i-16, " "+IRQN[i-16] if (i-16) in IRQN else "") if i >= 16 else "vec%d" % i)
    if a == 0x0800517F or a == 0:      # 默认 handler / 空
        continue
    print("  [%2d] %-16s = 0x%08X" % (i, name, a))

# ---------- 解析反汇编 ----------
rows = []
for l in open(ASM, encoding="utf-8"):
    l = l.rstrip()
    if not l.strip():
        continue
    p = l.split(None, 2)
    if len(p) < 2:
        continue
    try:
        pc = int(p[0], 16)
    except ValueError:
        continue
    rows.append((pc, p[1], p[2] if len(p) > 2 else ""))

# ---------- HAL 调用点 ----------
HAL = {0x0800FBF8:"wr_DR(+0x10)", 0x0800FC0C:"CR1 |= PE(0x01)", 0x0800FC20:"CR2 |= bit(IT)",
       0x0800FC44:"ClearFlag", 0x0800FC80:"GetFlagStatus", 0x0800F9CC:"CR1 |= ACK(0x400)",
       0x0800F9F8:"CR1 |= POS(0x800)", 0x0800FD24:"OAR1(+0x08)", 0x0800FA20:"I2C_Init",
       0x0800FE3C:"helper_FE3C", 0x0800F81C:"gpio_cfg", 0x080101D8:"clk_helper"}
calls = collections.defaultdict(list)
for pc, mn, ops in rows:
    if mn in ("bl", "blx", "b.w", "bl.w"):
        m = re.search(r"#(0x[0-9a-fA-F]+)", ops)
        if m:
            t = int(m.group(1), 16)
            if t in HAL:
                calls[t].append(pc)
print("\n=== I2C HAL 调用点 ===")
for t in sorted(calls):
    print("  0x%08X %-18s 被调用 %d 次:" % (t, HAL[t], len(calls[t])), " ".join("%08X" % s for s in calls[t]))

# ---------- 所有 I2C1 地址常量 ----------
print("\n=== 所有 'movw #0x54NN' 立即数（判定是否真是 0x4000_54NN）===")
for i, (pc, mn, ops) in enumerate(rows):
    if mn == "movw":
        m = re.search(r"#0x54([0-9a-fA-F]{2})", ops)
        if m:
            nxt = rows[i+1] if i+1 < len(rows) else None
            nxt2 = rows[i+2] if i+2 < len(rows) else None
            hi, hi_pc = None, None
            for c in (nxt, nxt2):
                if c and c[1] == "movt" and "#0x4000" in c[2]:
                    hi, hi_pc = 0x4000, c[0]
                    break
            tgt = "0x%08X" % (0x40000000 | int(m.group(1), 16)) if hi else "0x%08X (movt 非 0x4000)" % (0x08000000 | int(m.group(1), 16))
            print("  %08X  %-22s -> %s %s" % (pc, ops, tgt, "(★ I2C1)" if hi else ""))
