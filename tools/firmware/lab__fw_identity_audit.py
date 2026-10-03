# fw_identity_audit.py — 假设审计：容器里两个段，各自到底是哪颗芯片的固件？
#   要审的三个"文档级假设"：
#     A1 高熵段 = GT7868Q（汇顶，AES 加密）；明文段 = TF100A（钛方）
#     A2 明文段自报的 "TF100A_Test_FW" 指的是那颗芯片
#     A3 明文段就是【在跑】的固件（文档自己都标了 Test_FW + 被截断）
#   纯本地，不碰设备。
import io

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
full = open(BIN, 'rb').read()
OFF = 0x19ABC
enc, plain = full[:OFF], full[OFF:]
print("容器 %d B  |  高熵段 0x000000-0x%06X (%d B)  |  明文段 0x%06X-0x%06X (%d B)"
      % (len(full), OFF, len(enc), OFF, len(full), len(plain)))
print()

# 搜索目标：两颗芯片的丝印 + 厂商 + 方案名 + 项目名
TARGETS = [
    # 右侧芯片丝印（实测照片）
    b"TF100A", b"TF100", b"TB0V200", b"0001-2311",
    # 左侧芯片丝印（文档称 QR 解出）
    b"8SST61M69932", b"SLE0141701", b"SLB141701",
    # 触摸控制器
    b"GT7868", b"7868Q", b"GXTP5100", b"GXTP",
    # 厂商
    b"Goodix", b"GOODIX", b"Taifang", b"TAIFANG", b"taifang",
    # 方案/机型/代号
    b"YELSTO", b"MARSEI", b"BERLIN", b"PNOR", b"TB14P", b"FORCEPAD", b"ForcePad", b"Forcepad",
    # 技术线索
    b"USART", b"STM32", b"LRA", b"Hapt", b"hapt",
    # 版本/时间
    b"5.21.01", b"Nov 28 2023", b"Test_FW", b"_FW",
    # 中文（UTF-8）
    "\u94a5\u65b9".encode("utf-8"),          # 钛方
    "\u6c47\u9876".encode("utf-8"),          # 汇顶
]

def hits(buf, s):
    out, i = [], buf.find(s)
    while i >= 0 and len(out) < 8:
        out.append(i)
        i = buf.find(s, i + 1)
    return out

print("=" * 92)
print("%-22s | %-38s | %s" % ("字符串", "高熵段(疑 GT7868Q)", "明文段(疑 TF100A)"))
print("=" * 92)
for t in TARGETS:
    he = hits(enc, t)
    hp = hits(plain, t)
    def fmt(h, base=0):
        if not h:
            return "—"
        return "%d 处 @ %s" % (len(h), ",".join("0x%X" % x for x in h[:3]))
    print("%-22s | %-38s | %s" % (repr(t)[:22], fmt(he), fmt(hp)))

print()
print("=" * 92)
print("明文段里所有可打印字符串中，含关键字（长字符串表，前 60 条）")
print("=" * 92)
import re
ss = sorted(set(s.decode("ascii", "ignore") for s in re.findall(rb"[\x20-\x7e]{5,}", plain)))
kw = ("TF", "TB", "GT", "GX", "goodix", "Goodix", "USART", "haptic", "Haptic", "LRA",
      "Test", "FW", "5.21", "20 23", "2023", "Nov", "Mar", "Err", "err", "PASS", "FAIL")
shown = 0
for s in ss:
    if len(s) > 60:
        continue
    if any(k in s for k in kw):
        print("   ", repr(s))
        shown += 1
        if shown >= 60:
            break
print("   （共匹配 %d 条，已截断）" % shown)
