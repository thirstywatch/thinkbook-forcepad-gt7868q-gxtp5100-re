"""反编译 DSDT 里的 ERCD 方法体 + 提取所有调用点的命令常量。"""
import struct, re, sys

SPACE={0x00:"Zero",0x01:"One",0x0A:"Byte",0x0B:"Word",0x0C:"Dword",0x0E:"Qword"}
OPS={0x00:"ZeroOp",0x01:"OneOp",0x06:"AliasOp",0x08:"NameOp",0x0A:"BytePrefix",0x0B:"WordPrefix",
 0x0C:"DwordPrefix",0x0E:"QwordPrefix",0x10:"ScopeOp",0x11:"BufferOp",0x12:"PackageOp",0x13:"VarPackageOp",
 0x14:"MethodOp",0x15:"ExternalOp",0x5B:"ExtOpPrefix",0x60:"Local0",0x61:"Local1",0x62:"Local2",
 0x63:"Local3",0x64:"Local4",0x65:"Local5",0x66:"Local6",0x67:"Local7",0x68:"Arg0",0x69:"Arg1",
 0x6A:"Arg2",0x6B:"Arg3",0x6C:"Arg4",0x6D:"Arg5",0x6E:"Arg6",0x70:"StoreOp",0x71:"RefOfOp",
 0x72:"AddOp",0x74:"SubtractOp",0x75:"IncrementOp",0x76:"DecrementOp",0x77:"MultiplyOp",0x78:"DivideOp",
 0x79:"ShiftLeftOp",0x7A:"ShiftRightOp",0x7B:"AndOp",0x7C:"NandOp",0x7D:"OrOp",0x7E:"NorOp",0x7F:"XorOp",
 0x80:"NotOp",0x81:"FindSetLeftBitOp",0x86:"NotifyOp",0x88:"IndexOp",0x89:"DerefOfOp",0x8A:"SizeOfOp",
 0x8C:"ObjectTypeOp",0x8E:"ConcatenateOp",0x90:"LAndOp",0x91:"LOrOp",0x92:"LNotOp",0x93:"LEqualOp",
 0x94:"LGreaterOp",0x95:"LLessOp",0x96:"ToBufferOp",0x97:"ToDecimalStringOp",0x98:"ToHexStringOp",
 0x99:"ToIntegerOp",0x9C:"ToStringOp",0x9D:"CopyObjectOp",0xA0:"IfOp",0xA1:"ElseOp",0xA2:"WhileOp",
 0xA3:"NoopOp",0xA4:"ReturnOp",0xA5:"BreakOp",0xCC:"BreakPointOp"}
EXT={0x01:"MutexOp",0x02:"EventOp",0x12:"CondRefOfOp",0x13:"CreateFieldOp",0x1F:"LoadTableOp",
 0x21:"StallOp",0x22:"SleepOp",0x23:"IndexOp",0x24:"AcquireOp",0x25:"SignalOp",0x26:"WaitOp",
 0x28:"ResetOp",0x29:"ReleaseOp",0x2A:"FromBCDOp",0x2B:"ToBCDOp",0x30:"RevisionOp",0x31:"DebugOp",
 0x32:"FatalOp",0x33:"TimerOp",0x80:"OpRegionOp",0x81:"FieldOp",0x82:"DeviceOp",0x83:"ProcessorOp",
 0x84:"PowerResOp",0x85:"ThermalZoneOp",0x86:"IndexFieldOp",0x87:"BankFieldOp",0x88:"DataRegionOp"}

def pkglen(b,i):
    lead=b[i]; n=lead>>6
    if n==0: return lead & 0x3F, 1
    v=lead & 0x0F
    for k in range(n): v |= b[i+1+k] << (4+8*k)
    return v, 1+n

d=open("out/DSDT-528KB.bin","rb").read()

# 1) 找 ERCD 的 MethodOp
targets=[]
i=0
while i < len(d)-8:
    if d[i]==0x14:
        pl,pn = pkglen(d,i+1)
        off=i+1+pn
        if d[off:off+4]==b"ERCD":
            targets.append((i, pl, pn, off, d[off+4]))
    i+=1
print("=== ERCD 的 MethodOp ===")
for t in targets: print("   @0x%X PkgLen=0x%X argcount=%d"%(t[0],t[1],t[4]))

def dump_method(start, plen, pn, name_off, argn):
    body_s = name_off+5
    body_e = start+1+plen
    print("\n--- %s 方法体 0x%X..0x%X (%d 字节, %d 参数) ---"%(d[name_off:name_off+4].decode('latin1'),body_s,body_e,body_e-body_s,argn))
    s=d[body_s:body_e]
    for k in range(0,len(s),16):
        x=s[k:k+16]
        print("   +%03X  %s  |%s|"%(k," ".join("%02X"%c for c in x),"".join(chr(c) if 32<=c<127 else "." for c in x)))
    return s

allb=[]
for st,pl,pn,no,argn in targets:
    allb.append(dump_method(st,pl,pn,no,argn))

# 2) 所有 ERCD 调用点的「前面的命令字节」——扫 DSDT 里 0x0A xx（Byte 常量）出现在 ERCD 引用前的模式
print("\n=== ERCD 调用点（\x88 Index 写入模式）附近的 Byte 常量 ===")
pat = re.compile(rb"\x70\x0a(.)\x88")
hits=[]
for m in re.finditer(rb"ERCD", d):
    j=m.start()
    ctx=d[max(0,j-200):j]
    for mm in re.finditer(rb"\x70\x0a(.)", ctx):
        hits.append((mm.start()+max(0,j-200), mm.group(1)[0]))
    # 也找 \x70 <byte> \x88 的直接形式
print("   找到 ERCD 引用 %d 处"%len(re.findall(rb"ERCD",d)))
from collections import Counter
c=Counter(v for _,v in hits)
print("   附近 Byte 常量分布：", [(hex(k),n) for k,n in c.most_common(30)])
