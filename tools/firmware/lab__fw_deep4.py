# fw_deep4.py - 展开全部 tbb/tbh 跳转表; 找出索引来源; 检查是否触达震动链
import struct
from capstone import *

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
OFF = 0x19ABC
img = data[OFF:]
BASE = 0x08000000
N = len(img)
END = BASE + N

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
idx = {i.address: k for k, i in enumerate(insns)}

VIB = {0x08009750: "LRA_cfg", 0x08008FE8: "TIM2_init", 0x08008704: "PWM_cfg",
       0x0800AA20: "vib_fn", 0x0800D6F4: "wave_cb", 0x0800AD24: "fn_AD24",
       0x0800AC20: "fn_AC20", 0x0800AC0C: "fn_AC0C", 0x0800A9CC: "fn_A9CC"}

def dis(a0, n):
    out = []
    for i in insns:
        if i.address < a0: continue
        out.append(i)
        if len(out) >= n: break
    return out

def calls_of(a0, n=400):
    """收集从 a0 开始 n 条指令内的 bl 目标"""
    t = []
    for i in dis(a0, n):
        if i.mnemonic in ("bl", "blx") and i.op_str.startswith("#"):
            try: t.append(int(i.op_str[1:], 16))
            except Exception: pass
    return t

TBLS = [0x080012CC, 0x08008D9C, 0x0800B3D6, 0x0800B5C6, 0x0800B896, 0x0800B920, 0x0800B96A]
for a in TBLS:
    k = idx.get(a)
    if k is None: continue
    ins = insns[k]
    kind = "tbh" if ins.mnemonic.startswith("tbh") else "tbb"
    print("\n" + "=" * 70)
    print("### %s @0x%08X   %s %s" % (kind, a, ins.mnemonic, ins.op_str))

    # 1) 往前找边界 (cmp/sub immediate) 和索引来源
    back = insns[max(0, k-14):k]
    print("  --- setup (前 %d 条) ---" % len(back))
    for i in back:
        print("    %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))

    bound = None
    for i in reversed(back):
        if i.mnemonic.startswith("cmp") and "#" in i.op_str:
            try: bound = int(i.op_str.split("#")[1].split(",")[0], 0); break
            except Exception: pass
    n_ent = (bound + 1) if bound is not None else 32
    print("  bound=%s -> entries=%d" % (hex(bound) if bound is not None else "?", n_ent))

    # 2) 展开表
    tb = a + ins.size
    if tb % 2: tb += 1
    fo = tb - BASE
    tgts = []
    for j in range(n_ent):
        if kind == "tbb":
            if fo + j >= N: break
            e = img[fo + j]; tgt = tb + 2 * e
        else:
            if fo + 2*j + 2 > N: break
            e = struct.unpack_from("<H", img, fo + 2*j)[0]; tgt = tb + 2 * e
        tgts.append((j, e, tgt))
    for j, e, tgt in tgts:
        print("    case %2d (0x%X) -> 0x%08X" % (j, e, tgt))

    # 3) 每个 case 目标是否会调到震动链
    print("  --- case handlers ---")
    for j, e, tgt in tgts:
        cs = calls_of(tgt, 60)
        hot = [VIB[c] for c in cs if c in VIB]
        print("    case %2d @0x%08X  calls=%s%s" % (j, tgt, [hex(c) for c in cs[:6]], ("   *** VIB:" + str(hot)) if hot else ""))
