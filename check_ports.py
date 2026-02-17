import serial.tools.list_ports
import time

print("--- RASTREAMENTO DE HARDWARE PHANTOM ---")
print("Procurando dispositivos conectados...\n")

ports = serial.tools.list_ports.comports()

if not ports:
    print("[ERRO] Nenhuma porta COM detectada!")
    print("Possíveis causas:")
    print("1. RP2350 não está plugado.")
    print("2. Cabo USB é apenas de carga (troque o cabo).")
    print("3. Firmware não está rodando (instale CircuitPython).")
else:
    for p in ports:
        print(f"🟢 PORTA:      {p.device}")
        print(f"   DESCRIÇÃO:  {p.description}")
        print(f"   HWID:       {p.hwid}")
        print("-" * 40)

print("\n[INSTRUÇÃO]")
print("Copie o NOME DA PORTA (ex: COM3, COM4) do seu dispositivo e")
print("coloque na variável 'target_port' na classe HardwareDriver.")
input("\nPressione ENTER para sair...")