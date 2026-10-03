import struct
from capstone import *
data=open(r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN","rb").read()
img=data[0x19ABC:]; BASE=0x08000000; N=len(img)
off=0xAD80
hw1,hw2=struct.unpack_from("<HH",img,off)
print("bytes@0xAD80: %02X %02X %02X %02X" % (img[off],img[off+1],img[off+2],img[off+3]))
print("hw1=0x%04X hw2=0x%04X  hw1&0xF800=0x%04X  hw2&0xD000=0x%04X  hw2&0xF800=0x%04X" %
      (hw1,hw2,hw1&0xF800,hw2&0xD000,hw2&0xF800))
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.skipdata=True
n_bl=0; n_blx=0; tgts=set()
for i in md.disasm(bytes(img),BASE):
    if i.mnemonic=="bl": n_bl+=1
    elif i.mnemonic=="blx": n_blx+=1
print("capstone 全图: bl=%d  blx=%d" % (n_bl,n_blx))
