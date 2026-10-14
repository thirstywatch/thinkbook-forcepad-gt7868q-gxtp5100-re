# -*- coding: utf-8 -*-
"""R10-1 ★★★ 下载真实的 goodix_cfg_group.bin 并读取 x/y/trigger_offset 真值
—— 目的：判定官方三个 offset 的【间距】到底是 +2 还是 +4，从而检验我们对
   本机 cfg +0x10F/+0x111/+0x113 的解释"""
import os, urllib.request, ssl, traceback

OUT = os.path.dirname(os.path.abspath(__file__))
URLS = [
    "https://raw.githubusercontent.com/rahulsnair/proprietary_vendor_motorola_cybert_bak/HEAD/proprietary/vendor/firmware/goodix_cfg_group.bin",
    "https://raw.githubusercontent.com/JoseMCC0705/vendor_motorola_dubai/HEAD/proprietary/vendor/firmware/csot_goodix_cfg_group.bin",
    "https://raw.githubusercontent.com/JoseMCC0705/vendor_motorola_dubai/HEAD/proprietary/vendor/firmware/tianma_goodix_cfg_group.bin",
    "https://raw.githubusercontent.com/snapboss/vendor_xiaomi_duchamp/HEAD/proprietary/vendor/firmware/goodix_cfg_group_duchamp.bin",
    "https://raw.githubusercontent.com/yuanxing109/android_vendor_xiaomi_manet/HEAD/proprietary/odm/firmware/goodix_cfg_group_manet.bin",
    "https://raw.githubusercontent.com/MrZ3T4/proprietary_vendor_xiaomi_rodin/HEAD/proprietary/odm/firmware/goodix_cfg_group_rodin.bin",
]
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def u16(b, o): return b[o] | (b[o + 1] << 8)
def u32(b, o): return int.from_bytes(b[o:o + 4], 'little')

def parse(name, b):
    print(f"\n{'='*92}\n### {name}   ({len(b)} B)")
    size = u32(b, 0)
    if size != len(b):
        print(f"  head.bin_len={size} != 文件长 {len(b)}  ⇒ 不是官方 cfg_bin")
        return
    cks = b[4]
    real = sum(b[5:]) & 0xFF
    pn = b[9]
    print(f"  bin_len={size} ✓  checksum=0x{cks:02x} 实测=0x{real:02x} {'✓' if cks==real else '✗'}"
          f"  ver={b[5:9].hex(' ')}  pkg_num={pn}")
    need = 16 + 2 * pn
    ov = [u16(b, 16 + 2 * i) for i in range(pn)]
    print(f"  pkg offsets = {[hex(x) for x in ov]}")
    if any(o >= size or o < need for o in ov) or any(ov[i] >= ov[i+1] for i in range(pn-1)):
        print("  ⇒ 偏移表不自洽，判为非 cfg_bin（或结构不同）")
        return
    for i, o in enumerate(ov):
        ic = b[o+4:o+19].split(b'\0')[0]
        ctype = b[o+19]; sid = b[o+20]
        pid = b[o+21:o+29].split(b'\0')[0]; vid = b[o+29:o+37].split(b'\0')[0]
        fwm = b[o+37:o+46].split(b'\0')[0]; fwp = b[o+46:o+50].split(b'\0')[0]
        xo = u16(b, o+50); yo = u16(b, o+52); to = u16(b, o+54)
        pkg_len = u32(b, o)
        print(f"  --- pkg {i} @0x{o:x} ic_type={ic!r} cfg_type={ctype:#04x} sensor_id={sid:#x}")
        print(f"      hw_pid={pid!r} hw_vid={vid!r} fw_mask={fwm!r} fw_patch={fwp!r} pkg_len={pkg_len}")
        print(f"      ★ x_res_offset={xo} (0x{xo:x})   y_res_offset={yo} (0x{yo:x})   "
              f"trigger_offset={to} (0x{to:x})")
        print(f"      ★ 间距: y-x = {yo-xo}   trig-y = {to-yo}")
        ro = o + 56
        names = ["cfg_send_flag","version_base","pid","vid","sensor_id","fw_mask","fw_status",
                 "cfg_addr","esd","command","coor","gesture","fw_request","proximity"]
        regs = [(nm, u16(b, ro + 4*k)) for k, nm in enumerate(names)]
        print("      寄存器映射: " + "  ".join(f"{nm}=0x{a:04x}" for nm, a in regs))
        cfg = b[o+121:o+pkg_len] if pkg_len > 121 else b[o+121:]
        print(f"      cfg 数据长度 {len(cfg)}")
        # 若 offsets 落在 cfg 内，把那里的值读出来！
        for nm, off in (("x_res", xo), ("y_res", yo), ("trigger", to)):
            if off and off + 2 <= len(cfg):
                vbe = int.from_bytes(cfg[off:off+2], 'big')
                vle = int.from_bytes(cfg[off:off+2], 'little')
                print(f"        ★ {nm}@cfg+0x{off:x}: u16BE={vbe}  u16LE={vle}   "
                      f"上下文 {cfg[max(0,off-4):off+6].hex(' ')}")

for url in URLS:
    name = url.rsplit('/', 1)[-1] + "  [" + url.split('/')[3] + "]"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        b = urllib.request.urlopen(req, timeout=45, context=ctx).read()
        parse(name, b)
    except Exception as e:
        print(f"\n### {name}\n  下载失败: {type(e).__name__}: {e}")
