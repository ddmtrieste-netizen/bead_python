# probe_mlx90393_mcp2221.py
import time
import EasyMCP2221
from EasyMCP2221 import exceptions

# Indirizzi plausibili.
# 0x10 viene dal vecchio codice C.
# 0x0C è default comune nelle librerie Adafruit.
# 0x18 compare in alcuni breakout.
CANDIDATE_ADDRS = [
    0x10,
    0x0C, 0x0D, 0x0E, 0x0F,
    0x18,
]

# Comandi MLX90393
CMD_NOP = 0x00
CMD_EX  = 0x80   # Exit: forza idle mode
CMD_RT  = 0xF0   # Reset
CMD_SM_ALL = 0x3F  # Start Measurement, zyxt = 1111
CMD_RM_ALL = 0x4F  # Read Measurement, zyxt = 1111


def s16(msb, lsb):
    """Converti due byte big-endian in signed int16."""
    v = (msb << 8) | lsb
    return v - 65536 if v & 0x8000 else v


def try_write(mcp, addr, data, label):
    try:
        mcp.I2C_write(addr, bytes(data), timeout_ms=50)
        print(f"[0x{addr:02X}] {label}: WRITE OK")
        return True
    except exceptions.NotAckError:
        print(f"[0x{addr:02X}] {label}: NACK")
        return False
    except Exception as e:
        print(f"[0x{addr:02X}] {label}: {type(e).__name__}: {e}")
        return False


def try_read(mcp, addr, n, label):
    try:
        data = mcp.I2C_read(addr, n, timeout_ms=100)
        print(f"[0x{addr:02X}] {label}: READ OK -> {data.hex(' ')}")
        return data
    except exceptions.NotAckError:
        print(f"[0x{addr:02X}] {label}: NACK")
        return None
    except Exception as e:
        print(f"[0x{addr:02X}] {label}: {type(e).__name__}: {e}")
        return None


def probe_addr(mcp, addr):
    print("\n" + "=" * 50)
    print(f"Testing address 0x{addr:02X}")

    # 1. NOP: comando innocuo. Se risponde, abbiamo già trovato qualcosa.
    if try_write(mcp, addr, [CMD_NOP], "NOP") is False:
        return False

    status = try_read(mcp, addr, 1, "status after NOP")
    if status is None:
        # Alcuni bridge/sensori possono non gradire read separato dopo NOP.
        # Continuiamo comunque con una sequenza reale.
        print(f"[0x{addr:02X}] NOP write ok, status read failed; continuing")

    # 2. EX: uscita da eventuale burst/wake mode. Non modifica registri.
    try_write(mcp, addr, [CMD_EX], "EX idle")
    time.sleep(0.01)
    try_read(mcp, addr, 1, "status after EX")

    # 3. RT: reset software del sensore. Non scrive flash.
    if not try_write(mcp, addr, [CMD_RT], "RT reset"):
        return False

    time.sleep(0.05)
    try_read(mcp, addr, 1, "status after RT")

    # 4. Misura completa: temperatura + X + Y + Z.
    if not try_write(mcp, addr, [CMD_SM_ALL], "SM all"):
        return False

    # Attesa conservativa: filtri/oversampling possono richiedere qualche ms.
    time.sleep(0.08)

    if not try_write(mcp, addr, [CMD_RM_ALL], "RM all"):
        return False

    data = try_read(mcp, addr, 9, "measurement")
    if data is None or len(data) < 9:
        return False

    status = data[0]
    t_raw = s16(data[1], data[2])
    x_raw = s16(data[3], data[4])
    y_raw = s16(data[5], data[6])
    z_raw = s16(data[7], data[8])

    print(f"[0x{addr:02X}] STATUS = 0x{status:02X}")
    print(f"[0x{addr:02X}] RAW: T={t_raw}, X={x_raw}, Y={y_raw}, Z={z_raw}")

    # Test fisico grezzo: valori tutti zero o tutti 0xFFFF sono sospetti.
    suspicious = (x_raw == y_raw == z_raw == 0) or (x_raw == y_raw == z_raw == -1)
    if suspicious:
        print(f"[0x{addr:02X}] WARNING: values look suspicious")
    else:
        print(f"[0x{addr:02X}] LIKELY MLX90393 FOUND")

    return True


def main():
    print("Opening MCP2221...")
    mcp = EasyMCP2221.Device()
    print("MCP2221 opened")

    # Frequenza bassa = più robusta. Non viene salvata in flash.
    try:
        mcp.I2C_speed(100000)
        print("I2C speed set to 100 kHz")
    except Exception as e:
        print(f"Could not set I2C speed: {type(e).__name__}: {e}")

    hits = []
    for addr in CANDIDATE_ADDRS:
        ok = probe_addr(mcp, addr)
        if ok:
            hits.append(addr)

    print("\n" + "=" * 50)
    print("Candidate hits:", [f"0x{a:02X}" for a in hits])

    if not hits:
        print("No MLX90393-like response found.")
        print("If C works, copy the exact I2C address and command sequence from the C file.")
    else:
        print("Try moving the magnet/sensor and rerun measurement on the best address.")


if __name__ == "__main__":
    main()
