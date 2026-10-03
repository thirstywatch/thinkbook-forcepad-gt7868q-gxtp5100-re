# analyze_hellcat.py - 分析 Dell/Goodix Hellcat 工具（Windows 侧协议）
import re, os, struct, hashlib

P = r'<LAB>\touchpad-lab\vendor\dup\DellTouchpadUpdate_Hellcat_v0.2.2.100.exe'
data = open(P, 'rb').read()
print('大小: %d 字节' % len(data))
print('SHA256:', hashlib.sha256(data).hexdigest())
print('头: ' + ' '.join('%02X' % b for b in data[:32]))

# .NET?
print('CLI 元数据 (BSJB): %s' % ('是 (.NET)' if b'BSJB' in data else '否 (原生)'))
print('MSVC 痕迹: %s' % ('有' if b'mscoree.dll' in data or b'_CorExeMain' in data else '无'))

# 内嵌 PE
offs = []
i = data.find(b'MZ')
while i >= 0:
    if i+0x40 < len(data):
        e = struct.unpack_from('<I', data, i+0x3C)[0]
        if 0 < e < 0x400 and i+e+4 < len(data) and data[i+e:i+e+4] == b'PE\x00\x00':
            offs.append(i)
    i = data.find(b'MZ', i+1)
print('内嵌 PE: %s' % (', '.join('0x%X' % o for o in offs) or '无'))

# Goodix 协议常量（二进制）
PATTERNS = {
    'disable_report 33 00 CD': bytes([0x33,0x00,0xCD]),
    'confirm 35 00 CB':        bytes([0x35,0x00,0xCB]),
    'switch_to_patch 00 10 00 00 01 01': bytes([0x00,0x10,0x00,0x00,0x01,0x01]),
    'start_update 00 11 00 00 01 01':    bytes([0x00,0x11,0x00,0x00,0x01,0x01]),
    'reset 0E 13 00 00 01 01':           bytes([0x0E,0x13,0x00,0x00,0x01,0x01]),
    'ptp_mode 03 03 00 00 01 01':        bytes([0x03,0x03,0x00,0x00,0x01,0x01]),
    'load_flash 0E 12':                  bytes([0x0E,0x12,0x00,0x00,0x06]),
    'i2c_direct_rw 0E 20':               bytes([0x0E,0x20]),
    'addr 60 CC': bytes([0x60,0xCC]),
    'addr 50 95': bytes([0x50,0x95]),
    'addr 50 96': bytes([0x50,0x96]),
    'addr 45 2C': bytes([0x45,0x2C]),
    'addr 60 DC': bytes([0x60,0xDC]),
    'addr C0 00': bytes([0xC0,0x00]),
}
print('\n=== Goodix 协议常量（二进制搜索）===')
for k, pat in PATTERNS.items():
    n = data.count(pat)
    if n:
        first = data.find(pat)
        print('  %-38s 命中 %3d 处  (首个 @0x%X)' % (k, n, first))

# 字符串
a = data.decode('latin-1')
u = data.decode('utf-16-le', errors='ignore')
KEYS = ['goodix','Goodix','GOODIX','GT78','GXTP','27C6','27c6','HidD_','HidP_','SetupDi','DeviceIoControl',
        'CreateFile','SetFeature','GetFeature','SetOutputReport','WriteFile','ReadFile','IOCTL','report',
        'Report','haptic','Haptic','vibrat','Vibrat','LRA','motor','Motor','force','Force','press','Press',
        'report_id','ReportID','packet','Packet','0x0E','65','INTEL','I2C','i2c','firmware','Firmware',
        'update','Update','flash','Flash','.dll','.DLL','.sys','.bin','.BIN']
print('\n=== 相关字符串 (ASCII) ===')
seen=set(); c=0
for m in re.finditer(r'[\x20-\x7E]{5,}', a):
    s=m.group(0)
    if any(k in s for k in KEYS) and s not in seen:
        seen.add(s); print('   %s' % s[:130]); c+=1
        if c>=110: break
print('\n=== 相关字符串 (UTF-16) ===')
seen=set(); c=0
for m in re.finditer(r'[\x20-\x7E]{5,}', u):
    s=m.group(0)
    if any(k in s for k in KEYS) and s not in seen:
        seen.add(s); print('   [U] %s' % s[:130]); c+=1
        if c>=70: break
