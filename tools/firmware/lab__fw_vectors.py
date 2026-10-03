# fw_vectors.py — 打印完整中断向量表（STM32F1 映射）并反汇编关键中断处理程序
import struct, capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
def foff(a): return VOFF + (a - BASE)
def u32(a): return struct.unpack_from('<I', data, foff(a))[0]

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = False

NAMES = ['SP','Reset','NMI','HardFault','MemManage','BusFault','UsageFault','r7','r8','r9','r10','SVC','DebugMon','r13','PendSV','SysTick',
 'WWDG','PVD','TAMPER','RTC','FLASH','RCC','EXTI0','EXTI1','EXTI2','EXTI3','EXTI4','DMA1_CH1','DMA1_CH2','DMA1_CH3','DMA1_CH4','DMA1_CH5','DMA1_CH6','DMA1_CH7',
 'ADC1_2','USB_HP_CAN_TX','USB_LP_CAN_RX0','CAN_RX1','CAN_SCE','EXTI9_5','TIM1_BRK','TIM1_UP','TIM1_TRG','TIM1_CC','TIM2','TIM3','TIM4',
 'I2C1_EV','I2C1_ER','I2C2_EV','I2C2_ER','SPI1','SPI2','USART1','USART2','USART3','EXTI15_10','RTCAlarm','USBWakeUp',
 'TIM8_BRK','TIM8_UP','TIM8_TRG','TIM8_CC','ADC3','FSMC','SDIO','TIM5','SPI3','UART4','UART5','TIM6','TIM7','DMA2_CH1','DMA2_CH2','DMA2_CH3','DMA2_CH4_5']

print('=== 完整中断向量表（%d 项）===' % len(NAMES))
vec = {}
for i, nm in enumerate(NAMES):
    v = u32(BASE + 4*i)
    vec[nm] = v
    mark = ''
    if v and (v & 1) and 0x08000000 <= v < 0x0800E000:
        mark = '-> file 0x%X' % foff(v & ~1)
    print('  [%2d] %-12s 0x%08X %s' % (i, nm, v, mark))

def dis(name, n=70):
    v = vec.get(name, 0)
    if not (v and (v & 1)):
        print('\n=== %s: 未实现 ===' % name); return
    start = v & ~1
    print('\n=== %s 处理程序 @0x%08X ===' % (name, start))
    cnt = 0
    for ins in md.disasm(data[foff(start):foff(start)+n*4], start):
        print('  0x%08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str))
        cnt += 1
        if cnt >= n: break

for nm in ['I2C1_EV', 'I2C1_ER']:
    dis(nm, 80)
