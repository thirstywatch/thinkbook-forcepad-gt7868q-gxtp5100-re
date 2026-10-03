import struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
d=open(BIN,"rb").read(); REC=1084
print("=== 记录头 32 字节 (找校验字段) ===")
for i in range(6):
    r=d[i*REC:(i+1)*REC]
    print(f"  记录{i}: {r[:32].hex(' ')}")
print()
def sum8(b): return sum(b)&0xFF
def sum16le(b):
    s=0
    for k in range(0,len(b)-1,2): s=(s+struct.unpack_from('<H',b,k)[0])&0xFFFF
    return s
def sum16be(b):
    s=0
    for k in range(0,len(b)-1,2): s=(s+struct.unpack_from('>H',b,k)[0])&0xFFFF
    return s
print("=== 对记录 0 做各种校验假设 (看哪个能得 0 或与头部字段吻合) ===")
r0=d[0:REC]
head=struct.unpack_from("<I",r0,0)[0]
print(f"  头部前 4 字节 = 0x{head:08X}")
tests = {
 "整条 sum8": sum8(r0),
 "整条 sum8 (去掉前4字节)": sum8(r0[4:]),
 "整条 sum16le": sum16le(r0),
 "整条 sum16be": sum16be(r0),
 "前4字节之后 sum8": sum8(r0[4:]),
}
for k,v in tests.items(): print(f"  {k} = 0x{v:02X} / {v}")
print()
print("=== 记录 1..5 的头部字段对比 (找变化量) ===")
for i in range(6):
    r=d[i*REC:(i+1)*REC]
    print(f"  记录{i}: [0:4]={r[:4].hex(' ')}  sum8(整条)=0x{sum8(r):02X}  sum8([4:])=0x{sum8(r[4:]):02X}")
