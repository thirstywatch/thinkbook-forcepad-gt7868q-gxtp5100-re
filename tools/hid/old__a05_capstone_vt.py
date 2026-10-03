import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
BIN = r"<WORKSPACE>"
BASE_ADDR = 0x08005000; BASE_OFF = 0x19ABC
blob = open(BIN,'rb').read()
SEG = 56480
seg = blob[BASE_OFF:BASE_OFF+SEG]
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True

def disasm(a0, a1):
    o0 = a0 - BASE_ADDR
    o1 = a1 - BASE_ADDR
    out=[]
    for i in md.disasm(seg[o0:o1], a0):
        out.append(f"{i.address:08X}  {i.mnemonic:8s} {i.op_str}")
    return out

print("=== independent capstone disasm 0x800894C..0x8008978 ===")
for l in disasm(0x800894C, 0x8008978): print(" ", l)
print()
print("=== 0x8008A40..0x8008A80 ===")
for l in disasm(0x8008A40, 0x8008A80): print(" ", l)
print()
print("=== ---------------- VECTOR TABLE at 0x08005000 ----------------")
vt = []
for i in range(64):
    w = struct.unpack_from('<I', seg, i*4)[0]
    vt.append(w)
core = ["InitialSP","Reset","NMI","HardFault","MemManage","BusFault","UsageFault","rsv7","rsv8","rsv9","rsv10","SVC","DebugMon","rsv13","PendSV","SysTick"]
irq = ["WWDG","PVD","TAMPER","RTC","FLASH","RCC","EXTI0","EXTI1","EXTI2","EXTI3","EXTI4",
 "DMA1_Ch1","DMA1_Ch2","DMA1_Ch3","DMA1_Ch4","DMA1_Ch5","DMA1_Ch6","DMA1_Ch7","ADC1_2",
 "USB_HP_CAN1_TX","USB_LP_CAN1_RX0","CAN1_RX1","CAN1_SCE","EXTI9_5","TIM1_BRK","TIM1_UP",
 "TIM1_TRG_COM","TIM1_CC","TIM2","TIM3","TIM4","I2C1_EV","I2C1_ER","I2C2_EV","I2C2_ER",
 "SPI1","SPI2","USART1","USART2","USART3","EXTI15_10","RTCAlarm","USBWakeUp","TIM8_BRK"]
for i,w in enumerate(vt):
    if i < 16:
        name = core[i]; kind="CORE"
    else:
        n = i-16
        name = irq[n] if n < len(irq) else f"IRQ{n}"; kind="IRQ"
    flag = ""
    if name in ("I2C1_EV","I2C1_ER","I2C2_EV","I2C2_ER"): flag = "   <<<<<< I2C"
    print(f"  idx{i:3d} off{i*4:#06x} {kind} {name:16s} = {w:#010x}{flag}")
