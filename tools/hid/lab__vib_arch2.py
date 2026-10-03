# vib_arch2.py — 把 dispatcher 0x080091C0 完整解出来：命令类字节 / 16 位子命令 / 每个 handler 干了什么
#               顺带：全镜像的"越界调用"、外设基址、消息结构体的写入者
import re, struct, io
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG_OFF = 0x19ABC
img = data[IMG_OFF:]
BASE = 0x08000000
END = BASE + len(img)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True          # 关键：数据区不失步
out = io.open(r"<LAB>\touchpad-lab\re\vib_arch2_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")

P("image 0x%08X..0x%08X  len=%d" % (BASE, END, len(img)))

allins = list(md.disasm(img, BASE))
P("总指令数 %d" % len(allins))
byaddr = {}
for i in allins:
    byaddr[i.address] = i


def show(a, n, title, ind="  "):
    P("\n===== %s @0x%08X =====" % (title, a))
    c = 0
    for i in allins:
        if i.address < a:
            continue
        P("%s%08X: %-10s %s" % (ind, i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))
        c += 1
        if c >= n:
            break


# ---------- 1) dispatcher 全貌 ----------
show(0x080091C0, 260, "dispatcher 0x080091C0 (前 260 条)")

# ---------- 2) dispatcher 里所有分支目标 = handler ----------
P("\n" + "=" * 78)
P("=== dispatcher 中的分支目标（候选 handler） ===")
disp = [i for i in allins if 0x080091C0 <= i.address < 0x08009410]
tgts = []
for i in disp:
    if i.mnemonic in ("beq", "bne", "b", "beq.w", "bne.w", "bl", "bl.w", "cbz", "cbnz") and i.op_str.startswith("#"):
        t = int(i.op_str[1:], 16)
        tgts.append((i.address, t, i.mnemonic))
seen = set()
for a, t, m in tgts:
    if t in seen:
        continue
    seen.add(t)
    P("  %08X %-6s -> 0x%08X %s" % (a, m, t, "★越界" if not (BASE <= t < END) else ""))

# ---------- 3) 全镜像：越界调用 ----------
P("\n" + "=" * 78)
P("=== 全镜像中跳向镜像之外的目标（缺失尾部的入口线索） ===")
oob = []
for i in allins:
    if i.mnemonic.startswith("bl") or i.mnemonic in ("b", "bx") and i.op_str.startswith("#"):
        if i.op_str.startswith("#"):
            t = int(i.op_str[1:], 16)
            if not (BASE <= t < END):
                oob.append((i.address, t, i.mnemonic))
P("  越界目标数 = %d" % len(oob))
for a, t, m in oob[:60]:
    P("    %08X %-5s -> 0x%08X  (镜像外 +%d)" % (a, m, t, t - END if t >= END else -(BASE - t)))

# ---------- 4) 外设基址引用 ----------
P("\n" + "=" * 78)
P("=== 外设/关键地址引用统计 ===")
PERIPH = {
    0x40013800: "USART1", 0x40004400: "USART2", 0x40004800: "USART3",
    0x40005400: "I2C1", 0x40005800: "I2C2", 0x40005C00: "I2C3",
    0x40013000: "SPI1", 0x40003800: "SPI2", 0x40003C00: "SPI3",
    0x40012400: "ADC1", 0x40012800: "ADC2",
    0x40010000: "TIM2", 0x40000400: "TIM3", 0x40000800: "TIM4",
    0x40012C00: "TIM5", 0x40001000: "TIM6", 0x40001400: "TIM7", 0x40013400: "TIM8",
    0x40020000: "DMA1", 0x40020400: "DMA2",
    0x40010800: "GPIOA", 0x40010C00: "GPIOB", 0x40011000: "GPIOC",
    0x40011400: "GPIOD", 0x40011800: "GPIOE",
    0x40021000: "RCC", 0x40022000: "FLASH", 0x40010400: "EXTI",
    0xE000E100: "NVIC", 0xE000E000: "SCS",
}
hits = {}
for i in allins:
    for mm in re.finditer(r"#0x([0-9a-fA-F]+)", i.op_str):
        v = int(mm.group(1), 16)
        if v in PERIPH:
            hits.setdefault(v, []).append(i.address)
        elif 0x40000000 <= v < 0x50000000 and v not in PERIPH:
            hits.setdefault(v, []).append(i.address)
for v in sorted(hits):
    nm = PERIPH.get(v, "(未分类外设)")
    P("  0x%08X %-12s 引用 %3d 次  首处 %s" % (v, nm, len(hits[v]), " ".join("%X" % x for x in hits[v][:6])))

# ---------- 5) 消息结构体的写入者 ----------
P("\n" + "=" * 78)
P("=== 谁在写 0x20004128 / 0x20004134 / 0x20004940 附近 ===")
WATCH = [0x20004128, 0x20004134, 0x20004940, 0x200040E8]
for w in WATCH:
    P("  --- 0x%08X ---" % w)
    for i in allins:
        if ("#0x%X" % (w & 0xFFFF)) in i.op_str and ("0x2000" in i.op_str or True):
            P("      %08X %-8s %s" % (i.address, i.mnemonic, i.op_str))

out.close()
print("done")
