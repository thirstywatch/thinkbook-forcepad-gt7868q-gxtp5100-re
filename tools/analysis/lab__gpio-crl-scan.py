#!/usr/bin/env python3
"""gpio-crl-scan.py —— 搜「直接写 GPIO CRL/CRH 寄存器」的代码

目的：验证 TF100A 是否通过【运行时改写引脚模式寄存器】来门控马达 PWM。
  背景：TIM2 (0x40000000) 被配成 200 Hz PWM（CCR1=0x2BC、CC1E 置位），
        但 STM32F1 的 TIM2_CH1 默认在 PA0，而 GPIO_Init 把 PA0–PA3 配成了
        4 路 ADC 模拟输入 ⇒ PWM 输出不到引脚 ⇒ 马达不震。
        若"震动"= 把 PA0 切回复用输出，则该切换必然写 GPIOA_CRL (0x40010800+0x00)。
  本脚本就找这种写。
"""
import re, sys

asm_path = r"<WORKSPACE>"
lines = open(asm_path, encoding='utf-8', errors='ignore').read().splitlines()

def parse(l):
    m = re.match(r'^\s*([0-9a-f]{8})\s+(\S+)\s*(.*)$', l)
    if not m:
        return None
    return {'addr': int(m.group(1), 16), 'mnem': m.group(2), 'ops': m.group(3).strip()}

# ── 1) 找所有 GPIOx 基址构造（movw #lo + movt #0x4001）────────────────
bases = {
    0x40010800: 'GPIOA', 0x40010c00: 'GPIOB', 0x40011000: 'GPIOC',
    0x40011400: 'GPIOD', 0x40011800: 'GPIOE',
}
# 记录：寄存器 -> 最近一次被赋予的 GPIO 基址（附带行号）
constructions = []          # (line_idx, reg, base_addr)
pending = {}
for i, l in enumerate(lines):
    p = parse(l)
    if not p:
        continue
    m = re.match(r'^(r\d+),\s*#(0x[0-9a-f]+)$', p['ops'])
    if not m:
        continue
    reg, val = m.group(1), int(m.group(2), 16)
    if p['mnem'] == 'movw':
        pending[reg] = {'lo': val, 'line': i}
    elif p['mnem'] == 'movt' and reg in pending and val == 0x4001:
        base = (val << 16) | pending[reg]['lo']
        if base in bases:
            constructions.append((i, reg, base))
        pending.pop(reg, None)

print(f"GPIO 基址构造点：{len(constructions)} 处")
from collections import Counter
print("  按端口:", Counter(bases[b] for _, _, b in constructions))

# ── 2) 对每处构造，往下 16 行找对 [reg] / [reg,#0] / [reg,#4] 的读或写 ──
print("\n=== 直接访问 GPIO 基址+0x00(CRL) / +0x04(CRH) / +0x08 / +0x0C 的地方 ===")
found = 0
for (i, reg, base) in constructions:
    port = bases[base]
    for k in range(i + 1, min(i + 16, len(lines))):
        p = parse(lines[k])
        if not p:
            continue
        # 该寄存器是否被改用作别的用途？简单起见只看文本
        ops = p['ops']
        for off, name in [(0, 'CRL'), (4, 'CRH'), (8, '???'), (0xc, '???')]:
            pat = rf'\[{reg}(?:,\s*#0x{off:x})?\]'
            if re.search(pat, ops) and p['mnem'] in ('str', 'strh', 'strb', 'ldr', 'ldrh', 'ldrb'):
                acc = '读' if p['mnem'].startswith('ldr') else '★写'
                print(f"  {acc} {port}+0x{off:02X}({name})  L{k+1}: {lines[k].strip()}    (基址建于 L{i+1})")
                found += 1
print(f"  共 {found} 处")

# ── 3) 另一路径：搜所有 str/strh 到「无偏移的 [rX]」且 rX 在附近被赋 GPIOA 值 ──
print("\n=== 反向检查：0x08005C20~0x08005CE0 区（ADC 引脚配置前后）有无 CRL 写 ===")
for k in range(1200, 1290):
    if k < len(lines):
        t = lines[k].strip()
        if re.search(r'\bstr\b|\bstrh\b', t):
            print(f"  L{k+1}: {t}")

# ── 4) 检查 GPIO_Init 内部是否写 CRL/CRH（0x0800F81C 起 60 行）──
print("\n=== GPIO_Init (0x0800F81C) 内部对基址的写入 ===")
start = None
for i, l in enumerate(lines):
    if l.strip().startswith('0800F81C'):
        start = i
        break
if start:
    for k in range(start, start + 70):
        t = lines[k].strip()
        if re.search(r'\bstr\b|\bstrh\b|\bldr\b', t):
            print(f"  L{k+1}: {t}")
