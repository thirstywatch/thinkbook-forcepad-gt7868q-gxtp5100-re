# vib_isr2.py — I2C1 从机 ISR + TIM3 触觉 ISR + 播放回调：命令帧格式与"何时震"的真身
import re, struct, io
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
img = open(BIN, "rb").read()[0x19ABC:]
BASE = 0x08000000
END = BASE + len(img)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
allins = list(md.disasm(img, BASE))
out = io.open(r"<LAB>\touchpad-lab\re\vib_isr2_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")

def show(a, b, title):
    P("\n===== %s [0x%08X..0x%08X] =====" % (title, a, b))
    for i in allins:
        if a <= i.address < b:
            P("  %08X: %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

show(0x08008940, 0x08008A40, "I2C1_ER(0x0800894D) / I2C1_EV(0x08008979) ISR")
show(0x0800D600, 0x0800D6A0, "TIM3 ISR (0x0800D629) —— 触觉状态机")
show(0x0800D6A0, 0x0800D780, "播放回调 0x0800D6F4 + 邻居")
show(0x0800D880, 0x0800DC60, "镜像末尾：调用缺失尾部的那段代码")

# 谁写 0x20004094 / 0x200040D0 / 0x200040E8（触觉状态与波形缓冲）
P("\n" + "=" * 78)
P("=== 关键 RAM 变量的读写者 ===")
WATCH = {0x4090: "ctx 周边", 0x4094: "状态字节", 0x40D0: "触觉 ctx", 0x40E8: "波形缓冲", 0x495E: "5.7KB 缓冲", 0x426C: "44B 结构"}
for k, nm in sorted(WATCH.items()):
    pat = "#0x%04X" % k
    sites = [i.address for i in allins if pat in i.op_str and "0x2000" not in i.op_str]
    P("  0x2000%04X (%s): %d 处 %s" % (k, nm, len(sites), " ".join("%X" % s for s in sites[:12])))
out.close()
print("done")
