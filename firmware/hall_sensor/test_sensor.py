# read_mlx90393_mcp2221_repeated_start.py

import time
import EasyMCP2221
from EasyMCP2221 import exceptions

ADDR = 0x10

CMD_SM_ALL = 0x3F
CMD_RM_ALL = 0x4F


def s16(msb, lsb):
    v = (msb << 8) | lsb
    return v - 65536 if v & 0x8000 else v


def i2c_cmd_read(mcp, addr, cmd, nbytes):
    """
    Esegue una transazione I2C combinata:
    START + addr(W) + cmd + REPEATED START + addr(R) + nbytes + STOP

    È l'equivalente concettuale del blocco ioctl I2C_RDWR usato nel C.
    """
    mcp.I2C_write(addr, bytes([cmd]), kind="nonstop")
    data = mcp.I2C_read(addr, nbytes, kind="restart")
    return data


def main():
    mcp = EasyMCP2221.Device()
    print("MCP2221 opened")

    try:
        mcp.I2C_speed(100000)
        print("I2C speed set to 100 kHz")
    except Exception as e:
        print(f"Could not set speed: {type(e).__name__}: {e}")

    # 1. Start single measurement: comando 0x3f + lettura status
    try:
        status = i2c_cmd_read(mcp, ADDR, CMD_SM_ALL, 1)[0]
        print(f"SM status = 0x{status:02X}")
    except Exception as e:
        print(f"SM failed: {type(e).__name__}: {e}")
        return

    if not (status & 0x20):
        print("WARNING: status bit 0x20 not set after SM")

    # Il C aspetta 202300 microsecondi.
    time.sleep(0.203)

    # 2. Read measurement: comando 0x4f + lettura 9 byte
    try:
        data = i2c_cmd_read(mcp, ADDR, CMD_RM_ALL, 9)
    except Exception as e:
        print(f"RM failed: {type(e).__name__}: {e}")
        return

    print("raw bytes:", data.hex(" "))

    status = data[0]
    t_raw = (data[1] << 8) | data[2]
    x_raw = s16(data[3], data[4])
    y_raw = s16(data[5], data[6])
    z_raw = s16(data[7], data[8])

    temperature = t_raw / 45.2 + (25 - 46244 / 45.2)

    print(f"RM status = 0x{status:02X}")
    print(f"T_raw = {t_raw}")
    print(f"X_raw = {x_raw}")
    print(f"Y_raw = {y_raw}")
    print(f"Z_raw = {z_raw}")
    print(f"T_C   = {temperature:.2f}")


if __name__ == "__main__":
    main()
