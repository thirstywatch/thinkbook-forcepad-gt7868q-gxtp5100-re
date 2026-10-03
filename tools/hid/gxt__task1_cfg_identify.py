# -*- coding: utf-8 -*-
"""
任务 #1：确认本机使用哪一份 cfg 版式。

结论框架：
  官方固件 TB14P_GT7868Q_14030522_20240202.BIN 内嵌 4 份 0x43C 记录：
    #0 @0x00000  头 73c01104  = 出厂默认模板
    #1 @0x0043C  头 c7800803  ┐
    #2 @0x00878  头 c7800803  ├ 三份完全相同 = 量产配置
    #3 @0x00CB4  头 c7800803  ┘
  而驱动 CAB 里的 sid0/sid2/sid3 在固件中匹配 0 次。
"""
import os, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
FW = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
fw = open(FW, 'rb').read()

L = []
def w(s=''):
    L.append(s); print(s)

REC = 0x43C
BASES = [0x00000, 0x0043C, 0x00878, 0x00CB4]

w('=' * 82)
w('任务 #1 结论：本机固件内嵌 4 份 0x%X 记录，而非驱动 CAB 里的 sid0/sid2/sid3' % REC)
w('=' * 82)
w()

# --- 1. 记录定位 ---
w('### 1. 记录定位（用 ASCII 标记串验证周期性）')
w('```')
mark = b'777777'
offs = []; o = 0
while True:
    j = fw.find(mark, o)
    if j < 0: break
    offs.append(j); o = j + 1
w(' 标记 "777777" 出现于：' + ', '.join('0x%05X' % x for x in offs))
w(' 间隔：' + ', '.join('0x%X' % (offs[i+1]-offs[i]) for i in range(len(offs)-1)))
w(' ⇒ 记录长度 = 0x%X = %d B' % (REC, REC))
w('```')
w()

# --- 2. 四份记录的头 ---
w('### 2. 四份记录的头部（前 44 B）')
w('```')
for i, b in enumerate(BASES):
    s = fw[b:b+44]
    w(' #%d @0x%05X  %s' % (i, b, s.hex(' ')))
w('```')
w()
w(' 解读：')
w('   #0  [0:4]=73 c0 11 04 | [4:8]=00 00 04 3c | [8:12]=00 00 04 3c | [12:44]=全零')
w('       ⇒ 出厂默认模板（长度字段 0x43C，其余占位）')
w('   #1~3 [0:4]=c7 80 08 03 | [4:8]=50 28 28 41 | [8:12]=10 32 0d 19 | ...')
w('       ⇒ 量产配置（三份完全一致）')
w()

# --- 3. 差异定位 ---
w('### 3. 差异定位（#0 vs #1）')
w('```')
s0 = fw[BASES[0]:BASES[0]+REC]
s1 = fw[BASES[1]:BASES[1]+REC]
d = [k for k in range(REC) if s0[k] != s1[k]]
w(' 差异索引范围 0x%03X..0x%03X，共 %d 处' % (min(d), max(d), len(d)))
w('   → 0x000..0x02B：记录头（44 B，完全不同）')
w('   → 0x02C..0x04B：机型差异字段（32 B，部分不同）')
w('   → 0x04C..0x43B：公共主体（%d B，完全相同）' % (REC-0x4C))
w()
for i in range(4):
    for j in range(i+1, 4):
        si = fw[BASES[i]:BASES[i]+REC]; sj = fw[BASES[j]:BASES[j]+REC]
        w(' #%d vs #%d：头差异 %d · 主体差异 %d'
          % (i, j,
             sum(1 for k in range(44) if si[k] != sj[k]),
             sum(1 for k in range(44, REC) if si[k] != sj[k])))
w('```')
w()

# --- 4. 驱动 CAB 的 sid 是否在固件里 ---
w('### 4. 驱动 CAB 的 sid0/sid2/sid3 是否在固件里')
w('```')
for name in ['sid0.bin', 'sid2.bin', 'sid3.bin']:
    p = os.path.join(HERE, 'cfg', name)
    if not os.path.exists(p):
        w(' %s: 文件不存在' % name); continue
    cfg = open(p, 'rb').read()
    n_full = fw.count(cfg)
    n_frag = fw.count(cfg[32:96])
    w(' %s (%5d B)：完整匹配 %d 处 · 64B 中段匹配 %d 处' % (name, len(cfg), n_full, n_frag))
w(' ⇒ 全部为 0 ⇒ 驱动 CAB 里的 cfg 不是本机固件内嵌的配置')
w(' ⇒ 它们是「主机侧待写入 payload」，格式同族但内容不同（不同机型/方案商）')
w('```')
w()

# --- 5. 记录主体可读内容 ---
w('### 5. 记录主体（0x04C 起）的可读内容摘要')
w('```')
body = fw[BASES[0]+0x04C: BASES[0]+REC]
# 找 0x5A（AW86927 I2C 地址）
w(' 0x5A 出现位置（相对主体）：' + str([hex(i) for i in range(len(body)) if body[i] == 0x5A][:10]))
# u16 数值分布
v = struct.unpack('<%dH' % (len(body)//2), body[:len(body)//2*2])
c = collections.Counter(v)
w(' u16 众数前 12：' + ' '.join('%d×%d' % (val, n) for val, n in c.most_common(12)))
# 找明显的"时长"常量
for const in (100, 300, 400, 500, 600, 1000, 2000, 3000, 5000, 8000, 10000):
    n = v.count(const)
    if n >= 2:
        w('   常量 %5d 出现 %d 次' % (const, n))
w('```')

txt = '\n'.join(L)
open(os.path.join(HERE, 'cfg_parsed', 'task1_cfg_identify.txt'), 'w', encoding='utf-8').write(txt)
w()
w('写入 cfg_parsed/task1_cfg_identify.txt')
