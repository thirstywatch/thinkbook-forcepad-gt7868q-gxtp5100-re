import struct, re, collections
b=open("touchpad_GT7868Q_fw.bin","rb").read()
IMG_FILE=0x19ABC; IMG_BASE=0x08005000; END=0x26E00
def f2a(f): return IMG_BASE+(f-IMG_FILE)
def a2f(a): return IMG_FILE+(a-IMG_BASE)
img=b[IMG_FILE:END]
# 1) 扫字面量池：所有 4 字节对齐值像 flash 地址的
lits=collections.defaultdict(list)
for off in range(0,len(img)-4,4):
    v=struct.unpack_from("<I",img,off)[0]
    if IMG_BASE<=v<f2a(END): lits[v].append(f2a(off))
print("=== 字面量池里指向镜像内的指针：%d 个不同目标 ==="%len(lits))

# 2) 真正的字符串（版本 banner 区）
print("\n=== 版本 banner 区 file 0x19E80..0x19F40 ===")
for i in range(0x19E80,0x19F40,16):
    x=b[i:i+16]; print("%06X %s |%s|"%(i," ".join("%02X"%v for v in x),"".join(chr(v) if 32<=v<128 else "." for v in x)))

print("\n=== 谁引用了版本 banner / 关键串 ===")
for name,fa in (("TF100A_Test_FW",0x08005410),("Nov 28 2023",0x08005430),("5.21.01.23007",0x08011A32),
                ("0123456789abcdef",0x08011704),("7868Q",0x0800114B)):
    print("   %-18s flash 0x%08X -> 引用 %s"%(name,fa, ["0x%08X"%x for x in lits.get(fa,[])][:6] or "无"))

# 3) 最高频被调用函数 0x08005188 是什么
print("\n=== 函数 0x08005188（被调用 56 次）===")
f=a2f(0x08005188)
for i in range(f-8,f+0x60,4):
    print("   file 0x%X (%08X)  %s"%(i,f2a(i)," ".join("%02X"%v for v in b[i:i+4])))

# 4) 用反汇编文件找大字面量引用
L=[l for l in open("touchpad_TF100A_thumb.asm.txt",encoding="utf-8").read().splitlines()]
print("\n=== 反汇编里出现 '0x8005410'/'0x8011a32' 等字面量的行 ===")
import re as _re
for pat in ("0x8005410","0x8005430","0x8011a32","0x800114b","0x8011704","0x800503c"):
    hits=[l for l in L if pat.lower() in l.lower()]
    print("   %-12s %d 处  %s"%(pat,len(hits),hits[:3]))

# 5) 镜像尾部（尾部 0x26E00 之后是包尾）已有，这里看镜像内是否有函数指针表
print("\n=== 镜像内 '函数指针表' 候选（连续 ≥4 个 flash 地址）===")
runs=[];cur=None
for off in range(0,len(img)-4,4):
    v=struct.unpack_from("<I",img,off)[0]
    if IMG_BASE<=v<f2a(END):
        if cur and off==cur[1]+4: cur[1]=off
        else:
            if cur and (cur[1]-cur[0])>=12: runs.append(tuple(cur))
            cur=[off,off]
    else:
        if cur and (cur[1]-cur[0])>=12: runs.append(tuple(cur))
        cur=None
if cur and (cur[1]-cur[0])>=12: runs.append(tuple(cur))
print("   找到 %d 段"%len(runs))
for a,c in runs[:15]:
    print("      flash 0x%08X..0x%08X  (%d 项)"%(f2a(IMG_FILE+a),f2a(IMG_FILE+c),(c-a)//4+1))
