# fw_isr.py — 反汇编 TIM3 / USART1 / SysTick / DMA1_CH1 中断处理，并分析 97×1084 记录区结构
import struct, capstone, collections

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
def foff(a): return VOFF + (a - BASE)

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = False

def dis(tag, addr, n=72):
    print('\n=== %s @0x%08X ===' % (tag, addr))
    cnt = 0
    for ins in md.disasm(data[foff(addr):foff(addr) + n*4], addr):
        print('  0x%08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str))
        cnt += 1
        if cnt >= n:
            break

dis('TIM3 ISR', 0x0800D628)
dis('USART1 ISR', 0x0800DEE8, 60)

print('\n\n===== 97×1084 记录区结构分析 =====')
REC = 1084
recs = []
for i in range(97):
    off = i * REC
    recs.append(data[off:off+REC])
# 找出彼此相同的记录
sig = collections.defaultdict(list)
for i, r in enumerate(recs):
    sig[hash(r)].append(i)
print('不同记录种类数: %d' % len(sig))
groups = sorted(sig.values(), key=len, reverse=True)
for g in groups[:6]:
    print('  相同记录 %d 条: 索引 %s' % (len(g), g[:12]))

print('\n-- 记录 0 的前 48 字节 --')
print('  ' + ' '.join('%02X' % b for b in recs[0][:48]))
print('-- 记录 4 的前 48 字节 --')
print('  ' + ' '.join('%02X' % b for b in recs[4][:48]))
print('-- 记录 96 的前 48 字节（最后一条）--')
print('  ' + ' '.join('%02X' % b for b in recs[96][:48]))

# 统计记录 0 的字节分布，判断是波形(连续变化)还是配置(稀疏)
r0 = recs[0]
nz = sum(1 for b in r0 if b != 0)
print('\n记录 0: 非零字节 %d/%d, 取值范围 %d..%d' % (nz, REC, min(r0), max(r0)))
# 相邻差分，若是波形应平滑
diffs = [abs(r0[i+1] - r0[i]) for i in range(200) if i+1 < REC]
print('前 200 字节相邻差分均值: %.1f (波形应较小且连续)' % (sum(diffs)/len(diffs)))
print('记录 0 的 0..96 字节:')
print('  ' + ' '.join('%02X' % b for b in r0[:96]))
