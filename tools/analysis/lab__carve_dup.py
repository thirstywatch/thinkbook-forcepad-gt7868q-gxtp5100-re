# carve_dup.py - 静态解包 Dell DUP（不执行任何东西）
import io, os, struct, zipfile

P = r'<HOME>\Downloads\Goodix-Touchpad-Firmware-Update-Tool_XTDR1_WIN_0.2.2.100_A00.EXE'
OUT = r'<LAB>\touchpad-lab\vendor\dup'
os.makedirs(OUT, exist_ok=True)
data = open(P, 'rb').read()
print('DUP size = %d' % len(data))

# --- 1) 找 EOCD 并反推 ZIP 起始 ---
EOCD = b'PK\x05\x06'
cds = []
i = data.find(EOCD)
while i >= 0:
    if i + 22 <= len(data):
        try:
            n_ent, cd_size, cd_off = struct.unpack_from('<HH', data, i+10)[0], struct.unpack_from('<I', data, i+12)[0], struct.unpack_from('<I', data, i+16)[0]
            cds.append((i, n_ent, cd_size, cd_off))
        except Exception:
            pass
    i = data.find(EOCD, i+1)
print('EOCD 候选: %s' % ', '.join('0x%X(ent=%d,cdsz=%d,cdoff=0x%X)' % c for c in cds))

archives = []
for (e, n_ent, cd_size, cd_off) in cds:
    start = e + 22 - cd_size - cd_off          # 忽略 comment
    if 0 <= start < len(data):
        archives.append(start)
        print('  → 推测 ZIP 起始 0x%X' % start)

# 也把每个 PK\x03\x04 当作可能的独立小档案试一遍
starts = set(archives)
i = data.find(b'PK\x03\x04')
while i >= 0:
    starts.add(i)
    i = data.find(b'PK\x03\x04', i+1)

print('\n=== 尝试打开内嵌 ZIP ===')
found = []
for s in sorted(starts):
    try:
        zf = zipfile.ZipFile(io.BytesIO(data[s:]))
        names = zf.namelist()
        if names:
            print('  ZIP @0x%X: %d 个条目' % (s, len(names)))
            for nm in names[:40]:
                print('      %s' % nm)
            found.append((s, zf))
    except Exception as ex:
        pass

# --- 2) 解出所有条目 ---
if found:
    s, zf = found[0]
    print('\n=== 解包到 %s ===' % OUT)
    for nm in zf.namelist():
        try:
            dst = os.path.join(OUT, os.path.basename(nm))
            with zf.open(nm) as src, open(dst, 'wb') as f:
                f.write(src.read())
            print('   %-60s %d 字节' % (os.path.basename(nm), os.path.getsize(dst)))
        except Exception as ex:
            print('   %s 解包失败: %s' % (nm, ex))
else:
    print('\n没有可直接打开的 ZIP；尝试切割内嵌 PE')
    # 内嵌 PE：从头扫描 MZ，校验 PE 头与 SizeOfImage
    offs = []
    i = data.find(b'MZ')
    while i >= 0:
        if i+0x40 < len(data):
            e_lfanew = struct.unpack_from('<I', data, i+0x3C)[0]
            if 0 < e_lfanew < 0x400 and i+e_lfanew+4 < len(data) and data[i+e_lfanew:i+e_lfanew+4] == b'PE\x00\x00':
                offs.append(i)
        i = data.find(b'MZ', i+1)
    print('内嵌 PE: %s' % ', '.join('0x%X' % o for o in offs))
    for o in offs:
        e_lfanew = struct.unpack_from('<I', data, o+0x3C)[0]
        base = o + e_lfanew
        nsec = struct.unpack_from('<H', data, base+6)[0]
        optsz = struct.unpack_from('<H', data, base+20)[0]
        size_img = struct.unpack_from('<I', data, base+24+56)[0]
        size_hdr = struct.unpack_from('<I', data, base+24+60)[0]
        total = size_hdr + sum(struct.unpack_from('<I', data, base+24+optsz+16+ii*40+16)[0]
                               for ii in range(nsec)) if nsec < 40 else size_img
        print('  PE@0x%X: 段数=%d SizeOfImage=0x%X 估算长度=%d' % (o, nsec, size_img, total))
