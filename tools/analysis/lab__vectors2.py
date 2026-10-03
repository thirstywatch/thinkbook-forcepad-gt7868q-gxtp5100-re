import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data=open(BIN,"rb").read(); img=data[0x19ABC:]; BASE=0x08000000
vec=[struct.unpack_from("<I",img,i*4)[0] for i in range(76)]
names={0:"WWDG",1:"PVD",2:"TAMPER",3:"RTC",4:"FLASH",5:"RCC",6:"EXTI0",7:"EXTI1",8:"EXTI2",9:"EXTI3",
10:"EXTI4",11:"DMA1_CH1",12:"DMA1_CH2",13:"DMA1_CH3",14:"DMA1_CH4",15:"DMA1_CH5",16:"DMA1_CH6",
17:"DMA1_CH7",18:"ADC1_2",19:"USB_HP_CAN_TX",20:"USB_LP_CAN_RX0",21:"CAN_RX1",22:"CAN_SCE",
23:"EXTI9_5",24:"TIM1_BRK",25:"TIM1_UP",26:"TIM1_TRG_COM",27:"TIM1_CC",28:"TIM2",29:"TIM3",
30:"TIM4",31:"I2C1_EV",32:"I2C1_ER",33:"I2C2_EV",34:"I2C2_ER",35:"SPI1",36:"SPI2",37:"USART1",
38:"USART2",39:"USART3",40:"EXTI15_10",41:"RTCAlarm",42:"USBWakeUp",43:"TIM8_BRK",44:"TIM8_UP",
45:"TIM8_TRG_COM",46:"TIM8_CC",47:"ADC3",48:"FSMC",49:"SDIO",50:"TIM5",51:"SPI3",52:"UART4",
53:"UART5",54:"TIM6",55:"TIM7",56:"DMA2_CH1",57:"DMA2_CH2",58:"DMA2_CH3",59:"DMA2_CH4",60:"DMA2_CH5",
61:"ETH",62:"ETH_WKUP",63:"CAN2_TX",64:"CAN2_RX0",65:"CAN2_RX1",66:"CAN2_SCE",67:"OTG_FS"}
print("=== 向量表 (SP=0x%08X) ===" % vec[0])
for i,v in enumerate(vec):
    nm = "Reset" if i==1 else ("NMI" if i==2 else ("HardFault" if i==3 else names.get(i-16,"") if i>=16 else ""))
    flag=""
    if v % 2 == 0 and v != 0: flag=" (非 Thumb!?)"
    if v == 0: flag=" (空)"
    print(f"  [{i:2d}] 0x{v:08X}  {nm}{flag}")
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.skipdata=True
insns=list(md.disasm(bytes(img), BASE))
by={i.address:i for i in insns}
def show(a,n=25,title=""):
    print(f"\n--- {title} @0x{a:08X} ---")
    c=0
    for i in insns:
        if i.address<a: continue
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")
        c+=1
        if c>=n: break
for idx in (31,32,28,29):
    if idx < len(vec) and vec[idx]:
        show(vec[idx]&~1, 22, f"IRQ {idx} {names.get(idx,'')}")
