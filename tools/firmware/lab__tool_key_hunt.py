# -*- coding: utf-8 -*-
"""在固件工具二进制里找：加密算法常量 / 密钥 / 解密 API / 内嵌高熵块。
只读文件，绝不执行任何二进制。"""
import io, os, hashlib, math, re

CANDS = [
    r'<LAB>\touchpad-lab\poc\pkg\goodix-fw-tool.exe',
    r'<LAB>\touchpad-lab\poc\pkg\extract\zip0\DellTouchpadUpdate_Hellcat_v0.2.2.100.exe',
]

CONSTS = [
    ('AES S-box',        bytes.fromhex('637C777BF26B6FC53001672BFED7AB76')),
    ('AES InvS-box',     bytes.fromhex('52096AD53036A538BF40A39E81F3D7FB')),
    ('AES Rcon',         bytes.fromhex('01020408102040801B36')),
    ('SM4 S-box',        bytes.fromhex('D690E9FECCE13DB716B614C228FB2C05')),
    ('PRESENT S-box',    bytes.fromhex('0C560B90AD3EF84712')),
    ('TEA/XTEA delta',   bytes.fromhex('9E3779B9')),
    ('TEA delta LE',     bytes.fromhex('B9793 79E'.replace(' ', ''))),
    ('ChaCha "expand 32-byte k"', b'expand 32-byte k'),
    ('Blowfish P-init',  bytes.fromhex('243F6A8885A308D3')),
]

APIS = [b'bcrypt.dll', b'ncrypt.dll', b'advapi32.dll', b'CryptDecrypt', b'CryptEncrypt',
        b'CryptImportKey', b'BCryptDecrypt', b'BCryptOpenAlgorithmProvider',
        b'libcrypto', b'openssl', b'mbedtls', b'wolfssl', b'tiny-AES', 'aes.c'.encode()]

WORDS = ['aes', 'AES', 'decrypt', 'Decrypt', 'encrypt', 'Encrypt', 'gtx8', 'YELSTO',
         '7868', 'Goodix', 'GOODIX', 'capsule', 'Capsule', 'TB14P', 'Berlin', 'BERLIN',
         'firmware', 'Firmware', 'payload', 'xor', 'obfus']

out = []
def P(s=''):
    print(s); out.append(str(s))

def ent(b):
    if not b: return 0.0
    c = [0] * 256
    for x in b: c[x] += 1
    e = 0.0
    for v in c:
        if v:
            p = v / len(b); e -= p * math.log2(p)
    return e

for path in CANDS:
    if not os.path.exists(path):
        P('### [缺失] ' + path); P(); continue
    d = open(path, 'rb').read()
    name = os.path.basename(path)
    P('=' * 78)
    P('### %s   %d 字节   SHA256 %s' % (name, len(d), hashlib.sha256(d).hexdigest()[:32]))
    P('=' * 78)
    P('  .NET 元数据(BSJB): %s' % (d.find(b'BSJB') >= 0))
    P()

    P('  --- 加密算法常量 ---')
    any_hit = False
    for nm, pat in CONSTS:
        i = d.find(pat)
        hits = []
        while i >= 0 and len(hits) < 4:
            hits.append(hex(i)); i = d.find(pat, i + 1)
        if hits:
            any_hit = True
            P('    %-22s 命中 %s' % (nm, hits))
    if not any_hit:
        P('    （无任何命中）')
    P()

    P('  --- 加解密 API / 库痕迹 ---')
    any_api = False
    for api in APIS:
        for enc in (api, api.decode('latin1').encode('utf-16le')):
            i = d.find(enc)
            if i >= 0:
                any_api = True
                P('    %-28s @ %s (%s)' % (api.decode('latin1'), hex(i),
                                           'utf16' if len(enc) > len(api) else 'ascii'))
                break
    if not any_api:
        P('    （无）')
    P()

    P('  --- 关键词出现次数（ascii+utf16 合计）---')
    for w in WORDS:
        n = d.count(w.encode('latin1')) + d.count(w.encode('utf-16le'))
        if n:
            P('    %-10s %d' % (w, n))
    P()

    P('  --- 高熵区块（≥64KB 且熵>7.9，可能是内嵌固件）---')
    found = False
    BS = 4096
    runs = []
    cur = None
    for k in range(0, len(d) - BS, BS):
        e = ent(d[k:k + BS])
        if e > 7.9:
            if cur is None: cur = k
        else:
            if cur is not None:
                runs.append((cur, k)); cur = None
    if cur is not None: runs.append((cur, len(d) - BS))
    for a, b in runs:
        if b - a >= 65536:
            found = True
            P('    0x%06X .. 0x%06X  (%d B, 熵 %.3f)' % (a, b, b - a, ent(d[a:min(b, a + 262144)])))
    if not found:
        P('    （无 ≥64KB 的高熵块）')
    P()

    P('  --- 前 64 字节 ---')
    P('    ' + d[:64].hex(' '))
    P()

o = r'<LAB>\touchpad-lab\re\tool_key_hunt_out.txt'
io.open(o, 'w', encoding='utf-8').write('\n'.join(out))
print('[已写] ' + o)
