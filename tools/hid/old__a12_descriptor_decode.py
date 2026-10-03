import re
# ---- formal re-derivation of the descriptor semantics from the helper's own code ----
# sub_800FC80(base, desc):
#   reg_off  = (uint16_t)desc >> 6          ; ldrh at 0x0800FC98, lsrs #6 at 0x0800FC9C, ldr [r0,r1]
#   reg_bit  = desc & 0x1F                  ; and #0x1f at 0x0800FCA2, lsl 1<<bit
#   sr1_off  = desc >> 22                   ; lsrs #0x16 at 0x0800FCB4, ldr [r0,r2]
#   sr1_bit  = (desc >> 16) & 0x1F          ; ubfx #0x10,#5 at 0x0800FCBA
#   itbufen  = (base[4] & 0x400) != 0       ; 0x0800FC8E-FC94
DESCS = {0x050A0108:'ER/AF', 0x05010109:'EV/ADDR', 0x05060109:'EV/RxNE',
         0x05040109:'EV/STOPF', 0x05070109:'EV/TxE'}
I2C = {0x00:'CR1',0x04:'CR2',0x08:'OAR1',0x0C:'OAR2',0x10:'DR',0x14:'SR1',0x18:'SR2',0x1C:'CCR',0x20:'TRISE'}
CR1 = {0:'PE',1:'SMBUS',3:'SMBTYPE',4:'ENARP',5:'ENPEC',6:'ENGC',7:'NOSTRETCH',
       8:'START',9:'STOP',10:'ACK',11:'POS',12:'PEC',13:'ALERT',15:'SWRST'}
CR2 = {0:'FREQ0',5:'FREQ5',8:'ITERREN',9:'ITEVTEN',10:'ITBUFEN',11:'DMAEN',12:'LAST'}
SR1 = {0:'SB',1:'ADDR',2:'BTF',3:'ADD10',4:'STOPF',6:'RxNE',7:'TxE',8:'BERR',9:'ARLO',10:'AF',11:'OVR',12:'PECERR',14:'TIMEOUT',15:'SMBALERT'}
SR2 = {0:'MSL',1:'BUSY',2:'TRA',4:'GENCALL',5:'SMBDEFAULT',6:'SMBHOST',7:'DUALF'}
def bitname(tbl,o,b):
    return f"{(I2C.get(o,hex(o)))}.{tbl[o].get(b,'bit%d'%b) if o in tbl else 'bit%d'%b}"
print("=== FORMAL DECODE of the 5 descriptors passed to sub_800FC80(base=0x40005400, desc) ===")
for d,who in DESCS.items():
    lo = d & 0xFFFF
    en_off = lo >> 6; en_bit = d & 0x1F
    st_off = d >> 22; st_bit = (d >> 16) & 0x1F
    print(f"  desc {d:#010x}  [{who:9s}]")
    print(f"      enable-gate : {I2C.get(en_off,hex(en_off))} (offset {en_off:#x}) bit {en_bit:2d} = {bitname({en_off:CR2},en_off,en_bit)}")
    print(f"      status-test : offset {st_off:#x} ({I2C.get(st_off,hex(st_off))}) bit {st_bit:2d} = {bitname({st_off:SR1},st_off,st_bit)}")
    special = d in (0x05060109,0x05070109)
    print(f"      extra       : {'also requires CR2.ITBUFEN (bit10)  <-- from [base+4]&0x400' if special else 'none'}")

print()
print("=== set of SR1 bits EVER tested anywhere ==")
bits = sorted({(d>>16)&0x1F for d in DESCS})
print("  ", [(b, SR1.get(b,'?')) for b in bits])
print("  SR1.SB (bit0) tested?    ", 0 in bits)
print("  SR2.MSL (bit0) tested?   ", "SR2 is never read for a bit test (only read at 0x800FC5A-FC60 for the ADDR clear)")
print("=== set of CR1 bits written anywhere in the driver ===")
print("   PE(0) via 0x800fc0c ; SMBUS(1) cleared via 0x800fd24 ; ACK(10) via 0x800f9cc ; POS(11) via 0x800f9f8")
print("   START(8)/STOP(9): PRESENT?", False)
