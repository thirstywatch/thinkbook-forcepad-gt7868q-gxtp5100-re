# analyze_dell_tool.py - 分析 Dell Goodix 触控板固件工具（DUP 自解压包）
import os, re, hashlib, struct, collections

P = r'<HOME>\Downloads\Goodix-Touchpad-Firmware-Update-Tool_XTDR1_WIN_0.2.2.100_A00.EXE'
print('存在:', os.path.exists(P))
data = open(P, 'rb').read()
print('大小: %d 字节 (%.2f MB)' % (len(data), len(data)/1048576))
print('SHA256:', hashlib.sha256(data).hexdigest())
print('期望  : f476c0d5048f55f6bfde7e9403d3a8e9ac34a76d6a2c66884e4e7386f7863c38')
print('头 16 字节:', ' '.join('%02X' % b for b in data[:16]))

# 内嵌容器签名
sigs = {
    b'PK\x03\x04': 'ZIP 本地文件头',
    b'MSCF': 'CAB 头',
    b'MZ': 'PE 头 (MZ)',
    b'7z\xBC\xAF\x27\x1C': '7z 头',
    b'Rar!\x1A\x07': 'RAR 头',
    b'\x1F\x8B\x08': 'GZip 头',
    b'BZh': 'BZip2 头',
}
print('\n=== 内嵌容器扫描 ===')
for sig, name in sigs.items():
    offs = []
    i = data.find(sig)
    while i >= 0 and len(offs) < 12:
        offs.append(i)
        i = data.find(sig, i+1)
    if offs:
        print('  %-18s %d 处: %s' % (name, len(offs), ', '.join('0x%X' % o for o in offs[:12])))

# 字符串扫描
a = data.decode('latin-1')
u = data.decode('utf-16-le', errors='ignore')
keys = ['goodix', 'Goodix', 'GOODIX', 'GT7868', 'GXTP', '27C6', '27c6', 'HidD_', 'HidP_', 'SetupDi',
        'DeviceIoControl', 'CreateFile', 'SetFeature', 'GetFeature', 'SetOutputReport', 'WriteFile',
        'firmware', 'Firmware', 'haptic', 'Haptic', 'vibrat', 'Vibrat', 'LRA', 'touchpad', 'Touchpad',
        'update', 'Update', 'flash', 'Flash', 'BL_', 'verify', 'checksum']
print('\n=== 关键词命中的字符串（ASCII）===')
seen = set()
cnt = 0
for m in re.finditer(r'[\x20-\x7E]{5,}', a):
    s = m.group(0)
    for k in keys:
        if k in s:
            if s not in seen:
                seen.add(s)
                print('   %s' % s[:120])
                cnt += 1
            break
    if cnt > 90:
        break
print('  (共 %d 条)' % cnt)

print('\n=== 关键词命中的字符串（UTF-16）===')
seen2 = set(); cnt2 = 0
for m in re.finditer(r'[\x20-\x7E]{5,}', u):
    s = m.group(0)
    for k in keys:
        if k in s:
            if s not in seen2:
                seen2.add(s)
                print('   [U] %s' % s[:120])
                cnt2 += 1
            break
    if cnt2 > 60:
        break
print('  (共 %d 条)' % cnt2)
