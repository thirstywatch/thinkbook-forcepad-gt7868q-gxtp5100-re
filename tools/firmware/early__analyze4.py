SRC = r"<WORKSPACE>"
data=open(SRC,"rb").read()
VT=0x19ABC
def u32(o): return data[o]|data[o+1]<<8|data[o+2]<<16|data[o+3]<<24

print("=== Extended TF100A vector table (words 16..80) ===")
for i in range(16,81):
    w=u32(VT+i*4)
    print("  [%2d] 0x%08X %s" % (i,w, "" if w else "(unused)"))

# where does vector table end (first run of >=8 consecutive zero words)?
print("\n=== Vector-table end scan ===")
z=0;end=-1
for i in range(16,200):
    w=u32(VT+i*4)
    if w==0:
        z+=1
        if z>=8 and end<0: end=i-8
    else:
        z=0
print("  first >=8 zero-words starts at index", end)

# count populated external ISR slots (non-zero beyond index 15)
pop=[i for i in range(16,200) if u32(VT+i*4)!=0]
print("  populated ISR slots (idx>15):", len(pop), "highest idx:", max(pop) if pop else None)
print("  => vector table covers up to IRQn ~", max(pop)-16 if pop else None)

# does image contain a clean flash-padding (0xFF) anywhere after VT? (would indicate truncation)
ff=data[VT:].find(b'\xff\xff\xff\xff\xff\xff\xff\xff')
print("  first 8x 0xFF after VT: at image offset 0x%X (%s)" % (ff, "none" if ff<0 else "present"))

# USART1 on STM32F1 = IRQn 37 -> table index 53
us1=u32(VT+53*4)
print("  USART1 vector (idx53): 0x%08X %s" % (us1, "(POPULATED)" if us1 else "(null)"))
