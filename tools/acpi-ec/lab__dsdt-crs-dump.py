#!/usr/bin/env python3
# dsdt-crs-dump.py —— 干净 dump ADR0/IICB 的 CreateDWordField 模板区，定位地址来源
import sys
DSDT = r"<WORKSPACE>"
b = open(DSDT, "rb").read()

OPS = {
    0x08: "NameOp", 0x0A: "BytePrefix", 0x0B: "WordPrefix", 0x0C: "DWordPrefix",
    0x0D: "StringPrefix", 0x00: "ZeroOp", 0x01: "OneOp", 0xFF: "OnesOp",
    0x11: "BufferOp", 0x12: "PackageOp", 0x13: "VarPackageOp", 0x14: "MethodOp",
    0x15: "ExternalOp", 0x5B: "ExtOpPrefix", 0x70: "StoreOp", 0x74: "IncrementOp",
    0x75: "DecrementOp", 0x76: "DivideOp", 0x77: "MultiplyOp", 0x78: "ShiftLeftOp",
    0x79: "ShiftRightOp", 0x7A: "AndOp", 0x7B: "NandOp", 0x7C: "OrOp", 0x7D: "NorOp",
    0x7E: "XorOp", 0x82: "NotOp", 0x83: "FindSetLeftBitOp", 0x84: "FindSetRightBitOp",
    0x85: "DerefOfOp", 0x86: "ConcatOp", 0x87: "AddOp", 0x88: "SubtractOp",
    0x89: "IncrementOp2", 0x8A: "CreateDWordFieldOp", 0x8B: "CreateWordFieldOp",
    0x8C: "CreateByteFieldOp", 0x8D: "CreateBitFieldOp", 0x8E: "ObjectTypeOp",
    0x90: "LAndOp", 0x91: "LOrOp", 0x92: "LNotOp", 0x93: "LEqualOp", 0x94: "LGreaterOp",
    0x95: "LLessOp", 0x96: "ToBufferOp", 0x97: "ToDecimalStringOp", 0x98: "ToHexStringOp",
    0x99: "ToIntegerOp", 0x9C: "ToStringOp", 0x9D: "CopyObjectOp", 0x9E: "MidOp",
    0xA0: "IfOp", 0xA1: "ElseOp", 0xA2: "WhileOp", 0xA3: "NoopOp", 0xA4: "ReturnOp",
    0xA5: "BreakOp", 0xCC: "BreakPointOp", 0x5B82: "DeviceOp", 0x5B80: "OperationRegionOp",
    0x5B81: "FieldOp", 0x5B84: "PowerResOp", 0x5B85: "ProcessorOp", 0x5B88: "MethodOp2",
    0x5B89: "IndexFieldOp", 0x5B8A: "BankFieldOp", 0x5B8C: "DataRegionOp",
}

def namesegs(buf, i):
    """从 i 开始读 NameString，返回 (字符串, 新位置)"""
    out = []
    while i < len(buf):
        ch = buf[i]
        if ch == 0x00:
            return ("".join(out), i + 1)
        if ch == 0x2E:      # DualNamePrefix
            i += 1
            continue
        if ch == 0x2F:      # MultiNamePrefix
            n = buf[i+1]
            i += 2
            for _ in range(n):
                out.append(buf[i:i+4].decode('latin1'))
                i += 4
            return (".".join(out), i)
        if ch == 0x5C:      # RootChar
            out.append("\\")
            i += 1
            continue
        if ch == 0x5E:      # ParentPrefix
            out.append("^")
            i += 1
            continue
        if 0x41 <= ch <= 0x5A or ch == 0x5F:
            out.append(buf[i:i+4].decode('latin1'))
            i += 4
            continue
        return ("".join(out), i)
    return ("".join(out), i)

for center in (0x11739, 0x27CDB, 0x281C7, 0x286B3, 0x28B9F, 0x706B8):
    lo = max(0, center - 0x80)
    hi = min(len(b), center + 0x60)
    print("=" * 78)
    print(f"区域中心 0x{center:X}   （ADR0 出现处）")
    print("=" * 78)
    i = lo
    while i < hi:
        op = b[i]
        s = f"  0x{i:06X}: {op:02X}"
        desc = OPS.get(op)
        if op in (0x8A, 0x8B, 0x8C, 0x8D):
            # CreateXField(SourceBuf, Index, NameString)
            j = i + 1
            src, j = namesegs(b, j)
            idx = b[j]; j += 1
            idxv = b[j] if idx == 0x0A else None
            if idx == 0x0A: j += 1
            elif idx == 0x0B: j += 2
            elif idx == 0x0C: j += 4
            nm, j2 = namesegs(b, j)
            s += f"  ★ {desc}  source={src}  offset={idxv if idxv is not None else hex(idx)}  field={nm}"
            print(s)
            i = j2
            continue
        if op == 0x08:
            nm, j = namesegs(b, i + 1)
            # 看数据
            d = b[j]
            extra = ""
            if d == 0x0A: extra = f"= {b[j+1]}"
            elif d == 0x0B: extra = f"= 0x{b[j+1]|(b[j+2]<<8):X}"
            elif d == 0x0C: extra = f"= 0x{b[j+1]|(b[j+2]<<8)|(b[j+3]<<16)|(b[j+4]<<24):X}"
            elif d == 0x0D:
                e = b.find(b"\x00", j + 1)
                extra = '= "' + b[j+1:e].decode('latin1') + '"'
            elif d == 0x11: extra = "= Buffer(...)"
            elif d == 0x12: extra = "= Package(...)"
            elif d == 0x00: extra = "= Zero"
            elif d == 0x01: extra = "= One"
            print(s + f"  {desc} {nm} {extra}")
            i = j
            continue
        if op in (0x70, 0x7C, 0x78, 0x79):
            print(s + f"  {desc}")
            i += 1
            continue
        if op == 0xA0:
            print(s + "  IfOp")
            i += 1
            continue
        if op in (0x93, 0x94, 0x95, 0x90, 0x91):
            print(s + f"  {desc}")
            i += 1
            continue
        if desc:
            print(s + f"  {desc}")
        i += 1
    print()
