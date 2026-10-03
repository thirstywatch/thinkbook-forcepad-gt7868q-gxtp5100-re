# scan_goodix_cmds.py - 在本地二进制里搜索 Goodix 命令协议特征（零风险，纯离线分析）
import os, sys

ROOTS = [
    r'C:\ProgramData\Lenovo',
    r'C:\Program Files (x86)\Lenovo',
    r'C:\Windows\System32',
    r'C:\Windows\System32\DriverStore\FileRepository',
]

# Goodix 协议特征（来自 fwupd 的 goodix-tp 插件）
PATTERNS = {
    'disable_report 0x33 0x00 0xCD': bytes([0x33, 0x00, 0xCD]),
    'confirm 0x35 0x00 0xCB':        bytes([0x35, 0x00, 0xCB]),
    'cmd switch-to-patch 00 10 ..01 01': bytes([0x00, 0x10, 0x00, 0x00, 0x01, 0x01]),
    'cmd start-update 00 11 ..01 01':    bytes([0x00, 0x11, 0x00, 0x00, 0x01, 0x01]),
    'cmd reset 0E 13 00 00 01 01':        bytes([0x0E, 0x13, 0x00, 0x00, 0x01, 0x01]),
    'cmd ptp-mode 03 03 00 00 01 01':     bytes([0x03, 0x03, 0x00, 0x00, 0x01, 0x01]),
    'cmd load-flash 0E 12':               bytes([0x0E, 0x12, 0x00, 0x00, 0x06]),
    'addr 0x60CC (BE)':  bytes([0x60, 0xCC]),
    'addr 0x5095 (BE)':  bytes([0x50, 0x95]),
    'addr 0x5096 (BE)':  bytes([0x50, 0x96]),
    'addr 0x452C (BE)':  bytes([0x45, 0x2C]),
    'addr 0x60DC (BE)':  bytes([0x60, 0xDC]),
    'brlb addr 0x0001001E': bytes([0x00, 0x01, 0x00, 0x1E]),
    'brlb addr 0x00010076': bytes([0x00, 0x01, 0x00, 0x76]),
    'i2c_direct_rw 0x20 + 0x0E': bytes([0x0E, 0x20]),
}

EXT = {'.dll', '.exe', '.sys', '.ocx', '.cpl', '.node'}
MAXSIZE = 40 * 1024 * 1024

files = []
for root in ROOTS:
    if not os.path.isdir(root):
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath.count(os.sep) - root.count(os.sep) > 5:
            dirnames[:] = []
            continue
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in EXT:
                fp = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(fp) <= MAXSIZE:
                        files.append(fp)
                except OSError:
                    pass

print('扫描 %d 个二进制文件...' % len(files))
hits = {}
for fp in files:
    try:
        with open(fp, 'rb') as f:
            data = f.read()
    except OSError:
        continue
    for name, pat in PATTERNS.items():
        idx = data.find(pat)
        if idx >= 0:
            hits.setdefault(name, []).append((fp, idx))

print('\n=== 命中结果 ===')
if not hits:
    print('（无任何命中）')
for name in PATTERNS:
    lst = hits.get(name, [])
    print('\n[%s] 命中 %d 个文件' % (name, len(lst)))
    for fp, off in lst[:6]:
        print('    %s  @0x%X' % (fp, off))
