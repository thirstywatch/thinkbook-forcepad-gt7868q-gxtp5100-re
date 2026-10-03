#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨芯片子固件块比对 —— ★ 按【flash 地址】比对，不是按序号。
理由：不同型号的子固件数量/长度不同（13/13/13/12），按序号比会张冠李戴。
flash 地址是官方子固件表里写明的语义定位，才是正确的比对键。

目的：找"芯片无关的通用资产" —— 若某块在 GT7868Q / GT9896 / GT7863 三个不同芯片上
      都存在且逐字节相同，它就是 Goodix 家族共用资产，**波形库是首选候选**。
"""
import sys, os, struct, hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decrypt import find_container, parse_container, DATA_OFF

FIRMWARES = {
 'G7868Q_2024': r'..\..\bios-re\GT7868Q_native_fw.bin',
 'G7868Q_2020': r'..\goodix-fw\goodix_tp_payload.bin',
 'GT9896':      r'..\anchor-hunt\goodix_gt9896_fw.bin',
 'G7863':       r'<WORKSPACE>',
}
K = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'K_gt7868q.bin'),'rb').read() \
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)),'K_gt7868q.bin')) else None

def load(path, do_xor):
    if not os.path.exists(path):
        print('MISSING', path); return None
    buf = open(path,'rb').read()
    o = find_container(buf)
    if o is None:
        print('  no container in', path); return None
    info = parse_container(buf, o)
    base = o + DATA_OFF
    subs = {}
    for s in info['subsys']:
        raw = buf[base:base+s['size']]
        if do_xor and K:
            # 数据区相对相位 = 316 + 0x100 = 572；这里给每块单独从 0 起算
            plain = bytes(v ^ K[(i + 316 + 0x100) % 1024] for i, v in enumerate(raw))
        else:
            plain = raw
        subs[s['flash_addr']] = dict(type=s['type'], size=s['size'], data=plain,
                                     md5=hashlib.md5(plain).hexdigest())
    return dict(info=info, subs=subs, container=o)

ALL = {}
for k, p in FIRMWARES.items():
    r = load(p, do_xor=(k != 'GT7863'))
    if r:
        ALL[k] = r
        i = r['info']
        print('%-12s container@0x%04X pid=%s subsys=%d' % (k, r['container'],
              i['fw_pid'].rstrip(b'\x00').decode('ascii','replace'), i['subsys_num']))

# 汇总所有 flash 地址
alladdr = sorted({a for r in ALL.values() for a in r['subs']})
print('\n' + '='*104)
print('★ 按 flash 地址的跨芯片存在性矩阵（SAME=与 G7868Q_2024 逐字节相同；%=相同比例；--=该芯片无此地址）')
print('='*104)
hdr = f'{"flash":>8} {"size":>7} {"type":>4}  ' + ' '.join(f'{k:>12}' for k in ALL)
print(hdr); print('-'*len(hdr))
ref_k = 'G7868Q_2024' if 'G7868Q_2024' in ALL else list(ALL)[0]
for a in alladdr:
    ref = ALL[ref_k]['subs'].get(a)
    if not ref: continue
    row = f'{a:>8X} {ref["size"]:>7} {ref["type"]:>4}  '
    for k in ALL:
        b = ALL[k]['subs'].get(a)
        if not b: row += f'{"--":>12} '
        elif b['size'] != ref['size']: row += f'{"LEN":>12} '
        elif b['md5'] == ref['md5']: row += f'{"SAME":>12} '
        else:
            same = sum(1 for x,y in zip(b['data'], ref['data']) if x==y)/len(ref['data'])
            row += f'{same*100:>11.1f}% '
    print(row)

# 只被一两个芯片有的地址
print('\n' + '='*104)
print('只出现在单一芯片的 flash 地址（=该型号专属资产）')
print('='*104)
for a in alladdr:
    owners = [k for k in ALL if a in ALL[k]['subs']]
    if len(owners) == 1:
        print(f'  0x{a:05X}  size=0x{ALL[owners[0]]["subs"][a]["size"]:04X}  仅 {owners[0]}')
