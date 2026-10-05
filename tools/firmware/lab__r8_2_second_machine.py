# -*- coding: utf-8 -*-
"""R8-2 ★★★ 第二台机器验证：「cfg 值 = LogicalMax + 1」是否普适
 来源：vendor/wiki/esp32-ptp/About-Goodix-TouchPad.md 里的 GT7863 描述符
      X LogicalMax = 0x0D7F = 3455   Y LogicalMax = 0x086F = 2159
 预测：7863 的固件/容器里应出现相邻的 u16BE 3456(0x0D80) 与 2160(0x0870)
 对照：本机（GT7868Q）已证：4150/2148 = 4149/2147 + 1，位于 cfg +0x10F/+0x111
"""
import re, os, glob

# ---- 1) 从 wiki 描述符里把 (X LogicalMax, Y LogicalMax) 解出来 ----
WIKI = r"<LAB>\touchpad-lab\vendor\wiki\esp32-ptp"
HEXRE = re.compile(r"(?:[0-9A-Fa-f]{2}\s){40,}")


def parse_desc(hx):
    b = bytes.fromhex(re.sub(r"\s+", "", hx))
    out, i, gpen = [], 0, 0
    lastlogmax = None
    while i < len(b):
        p = b[i]
        if p == 0x05 and i + 1 < len(b):          # Usage Page
            gpen = b[i + 1]; i += 2; continue
        if p == 0x26 and i + 2 < len(b):          # Logical Maximum (2B)
            lastlogmax = b[i + 1] | (b[i + 2] << 8); i += 3; continue
        if p == 0x25 and i + 1 < len(b):          # Logical Maximum (1B)
            lastlogmax = b[i + 1]; i += 2; continue
        if p == 0x09 and i + 1 < len(b):          # Usage
            u = b[i + 1]
            if u == 0x30:
                out.append(('X', gpen, lastlogmax))
            elif u == 0x31:
                out.append(('Y', gpen, lastlogmax))
            i += 2; continue
        if p == 0x46 and i + 2 < len(b):          # Physical Maximum
            i += 3; continue
        if p in (0x75, 0x95, 0x85, 0x15, 0x55, 0x65, 0x35, 0x81, 0xB1, 0x91):
            i += 2; continue
        i += 1
    # 取 "up=0x01" 的 X/Y（真坐标），排除 Usage Page 0x01 下的相对鼠标
    xs = [v for n, gp, v in out if n == 'X' and gp == 0x01 and v and v > 100]
    ys = [v for n, gp, v in out if n == 'Y' and gp == 0x01 and v and v > 100]
    return xs, ys


print("=" * 100)
print("### 1 从工区 wiki 描述符里解出的 (X,Y) LogicalMax")
print("=" * 100)
DESCS = {}
for p in sorted(glob.glob(os.path.join(WIKI, "*.md"))):
    txt = open(p, encoding="utf-8", errors="replace").read()
    for m in HEXRE.finditer(txt):
        hx = m.group()
        if len(re.sub(r"\s+", "", hx)) < 400:
            continue
        xs, ys = parse_desc(hx)
        if xs and ys:
            print(f"  {os.path.basename(p):<34} X LogicalMax={xs[:4]}  Y LogicalMax={ys[:4]}")
            DESCS[os.path.basename(p)] = (xs, ys)

print("\n" + "=" * 100)
print("### 2 ★★★ 在 7863 的样本里搜「X+1 / Y+1」")
print("=" * 100)
TARGETS = {}
for name, (xs, ys) in DESCS.items():
    if xs and ys:
        TARGETS[name] = (max(xs), max(ys))
print("  目标（描述符值 +1）：")
for k, (x, y) in TARGETS.items():
    print(f"    {k:<34} X {x} -> {x+1} (0x{x+1:04X})   Y {y} -> {y+1} (0x{y+1:04X})")

FILES = {
    '7863 明文载荷': r"<LAB>\touchpad-lab\poc\decrypt-v2\GT7863_PNOR_G1_plain_data.bin",
    '7863 容器(原)': r"<WORKSPACE>",
    '9896 明文载荷': r"<LAB>\touchpad-lab\poc\decrypt-v2\GT9896_plain_data.bin",
    '本机容器': r"<WORKSPACE>",
}
for label, p in FILES.items():
    if not os.path.exists(p):
        print(f"  [缺] {label}: {p}"); continue
    d = open(p, 'rb').read()
    print(f"\n  --- {label} ({len(d)} B) ---")
    for k, (x, y) in TARGETS.items():
        for nm, v in ((f'{k[:14]} X+1', x + 1), (f'{k[:14]} Y+1', y + 1)):
            be = [i for i in range(len(d) - 1) if d[i:i+2] == v.to_bytes(2, 'big')]
            le = [i for i in range(len(d) - 1) if d[i:i+2] == v.to_bytes(2, 'little')]
            if be or le:
                print(f"    {nm:<22} v={v:<6} u16BE@{[hex(i) for i in be[:6]]}  u16LE@{[hex(i) for i in le[:6]]}")
    # 相邻性检验：找到 X+1 与 Y+1 相距 2 的位置
    for k, (x, y) in TARGETS.items():
        xb, yb = (x + 1).to_bytes(2, 'big'), (y + 1).to_bytes(2, 'big')
        for i in range(len(d) - 4):
            if d[i:i+2] == xb and d[i+2:i+4] == yb:
                print(f"    ★★★ 相邻命中（{k}）@ 0x{i:x}: {d[i-8:i+12].hex(' ')}")

print("\n" + "=" * 100)
print("### 3 本机对照（已知命中：0x4C+0x10F=0x15B / 0x597 / 0x9D3 / 0xE0F）")
print("=" * 100)
d = open(FILES['本机容器'], 'rb').read()
for v, nm in ((4150, 'X=4149+1'), (2148, 'Y=2147+1'), (4149, 'X'), (2147, 'Y'), (2000, 'P')):
    be = [i for i in range(len(d) - 1) if d[i:i+2] == v.to_bytes(2, 'big')]
    print(f"  {nm:<12} v={v:<6} u16BE 命中 {len(be)} 处 @ {[hex(i) for i in be[:8]]}")
