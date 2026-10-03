# callgraph.py —— 正确的函数边界 + 调用图，从震动链向上溯源
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC
BASE = 0x08000000
img = data[IMG:]
END = BASE + len(img)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)


def dis_func(start, maxn=800):
    """从 start 单独反汇编（避免线性扫描失步）"""
    off = start - BASE
    if off < 0 or off >= len(img):
        return []
    code = bytes(img[off:off + maxn * 4])
    out = []
    for ins in md.disasm(code, start):
        out.append(ins)
        if ins.mnemonic in ("pop",) and "pc" in ins.op_str:
            break
        if ins.mnemonic == "bx" and ins.op_str.strip() == "lr":
            break
        if ins.mnemonic.startswith("b") and not ins.mnemonic.startswith("bl") and ins.mnemonic != "b":
            # 可能是 tail-call / 跳到别处；继续一点
            pass
    return out


# 1) 收集函数起点：向量表 + 所有 bl 目标
vec = [struct.unpack_from("<I", img, i * 4)[0] for i in range(76)]
starts = set()
for v in vec:
    if 0x08000000 <= v < END and v & 1:
        starts.add(v & ~1)

# 先用线性扫描找 bl 目标（即使失步，bl 目标多数仍有效）
_md2 = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
_md2.skipdata = True
tmp = list(_md2.disasm(bytes(img), BASE))
print(f"线性扫描指令数: {len(tmp)}")
for ins in tmp:
    if ins.mnemonic.startswith("bl"):
        try:
            t = int(ins.op_str.lstrip("#"), 16)
        except ValueError:
            continue
        if BASE <= t < END:
            starts.add(t & ~1)

print(f"候选函数数: {len(starts)}")

# 2) 逐个函数反汇编，建调用图
calls = {}       # func -> [(site, target)]
for s in sorted(starts):
    ins = dis_func(s)
    lst = []
    for i in ins:
        if i.mnemonic.startswith("bl"):
            try:
                t = int(i.op_str.lstrip("#"), 16)
            except ValueError:
                continue
            lst.append((i.address, t & ~1))
    calls[s] = lst

# 反向索引
rev = {}
for f, lst in calls.items():
    for site, t in lst:
        rev.setdefault(t, []).append((f, site))


def enclosing(addr):
    """找出真正包含 addr 的函数（起点 <= addr 且最近的）"""
    c = [s for s in calls if s <= addr]
    return max(c) if c else None


def up(seed, depth=5, label=""):
    print(f"\n=== 向上溯源: {label} 0x{seed:08X} ===")
    cur = {seed}
    seen = set()
    for d in range(depth):
        nxt = set()
        for t in sorted(cur):
            callers = rev.get(t, [])
            # 过滤掉自己调用自己
            callers = [(f, s) for (f, s) in callers if f != t]
            if not callers:
                print(f"  [{d}] 0x{t:08X}: 无静态调用者（可能通过函数指针/表调用）")
                continue
            for f, s in callers:
                print(f"  [{d}] 0x{t:08X} ← 0x{f:08X} (调用点 0x{s:08X})")
                if f not in seen:
                    seen.add(f)
                    nxt.add(f)
        cur = nxt
        if not cur:
            break
    return seen


# 3) 从震动链的几个关键点向上追
seeds = {
    0x08009750: "LRA TIM3 运行时配置",
    0x08008704: "PWM 硬件配置",
    0x08008FE8: "LRA/TIM2 初始化",
    0x08003B68: "I2C/前端初始化",
}
allup = set()
for s, nm in seeds.items():
    allup |= up(s, 4, nm)

print("\n\n=== 单独反汇编: TIM3 向量 0x0800D628 (真正的 ISR?) ===")
for i in dis_func(0x0800D628, 40):
    print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")

print("\n=== 单独反汇编: 波形回调 0x0800D6F4 ===")
for i in dis_func(0x0800D6F4, 40):
    print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")
