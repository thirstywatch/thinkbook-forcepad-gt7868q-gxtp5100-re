# -*- coding: utf-8 -*-
"""R10-2 ★★★ 经 GitHub API 取真实 gtx8 cfg bin，读 x/y/trigger_offset 真值
   api.github.com 可通（raw.githubusercontent 不通）⇒ 用 /contents 取 base64；
   内核仓库里的 *.bin.ihex 是文本 Intel HEX ⇒ 解码回二进制"""
import subprocess, json, base64, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "_r10")
os.makedirs(TMP, exist_ok=True)

TARGETS = [
    ("ihex-m16-TM", "https://api.github.com/repos/xiaomi-mediatek-devs/android_kernel_xiaomi_mt6877/contents/firmware/goodix_cfg_group_m16_TM.bin.ihex", "ihex"),
    ("ihex-m16-GVO", "https://api.github.com/repos/xiaomi-mediatek-devs/android_kernel_xiaomi_mt6877/contents/firmware/goodix_cfg_group_m16_GVO.bin.ihex", "ihex"),
    ("lfs-moto-cybert", "https://media.githubusercontent.com/media/rahulsnair/proprietary_vendor_motorola_cybert_bak/HEAD/proprietary/vendor/firmware/goodix_cfg_group.bin", "raw"),
    ("lfs-moto-dubai-csot", "https://media.githubusercontent.com/media/JoseMCC0705/vendor_motorola_dubai/HEAD/proprietary/vendor/firmware/csot_goodix_cfg_group.bin", "raw"),
    ("lfs-xiaomi-manet", "https://media.githubusercontent.com/media/yuanxing109/android_vendor_xiaomi_manet/HEAD/proprietary/odm/firmware/goodix_cfg_group_manet.bin", "raw"),
]


def curl(url, out, tries=2):
    for t in range(tries):
        r = subprocess.run(["curl", "-sS", "-L", "--max-time", "60", "-o", out, url],
                           capture_output=True)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return True
        time.sleep(1)
    return False


def ihex_decode(txt):
    """Intel HEX → 二进制（按地址填空）"""
    mem = {}
    hi = 0
    for line in txt.splitlines():
        line = line.strip()
        if not line.startswith(':'):
            continue
        try:
            b = bytes.fromhex(line[1:])
        except ValueError:
            continue
        if len(b) < 5:
            continue
        ln, addr, typ = b[0], (b[1] << 8) | b[2], b[3]
        if typ == 0x00:
            for i in range(ln):
                mem[hi + addr + i] = b[4 + i]
        elif typ == 0x02:
            hi = ((b[4] << 8) | b[5]) << 4
        elif typ == 0x04:
            hi = ((b[4] << 8) | b[5]) << 16
        elif typ == 0x01:
            break
    if not mem:
        return b''
    lo, hiA = min(mem), max(mem)
    return bytes(mem.get(i, 0) for i in range(lo, hiA + 1)), lo


def u16(b, o): return b[o] | (b[o + 1] << 8)
def u32(b, o): return int.from_bytes(b[o:o + 4], 'little')


def parse_cfgbin(tag, b):
    print(f"\n{'='*94}\n### {tag}  ({len(b)} B)  首 16B: {b[:16].hex(' ')}")
    if len(b) < 32:
        print("  太短"); return
    size = u32(b, 0)
    print(f"  head: bin_len={size}  文件长={len(b)}  {'✓' if size == len(b) else '✗ 不等'}")
    if size != len(b):
        # 可能带偏移：扫一遍找自洽的起点
        for off in range(0, min(64, len(b) - 32)):
            s2 = u32(b, off)
            if s2 == len(b) - off and b[off + 4] == (sum(b[off + 5:]) & 0xFF) and 1 <= b[off + 9] <= 16:
                print(f"  ★ 在 +0x{off:x} 找到自洽 cfg_bin 头（bin_len={s2}）")
                b = b[off:]; size = s2; break
        else:
            print("  未找到自洽头"); 
            return
    cks = b[4]; real = sum(b[5:]) & 0xFF
    pn = b[9]
    print(f"  checksum=0x{cks:02x} 实测=0x{real:02x} {'✓' if cks == real else '✗'}"
          f"  ver={b[5:9].hex(' ')}  pkg_num={pn}")
    need = 16 + 2 * pn
    ov = [u16(b, 16 + 2 * i) for i in range(pn)]
    print(f"  pkg offsets = {[hex(x) for x in ov]}")
    ok = all(need <= o < size for o in ov) and all(ov[i] < ov[i+1] for i in range(pn-1))
    print(f"  偏移表自洽: {ok}")
    if not ok:
        return
    names = ["cfg_send_flag","version_base","pid","vid","sensor_id","fw_mask","fw_status",
             "cfg_addr","esd","command","coor","gesture","fw_request","proximity"]
    for i, o in enumerate(ov):
        ic = b[o+4:o+19].split(b'\0')[0].decode('latin-1')
        ctype = b[o+19]; sid = b[o+20]
        pid = b[o+21:o+29].split(b'\0')[0].decode('latin-1')
        fwm = b[o+37:o+46].split(b'\0')[0].decode('latin-1')
        xo, yo, to = u16(b, o+50), u16(b, o+52), u16(b, o+54)
        pkg_len = u32(b, o)
        print(f"  --- pkg{i} @0x{o:x} ic_type={ic!r} cfg_type={ctype:#04x} sensor_id={sid:#x} "
              f"hw_pid={pid!r} fw_mask={fwm!r} pkg_len={pkg_len}")
        print(f"      ★ x_res_offset={xo} (0x{xo:x})   y_res_offset={yo} (0x{yo:x})   "
              f"trigger_offset={to} (0x{to:x})")
        print(f"      ★ 间距 y-x={yo-xo}  trig-y={to-yo}   "
              f"{'→ 与「三个连续 u16(步长 2)」一致' if yo-xo == 2 and to-yo == 2 else '→ 间距不是 2！'}")
        regs = [(nm, u16(b, o + 56 + 4*k)) for k, nm in enumerate(names)]
        print("      寄存器: " + " ".join(f"{nm}=0x{a:04x}" for nm, a in regs))
        cfg = b[o+121:o+pkg_len] if pkg_len > 121 else b[o+121:]
        print(f"      cfg 数据 {len(cfg)} B")
        for nm, off in (("x_res", xo), ("y_res", yo), ("trigger", to)):
            if 0 < off and off + 2 <= len(cfg):
                print(f"        ★ {nm} @cfg+0x{off:x}: u16BE={int.from_bytes(cfg[off:off+2],'big')} "
                      f"u16LE={int.from_bytes(cfg[off:off+2],'little')}   "
                      f"ctx {cfg[max(0,off-4):off+6].hex(' ')}")


for tag, url, kind in TARGETS:
    out = os.path.join(TMP, tag + ".dat")
    if not curl(url, out):
        print(f"\n### {tag}\n  下载失败（curl 无输出）: {url}")
        continue
    d = open(out, 'rb').read()
    if kind == "ihex":
        txt = d.decode('utf-8', 'replace')
        if '"content"' in txt and '"base64"' in txt:
            try:
                j = json.loads(txt)
                d = base64.b64decode(j["content"])
                txt = d.decode('utf-8', 'replace')
            except Exception as e:
                print(f"\n### {tag}\n  JSON 解析失败 {e}"); continue
        res = ihex_decode(txt)
        if isinstance(res, tuple):
            b, lo = res
            print(f"\n### {tag}  ihex 解码: {len(b)} B @ 基址 0x{lo:x}")
            parse_cfgbin(tag, b)
        else:
            print(f"\n### {tag}  ihex 解码为空")
    else:
        print(f"\n### {tag}  取到 {len(d)} B")
        head = d[:80]
        if head.startswith(b'version https://git-lfs'):
            print("  ⇒ 仍是 LFS 指针（media 端点未解析）")
        else:
            parse_cfgbin(tag, d)
