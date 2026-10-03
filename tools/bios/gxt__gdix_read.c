/*=============================================================================
  gdix_read.c  --  用户态测试程序
  -----------------------------------------------------------------------------
  通过 DeviceIoControl 与 GdixSpbProbe.sys 通信，读取 Goodix 寄存器。

  用法：
      gdix_read.exe                 # 读默认地址（0x96F8 CFG_START + 0x4014 VER）
      gdix_read.exe 0x1800 32       # 读指定地址/长度
      gdix_read.exe --status        # 查询驱动状态

  依赖：
      GdixSpbProbe.sys 已加载，且创建了 \\.\GdixSpbProbe 符号链接。
      若符号链接不存在，程序会尝试用 SetupAPI 按设备接口查找。

  编译（MSVC x64）：
      cl /nologo /W4 /O2 gdix_read.c
=============================================================================*/

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* --- 与驱动一致的定义 --- */
#define IOCTL_GDIX_READ_REG \
    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define IOCTL_GDIX_STATUS \
    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define MAX_XFER 32

typedef struct _GDIX_READ_REQ {
    USHORT Address;
    USHORT Length;
} GDIX_READ_REQ;

typedef struct _GDIX_READ_RSP {
    LONG  Status;
    ULONG BytesReturned;
    UCHAR Data[MAX_XFER];
} GDIX_READ_RSP;

/* --- 已知寄存器 --- */
typedef struct {
    USHORT      addr;
    const char *name;
    USHORT      len;
} REG_INFO;

static const REG_INFO g_regs[] = {
    { 0x96F8, "CFG_START_ADDR",  3  },
    { 0x4014, "VER_ADDR",        32 },
    { 0x1800, "PARAM_A (0x1800)", 27 },
    { 0x3800, "PARAM_B (0x3800)", 8  },
};
#define N_REGS (sizeof(g_regs) / sizeof(g_regs[0]))

/*=============================================================================
  打开设备
=============================================================================*/
static HANDLE OpenProbe(void)
{
    HANDLE h;
    const char *paths[] = {
        "\\\\.\\GdixSpbProbe",
        "\\\\.\\Global\\GdixSpbProbe",
        NULL
    };
    int i;

    for (i = 0; paths[i] != NULL; i++) {
        h = CreateFileA(
                paths[i],
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                NULL,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                NULL);
        if (h != INVALID_HANDLE_VALUE) {
            printf("[+] opened %s\n", paths[i]);
            return h;
        }
    }

    printf("[!] cannot open device. LastError = %lu\n", GetLastError());
    printf("    -> driver not loaded? run: sc start GdixSpbProbe\n");
    return INVALID_HANDLE_VALUE;
}

/*=============================================================================
  读一个寄存器
=============================================================================*/
static int ReadReg(HANDLE h, USHORT addr, USHORT len, const char *name)
{
    GDIX_READ_REQ req;
    GDIX_READ_RSP rsp;
    DWORD         bytes = 0;
    BOOL          ok;
    USHORT        i;

    if (len == 0 || len > MAX_XFER) {
        printf("[!] bad length %u\n", len);
        return -1;
    }

    req.Address = addr;
    req.Length  = len;
    ZeroMemory(&rsp, sizeof(rsp));

    printf("\n--- read 0x%04X (%s), len=%u ---\n", addr, name ? name : "?", len);

    ok = DeviceIoControl(
            h,
            IOCTL_GDIX_READ_REG,
            &req, sizeof(req),
            &rsp, sizeof(rsp),
            &bytes,
            NULL);

    if (!ok) {
        DWORD err = GetLastError();
        printf("[!] DeviceIoControl failed. err=%lu (0x%lX)\n", err, err);
        switch (err) {
        case 5:    printf("    ACCESS_DENIED -> address not whitelisted, or need admin\n"); break;
        case 87:   printf("    INVALID_PARAMETER -> check length\n"); break;
        case 1167: printf("    DEVICE_NOT_CONNECTED -> SPB target not connected\n"); break;
        default:   break;
        }
        return -1;
    }

    printf("[+] status=0x%08lX  bytes=%lu\n", (unsigned long)rsp.Status,
           (unsigned long)rsp.BytesReturned);
    printf("    data: ");
    for (i = 0; i < len; i++) {
        printf("%02X ", rsp.Data[i]);
        if ((i + 1) % 16 == 0 && i + 1 < len) printf("\n          ");
    }
    printf("\n");

    /* 可打印字符串猜测 */
    if (len >= 4) {
        int printable = 1;
        for (i = 0; i < len; i++) {
            if (rsp.Data[i] != 0 &&
                (rsp.Data[i] < 0x20 || rsp.Data[i] > 0x7E)) {
                printable = 0;
                break;
            }
        }
        if (printable) {
            printf("    ascii: \"");
            for (i = 0; i < len && rsp.Data[i] != 0; i++) putchar(rsp.Data[i]);
            printf("\"\n");
        }
    }

    return 0;
}

/*=============================================================================
  main
=============================================================================*/
int main(int argc, char **argv)
{
    HANDLE h;
    int    i;
    int    rc = 0;

    printf("========================================\n");
    printf(" Goodix GT7868Q SPB Read-Only Probe\n");
    printf(" 只读测试 —— 不写任何寄存器\n");
    printf("========================================\n");

    h = OpenProbe();
    if (h == INVALID_HANDLE_VALUE) {
        return 1;
    }

    /* 只查状态 */
    if (argc >= 2 && _stricmp(argv[1], "--status") == 0) {
        GDIX_READ_RSP rsp;
        DWORD bytes = 0;
        ZeroMemory(&rsp, sizeof(rsp));
        if (DeviceIoControl(h, IOCTL_GDIX_STATUS, NULL, 0,
                            &rsp, sizeof(rsp), &bytes, NULL)) {
            printf("[+] driver alive. total_xfers=%lu failed=%u\n",
                   (unsigned long)rsp.BytesReturned, rsp.Data[0]);
        } else {
            printf("[!] status query failed. err=%lu\n", GetLastError());
        }
        CloseHandle(h);
        return 0;
    }

    /* 指定地址 */
    if (argc >= 3) {
        USHORT addr = (USHORT)strtoul(argv[1], NULL, 0);
        USHORT len  = (USHORT)strtoul(argv[2], NULL, 0);
        rc = ReadReg(h, addr, len, "user-specified");
        CloseHandle(h);
        return rc == 0 ? 0 : 1;
    }

    /* 默认：按顺序读所有已知寄存器 */
    for (i = 0; i < (int)N_REGS; i++) {
        if (ReadReg(h, g_regs[i].addr, g_regs[i].len, g_regs[i].name) != 0) {
            rc = 1;
        }
        /* ★ 与驱动内的 500 ms 节流配合，这里再加一点间隔，绝不抢总线 */
        Sleep(300);
    }

    printf("\n=== done (rc=%d) ===\n", rc);
    CloseHandle(h);
    return rc;
}
