import EasyMCP2221

mcp = EasyMCP2221.Device()
print("MCP2221 trovato")

found = []

for addr in range(0x03, 0x78):
    try:
        mcp.I2C_read(addr, 1)
        found.append(addr)
    except Exception:
        pass

print("Dispositivi I2C trovati:", [hex(a) for a in found])
