import os
SRC = r"<WORKSPACE>"
data = open(SRC,"rb").read()
n=len(data)
VT=0x19ABC  # TF100A vector table offset

def u32(o): return data[o]|data[o+1]<<8|data[o+2]<<16|data[o+3]<<24

print("=== Vector table @0x%X (first 16 words) ===" % VT)
for i in range(16):
    w=u32(VT+i*4)
    tag=["SP","Reset","NMI","HardFault","MemManage","BusFault","UsageFault","-","-","-","SVCall","DebugMon","-","PendSV","SysTick"][i] if i<15 else "?"
    print("  [%2d] 0x%08X  %s" % (i,w,tag))

sp=u32(VT); rst=u32(VT+4)
print("SP=0x%08X  Reset(raw)=0x%08X  -> handler @0x%08X (file 0x%X)" % (sp,rst,rst&~1,VT+(rst&~1)-0x08000000))

# reset handler code (thumb) - dump 32 bytes
hb=VT+(rst&~1)-0x08000000
print("\n=== Reset handler bytes @0x%X ===" % hb)
print("  "+data[hb:hb+48].hex())

# locate end of TF100A image: scan for long 0x00 or 0xFF padding run within [VT, n]
def run_from(o,val):
    j=o
    while j<n and data[j]==val: j+=1
    return j-o
best00=0;bo00=0;bestff=0;boff=0
o=VT+0x200  # skip header
while o<n:
    if data[o]==0x00:
        r=run_from(o,0x00)
        if r>best00: best00=r;bo00=o
        o+=max(r,1)
    elif data[o]==0xFF:
        r=run_from(o,0xFF)
        if r>bestff: bestff=r;boff=o
        o+=max(r,1)
    else:
        o+=1
print("\n=== Image-end heuristics ===")
print("  longest 0x00 run after 0x19CBC: %d bytes @0x%X" % (best00,bo00))
print("  longest 0xFF run after 0x19CBC: %d bytes @0x%X" % (bestff,boff))
print("  file end: 0x%X  last 32 bytes: %s" % (n, data[-32:].hex()))

# how many 0x00/0xFF bytes in tail 4KB
tail=data[VT:]
nz=sum(1 for b in tail if b not in (0x00,0xFF))
print("  TF100A region size = 0x%X (%d bytes); bytes that are not 0x00/0xFF = %d (%.1f%%)" % (len(tail),len(tail),nz,100*nz/len(tail)))

# extract TF100A image to file (VT .. end of file)
OUT=r"<WORKSPACE>"
open(OUT,"wb").write(data[VT:])
print("\n  extracted TF100A image -> %s  (%d bytes)" % (OUT, len(data[VT:])))
