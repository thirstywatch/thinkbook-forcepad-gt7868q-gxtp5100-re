"""提取 DSDT 里所有 ERCD 调用点 => EC 命令表 (cmd, d1..d5, 所在方法名)。"""
import re, struct
d=open("out/DSDT-528KB.bin","rb").read()

def pkglen(b,i):
    lead=b[i]; n=lead>>6
    if n==0: return lead & 0x3F, 1
    v=lead & 0x0F
    for k in range(n): v |= b[i+1+k] << (4+8*k)
    return v, 1+n

# 1) 收集所有 Method 的 [start, end, name, argc]
methods=[]; i=0
while i < len(d)-8:
    if d[i]==0x14:
        pl,pn = pkglen(d,i+1); off=i+1+pn
        nm=d[off:off+4]
        if re.fullmatch(rb"[A-Z_][A-Z0-9_]{3}", nm):
            methods.append((i, i+1+pl, nm.decode(), d[off+4]))
        i+=1
    else: i+=1
methods.sort()
print("DSDT 方法总数 = %d"%len(methods))

def enclosing(addr):
    best=None
    for st,en,nm,ac in methods:
        if st<=addr<en:
            if best is None or st>best[0]: best=(st,en,nm,ac)
    return best

# 2) 每个 ERCD 调用点
def imm(b,i):
    """读一个 AML 立即数；返回 (值或名字, 长度)"""
    t=b[i]
    if t==0x00: return 0,1
    if t==0x01: return 1,1
    if t==0x0A: return b[i+1],2
    if t==0x0B: return struct.unpack_from("<H",b,i+1)[0],3
    if t==0x0C: return struct.unpack_from("<I",b,i+1)[0],5
    if t==0x0E: return struct.unpack_from("<Q",b,i+1)[0],9
    if re.fullmatch(rb"[A-Z_][A-Z0-9_]{3}", b[i:i+4]): return b[i:i+4].decode('latin1'),4
    return None,0

print("\n=== ERCD 调用点 → EC 命令 ===")
print("%-8s %-6s | %-16s | %s"%("偏移","方法","cmd+d1..d5","响应取值"))
rows=[]
for m in re.finditer(rb"ERCD", d):
    j=m.start()
    # 只取「被调用」的位置（前面是 EC0_ 或 ^^/…/EC0. 之类），排除定义与方法名
    enc=enclosing(j)
    if enc and enc[0]==0x715A8: continue        # ERCD 自己的方法体
    if not enc: continue
    st,en,nm,ac = enc
    # 在该方法体内、ERCD 引用之前 220 字节窗口里找 Store(<imm>, Index(<local>, <idx>))
    ws=d[max(st,j-260):j]
    fields={}
    for mm in re.finditer(rb"\x70([\x00-\x7F])\x88", ws):
        pass
    k=0
    while k < len(ws)-2:
        if ws[k]==0x70:
            val,vl = imm(ws,k+1)
            if vl and k+1+vl < len(ws) and ws[k+1+vl]==0x88:
                q=k+2+vl
                # Index(<local>, <idx>, ...)
                if q<len(ws):
                    loc=ws[q]; 
                    idx,il = imm(ws,q+1)
                    if il and isinstance(idx,int) and 0<=idx<=8:
                        fields[idx]=val
                k = k+1+vl+1
                continue
        k+=1
    cmd=fields.get(0); d1=fields.get(1); d2=fields.get(2); d3=fields.get(3); d4=fields.get(4); d5=fields.get(5)
    # 响应：找 \x83\x88\x61\x0N\x00 (DerefOf(Index(Local1,N)))
    resp=[]
    for mm in re.finditer(rb"\x83\x88([\x60-\x67])([\x00-\x0E])\x00", d[j:j+400]):
        idx,il = imm(mm.group(2),0)
        resp.append(idx)
    def f(x): return "0x%02X"%x if isinstance(x,int) else (str(x) if x is not None else "-")
    print("0x%-6X %-6s | %s | %s"%(j, nm, " ".join(f(fields.get(i)) for i in range(6)), resp[:6]))
    rows.append((j,nm,fields))
print("\n共 %d 个 ERCD 调用点"%(len(rows)))
from collections import Counter
c=Counter(r[1] for r in rows)
print("\n调用 ERCD 的方法：", c.most_common(40))
