"""verify-B: 独立反汇编/交叉引用引擎（adversarial audit of H: no I2C master on TF100A）

不复用 touchpad_TF100A_thumb.asm.txt，直接从 bin 用 capstone 重新解码，
以便独立校验：线性反汇编 + 常量传播 + 字面量池 + 向量表识别。
"""
import struct, sys, json, os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import *

BASE_ADDR = 0x08005000
BASE_OFF  = 0x19ABC
BIN = r"<WORKSPACE>"

def off2addr(o): return o - BASE_OFF + BASE_ADDR
def addr2off(a): return a - BASE_ADDR + BASE_OFF

class Image:
    def __init__(self):
        self.data = open(BIN, "rb").read()
        # 明文段
        self.seg_lo = BASE_ADDR
        self.seg_hi = 0x08012C9F
        self.seg = self.data[BASE_OFF: addr2off(self.seg_hi) + 1]
        # 同时把整个文件映射进一个"全局地址空间"：0x08000000 + 文件偏移
        # 这样字面量池里可能出现的 flash 常量都能解析
        self.mem = {}
        for i, b in enumerate(self.data):
            a = 0x08000000 + i
            self.mem[a] = b

    def read32(self, addr):
        try:
            return struct.unpack("<I", bytes(self.mem[addr + k] for k in range(4)))[0]
        except KeyError:
            return None

    def read16(self, addr):
        try:
            return struct.unpack("<H", bytes(self.mem[addr + k] for k in range(2)))[0]
        except KeyError:
            return None

IMG = Image()

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.detail = True

def disasm_range(lo, hi):
    """线性反汇编 [lo,hi]"""
    out = []
    off = lo
    while off <= hi:
        chunk = bytes(IMG.mem[a] for a in range(off, min(off + 4, hi + 1)) if a in IMG.mem)
        if len(chunk) < 2:
            break
        got = False
        for ins in md.disasm(chunk, off):
            out.append(ins)
            off = ins.address + ins.size
            got = True
            break
        if not got:
            off += 2
    return out

def text():
    if not hasattr(text, "_c"):
        text._c = disasm_range(IMG.seg_lo, IMG.seg_hi)
    return text._c

# ---------- 寄存器常量传播 ----------
def const_prop(start, end):
    """返回 {addr: {reg: const}} —— 线性扫描，忽略分支合流。
    用于发现 '把常量放进寄存器' 的站点，不保证精确到路径。"""
    res = {}
    regs = {}
    for ins in text():
        if ins.address < start or ins.address > end:
            continue
        mn = ins.mnemonic
        ops = ins.op_str
        # movs/mov/movw/movt/ldr =imm
        if mn in ("mov", "movs", "movw", "movt"):
            if len(ins.operands) == 2 and ins.operands[0].type == ARM_OP_REG and \
               ins.operands[1].type == ARM_OP_IMM:
                r = ins.reg_name(ins.operands[0].reg)
                v = ins.operands[1].imm & 0xFFFFFFFF
                if mn == "movt":
                    regs[r] = ((regs.get(r, 0) & 0xFFFF) | (v << 16)) & 0xFFFFFFFF
                elif mn == "movw":
                    regs[r] = ((regs.get(r, 0) & 0xFFFF0000) | (v & 0xFFFF)) & 0xFFFFFFFF
                else:
                    regs[r] = v
                res.setdefault(ins.address, {})[r] = regs[r]
        elif mn == "ldr" and len(ins.operands) == 2 and \
             ins.operands[0].type == ARM_OP_REG and ins.operands[1].type == ARM_OP_MEM:
            m = ins.operands[1].mem
            if m.base == 0 or ins.reg_name(m.base) == "pc":
                # PC 相对
                pc = (ins.address + 4) & ~3
                # capstone 已算好 disp
                va = pc + m.disp
                v = IMG.read32(va)
                r = ins.reg_name(ins.operands[0].reg)
                if v is not None:
                    regs[r] = v
                    res.setdefault(ins.address, {})[r] = v
        elif mn in ("add", "adds", "sub", "subs") and len(ins.operands) == 3 and \
             all(o.type == ARM_OP_REG for o in ins.operands):
            d = ins.reg_name(ins.operands[0].reg)
            a = ins.reg_name(ins.operands[1].reg)
            b = ins.reg_name(ins.operands[2].reg)
            if a in regs and b in regs:
                regs[d] = (regs[a] + regs[b]) & 0xFFFFFFFF if mn.startswith("add") \
                          else (regs[a] - regs[b]) & 0xFFFFFFFF
                res.setdefault(ins.address, {})[d] = regs[d]
        elif len(ins.operands) >= 1 and ins.operands[0].type == ARM_OP_REG and \
             ins.regs_write:
            if mn == "str" or mn == "strb" or mn == "strh":
                continue
            for rr in ins.regs_write:
                nm = ins.reg_name(rr)
                if nm in regs and nm not in ("sp", "lr", "pc"):
                    pass  # 保守：不删除，仅标记可疑
    return res

def mem_refs():
    """所有 [reg + disp] 形式的访存，返回 (addr, mnemonic, reg, disp, 是否是写, 该点可解析的基址常量)"""
    out = []
    for ins in text():
        if not ins.operands:
            continue
        o0 = ins.operands[0]
        if o0.type != ARM_OP_MEM:
            continue
        m = o0.mem
        base = ins.reg_name(m.base) if m.base else None
        out.append(dict(pc=ins.address, mn=ins.mnemonic, ops=ins.op_str,
                        base=base, disp=m.disp,
                        write=(ins.mnemonic.startswith("str")),
                        idx=ins.reg_name(m.index) if m.index else None,
                        size=ins.size))
    return out

PERIPH = {
    0x40010800: "GPIOA", 0x40010C00: "GPIOB", 0x40011000: "GPIOC",
    0x40011400: "GPIOD", 0x40011800: "GPIOE",
    0x40005400: "I2C1", 0x40005800: "I2C2",
    0x40013000: "SPI1", 0x40003800: "SPI2",
    0x40013800: "USART1", 0x40004400: "USART2", 0x40004800: "USART3",
    0x40020000: "ADC1", 0x40012400: "ADC1?", 0x40012800: "ADC2?",
    0x40000000: "TIM2", 0x40000400: "TIM3", 0x40000800: "TIM4",
    0x40010000: "AFIO", 0x40021000: "RCC", 0xE000E000: "SCS",
    0x40022000: "FLASH", 0x40020000: "DMA1", 0x40020400: "DMA2",
    0x40005C00: "I2C?5C00", 0x40006000: "I2C?6000", 0x40007000: "?7000",
}
