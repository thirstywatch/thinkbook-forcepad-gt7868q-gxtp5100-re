"""DSDT 触控板（TPAD / GXTP）子树解析器。

不依赖任何硬编码偏移：从 DSDT 里自动定位 TPAD 设备节点，解析：
  - TPID 厂商表（5 条目：HID / 从机地址 / 描述符寄存器）
  - SBFI / SBFG / SBFB 资源描述符（I2cSerialBus / GpioInt）
  - _HID / _CID / _STA / _CRS / _DSM 方法体

用法:
  python dsdt_tpad.py [DSDT文件]
  默认: ../../acpi-dump/DSDT_LENOVO_CB-01____00000001.bin（相对本脚本）
"""
import os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "..", "acpi-dump", "DSDT_LENOVO_CB-01____00000001.bin")
PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
D = open(PATH, "rb").read()
print("DSDT: %s  (%d 字节)\n" % (os.path.basename(PATH), len(D)))

# ---------------------------------------------------------------- AML 小工具

def pkg_len(b, i):
    """读 AML PkgLength（i 指向首字节）。返回 (总占用字节数, 包内长度 PkgLength)。
    ★ 编码（ACPI 规范 20.2.4）：
        lead 高 2 位 n = 后续字节数；低 4 位是"最高 nibble"，
        之后 n 个字节依次是**更高**的字节（小端追加）。
        PkgLength 值 = (lead & 0x0F) | (b[i+1]<<4) | (b[i+2]<<12) | (b[i+3]<<20)
        PkgLength 含自身占用字节数。"""
    lead = b[i]
    n = lead >> 6
    if n == 0:
        return 1, lead & 0x3F
    v = lead & 0x0F
    for k in range(n):
        v |= b[i + 1 + k] << (4 + 8 * k)
    return 1 + n, v


def aml_str(b, i):
    """读 AML String（0x0D 前缀 + NUL 结尾）。返回 (字符串, 新偏移) 或 (None, i)。"""
    if i >= len(b) or b[i] != 0x0D:
        return None, i
    j = b.find(b"\x00", i + 1)
    if j < 0:
        return None, i
    return b[i + 1:j].decode("latin-1"), j + 1


def parse_sub_pkg(b, i):
    """解析一个 Package(0x12) / Buffer(0x11) 等，返回 (内容起, 内容止, 新偏移)。
    i 指向操作符字节。★ PkgLength 从操作符之后起算 ⇒
      内容止 = i + 1 + plen（plen 已含 PkgLength 自身占用的 n 字节）。"""
    op = b[i]
    n, plen = pkg_len(b, i + 1)
    start = i + 1 + n
    end = i + 1 + plen
    return start, end, end


def scan_ints_strs(sub):
    """从一段 AML 里顺序抽出整数（0x0A/0x0B/0x0C/0x00/0x01）与字符串（0x0D）。"""
    ints, strs, q = [], [], 0
    while q < len(sub):
        c = sub[q]
        if c == 0x0A:
            ints.append(sub[q + 1]); q += 2
        elif c == 0x0B:
            ints.append(struct.unpack_from("<H", sub, q + 1)[0]); q += 3
        elif c == 0x0C:
            ints.append(struct.unpack_from("<I", sub, q + 1)[0]); q += 5
        elif c == 0x00:
            ints.append(0); q += 1
        elif c == 0x01:
            ints.append(1); q += 1
        elif c == 0x0D:
            v, q = aml_str(sub, q)
            if v is None:
                break
            strs.append(v)
        else:
            q += 1
    return ints, strs


def dump_hex(b, base=0, width=16):
    for off in range(0, len(b), width):
        x = b[off:off + width]
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in x)
        print("  %06X  %-*s |%s|" % (base + off, width * 3 - 1,
                                     " ".join("%02X" % c for c in x), txt))


# ------------------------------------------------------- 1. 定位 TPAD 节点

# TPAD 出现在 _SB.PC00.I2C0 下（本机）。取最后一次出现作为设备名位置，
# 其前的 0x5B 0x82 (DeviceOp + PkgLength) 就是设备起始。
tpad_pos = [m.start() for m in re.finditer(b"TPAD", D)]
print("=== 1. TPAD 出现位置 ===")
for p in tpad_pos:
    # 往前找最近的 5B 82（Device 操作符）
    dev = D.rfind(b"\x5b\x82", max(0, p - 0x40), p)
    print("  0x%06X   (设备起始 0x%06X)" % (p, dev if dev >= 0 else -1))

if not tpad_pos:
    sys.exit("未找到 TPAD")
DEV = D.rfind(b"\x5b\x82", max(0, tpad_pos[-1] - 0x40), tpad_pos[-1])
if DEV < 0:
    sys.exit("未定位到 TPAD 的 Device 头")
# ★ PkgLength 从 DeviceOp(2 字节) 之后起算 ⇒ 设备体止 = DEV + 2 + plen
n, plen = pkg_len(D, DEV + 2)
# ★ PkgLength 占用总字节数 = 1 + n（首字节 + 后续 n 个）
DEV_END = DEV + 2 + plen
BODY = D[DEV:DEV_END]
print("\n=== 2. TPAD 设备体 ===")
print("  Device 起始 = 0x%06X, PkgLength = 0x%X（占 %d 字节）, 结束 = 0x%06X, 体大小 = %d 字节"
      % (DEV, plen, 1 + n, DEV_END, len(BODY)))
# 设备名：DeviceOp(1) + PkgLength(1+n) 后紧跟 4 字符 NameSeg
nsoff = DEV + 1 + 1 + n
name = D[nsoff:nsoff + 4]
print("  设备名 = %r （@0x%06X）" % (name.decode("latin-1"), nsoff))
print("  结束处后继字节 = %s（应为兄弟节点的 Op 码）"
      % " ".join("%02X" % c for c in D[DEV_END:DEV_END + 6]))

# --------------------------------------------------------- 3. TPID 厂商表

print("\n=== 3. ★ TPID 厂商表（5 条目）===")
tp = BODY.find(b"TPID")
if tp >= 0:
    i = tp + 4
    if BODY[i] != 0x12:
        print("  TPID 后不是 Package(0x12)：0x%02X" % BODY[i])
    else:
        s0, e0, _ = parse_sub_pkg(BODY, i)
        count = BODY[s0]
        print("  TPID 包 @+0x%X  条目数=%d" % (tp, count))
        j = s0 + 1
        for k in range(count):
            if BODY[j] != 0x12:
                print("    #%d 不是子包（0x%02X），停止" % (k + 1, BODY[j]))
                break
            ss, ee, j = parse_sub_pkg(BODY, j)
            ints, strs = scan_ints_strs(BODY[ss:ee])
            print("    #%-2d 索引=%-3s 从机地址=%-6s 描述符寄存器=%-6s HID=%-10s CID=%s" % (
                k + 1,
                ints[0] if len(ints) > 0 else "?",
                ("0x%02X" % ints[1]) if len(ints) > 1 else "?",
                ("0x%02X" % ints[2]) if len(ints) > 2 else "?",
                strs[0] if strs else "?",
                strs[1] if len(strs) > 1 else "-",
            ))
        print("  ⚠ 第 5 条 `XXXX0001`（从机地址 0xFF）是占位 ⇒ 实际 4 家厂商共用同一节点")
else:
    print("  未找到 TPID")

# --------------------------------------------------- 4. 资源描述符（SBF*）

print("\n=== 4. 资源描述符 ===")
for nm in (b"SBFI", b"SBFG", b"SBFB"):
    i = BODY.find(nm)
    if i < 0:
        print("\n--- %s: 未找到 ---" % nm.decode())
        continue
    j = i + 4
    if BODY[j] != 0x11:
        print("\n--- %s: 后跟 0x%02X（非 Buffer）---" % (nm.decode(), BODY[j]))
        continue
    nn, plen = pkg_len(BODY, j + 1)
    k = j + 1 + nn                    # 指向 Buffer 的"大小"字段
    # ★ Buffer 大小字段本身可能是 `0A <byte>`（BytePrefix + 值）或单字节。
    if BODY[k] == 0x0A:
        bsize = BODY[k + 1]
        k += 2
    elif BODY[k] == 0x0B:
        bsize = struct.unpack_from("<H", BODY, k + 1)[0]
        k += 3
    else:
        bsize = BODY[k]
        k += 1
    data = BODY[k:k + bsize]
    print("\n--- %s @+0x%X  PkgLen=0x%X  缓冲声明=%d 字节, 实取=%d ---"
          % (nm.decode(), i, plen, bsize, len(data)))
    print("    原始: " + " ".join("%02X" % c for c in data))

    # ★ 缓冲内可能有填充字节，资源描述符不总在偏移 0。先在缓冲里找已知描述符首字节。
    DESC = {0x89: "I2cSerialBus", 0x8C: "GpioInt", 0x8E: "GpioIo",
            0x8A: "SpiSerialBus", 0x8B: "UartSerialBus"}
    d0 = None
    for off in range(len(data)):
        if data[off] in DESC and off + 1 < len(data) and data[off] in (0x89, 0x8C, 0x8E, 0x8A, 0x8B):
            # 进一步确认：第 2 字节（TotalLen）应合理
            if 5 < data[off + 1] <= len(data) - off:
                d0 = off
                break
    if d0 is None:
        print("    （未识别出资源描述符）")
        continue
    d = data[d0:]
    kind = DESC[d[0]]
    print("    ★ 描述符起于缓冲 +0x%X，类型 = %s" % (d0, kind))

    if d[0] == 0x89:      # I2cSerialBus —— ★ 按下方的固定规范偏移读，不用猜
        # ACPI 5.0 大资源（本机实测）：
        #   [0]=89  [1..2]=Length(W LE)  [3]=RevID  [4]=ResSrcIdx  [5]=SerialBusType
        #   [6]=GenFlags  [7]=TypeFlags  [8..11]=ConnectionSpeed
        #   [12..13]=SlaveAddress  [14..]=ResourceSource(可空)
        length = struct.unpack_from("<H", d, 1)[0]
        print("      Length=%d (描述符总长，含头 3 字节)" % length)
        print("      RevID=%d ResSrcIdx=%d SerialBusType=%d GenFlags=0x%02X TypeFlags=0x%02X"
              % (d[3], d[4], d[5], d[6], d[7]))
        if length >= 14 and len(d) >= 14:
            print("      ★ 连接速率 = %d Hz" % struct.unpack_from("<I", d, 8)[0])
            print("      ★ 从机地址 = 0x%02X" % struct.unpack_from("<H", d, 12)[0])
        else:
            print("      ⚠ 本描述符为**最小形式**（Length=%d < 14）：不含速率与从机地址。" % length)
            print("        ⇒ 速率/地址由 `_CRS` 里的 `IICBADR0` / `IICSDA0` 动态给出" )
            print("        ⇒ 静态值为：从机地址 **0x2C**（TPID 表第 1/3/4 条一致）、总线 `\\_SB.PC00.I2C0`")
    elif d[0] == 0x8C:    # GpioInt
        # 8C <Len2> <RevID> <ResSrcIdx> <IntFlags2> <PinConfig?> <PinTable(N words)> <ResSrcStr NUL>
        length = struct.unpack_from("<H", d, 1)[0]
        fl = struct.unpack_from("<H", d, 5)[0]
        print("      Length=%d RevID=%d ResSrcIdx=%d IntFlags=0x%04X"
              % (length, d[3], d[4], fl))
        pol = fl & 1
        mode = (fl >> 1) & 1
        share = (fl >> 2) & 3
        wake = (fl >> 4) & 1
        print("      ★ 极性=%s  触发方式=%s  共享=%d  可唤醒=%s"
              % ("ActiveLow" if pol else "ActiveHigh",
                 "Edge" if mode else "Level", share, "Yes" if wake else "No"))
        # PinTable：紧跟 IntFlags 之后，长度 = Length - 3(头) - 2(RevSrc) - 2(flags) - 1(pinconfig) - 1(NUL)
        pt = d[8:]
        nz = pt.find(b"\\")
        if nz < 0:
            nz = len(pt)
        # PinTable 是 Word 数组（小端），去掉尾部 NUL
        raw = pt[:nz]
        pins = [struct.unpack_from("<H", raw, x)[0]
                for x in range(0, len(raw) - 1, 2)]
        print("      原始 PinTable 区 = %s" % " ".join("%02X" % c for c in raw))
        print("      ★ 引脚号 = %s" % pins)
        z = d.find(b"\\")
        print("      ★ 源设备 = %r" % (d[z:].rstrip(b"\x00").decode("latin-1") if z >= 0 else ""))
    elif d[0] == 0x8E:    # GpioIo
        length = struct.unpack_from("<H", d, 1)[0]
        print("      Length=%d RevID=%d ResSrcIdx=%d" % (length, d[3], d[4]))
        z = d.find(b"\\")
        print("      ★ 源设备 = %r" % (d[z:].rstrip(b"\x00").decode("latin-1") if z >= 0 else ""))

# --------------------------------------------------------------- 5. 方法

print("\n=== 5. 方法 ===")
for mname in (b"_HID", b"_CID", b"_STA", b"_CRS", b"_DSM", b"TPDS", b"_ADR", b"_UID", b"_S0W"):
    m = re.search(re.escape(mname) + bytes([0x14]), BODY)   # MethodOp 0x14
    if not m:
        m = re.search(re.escape(mname), BODY)
        if m:
            print("  %-6s @+0x%05X（有名字，但不是 MethodOp 紧随）"
                  % (mname.decode(), m.start()))
        else:
            print("  %-6s 未找到" % mname.decode())
        continue
    print("  %-6s @+0x%05X  ★ Method" % (mname.decode(), m.start()))

# _DSM 的 UUID 值得单独列出
print("\n=== 6. _DSM 的 UUID（决定厂商接口）===")
ii = BODY.find(b"_DSM")
if ii >= 0:
    seg = BODY[ii:ii + 0x200]
    # UUID 是 16 字节 Buffer，常以 0x11 0x13 0x0A 0x10 + 16 字节形式出现
    for mm in re.finditer(bytes([0x11, 0x13, 0x0A, 0x10]), seg):
        u = seg[mm.start() + 4:mm.start() + 20]
        if len(u) == 16:
            s = "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%s" % (
                u[3], u[2], u[1], u[0], u[5], u[4], u[7], u[6],
                u[8], u[9], "".join("%02x" % c for c in u[10:16]))
            print("   %s   （原始字节 %s）" % (s, " ".join("%02X" % c for c in u)))

print("\n=== 7. 原始字节（便于人工核对）===")
dump_hex(BODY[:0x400], base=DEV)
