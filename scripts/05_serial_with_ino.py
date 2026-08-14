import serial
import threading
import argparse
import time
import sys

# Cosmetics

ROSSO   = "\033[31m"
VERDE   = "\033[32m"
GIALLO  = "\033[33m"
BLU     = "\033[34m"
RESET   = "\033[0m"
VIOLA   = "\033[35m"

# Sostituisci con la tua porta e il tuo baud rate dell'Arduino
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600

def read_from_arduino(ser):
    """Funzione che gira in un thread separato per leggere continuamente dall'Arduino."""
    while ser.is_open:
        try:
            if ser.in_waiting > 0:
                # Legge la linea, la decodifica e rimuove gli spazi bianchi
                data = ser.readline().decode('utf-8', errors='ignore').strip()
                if data:
                    print(f"{VIOLA}\n[Arduino]:{RESET} {data}")
                    # Ristampa il cursore di input per pulizia visiva
                    print("Inserisci comando > ", end="", flush=True)
        except Exception as e:
            print(f"\nErrore di lettura: {e}")
            break

def main():
    parser = argparse.ArgumentParser(description="Parser.")
    parser.add_argument("--status", type=int, default=0, help="Camera index.")

    args = parser.parse_args()
    print(args.status)

    try:
        # Inizializzazione della porta seriale
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"{VERDE}Connesso a {SERIAL_PORT} a {BAUD_RATE} baud.{RESET}")
        print("Digita un comando e premi INVIO. Scrivi 'exit' per uscire.\n")
        
        # Avvia il thread per la lettura continua
        read_thread = threading.Thread(target=read_from_arduino, args=(ser,), daemon=True)
        read_thread.start()
        
        # Loop principale per prendere l'input del terminale in maniera continua

        # user_input = "exit"
        while True:
            # Prende l'input dall'utente
            if args.status == 1:
                tttt = "40"  + "\n"
                ser.write(tttt.encode('utf-8'))
                uuuu = "status" +  "\n"
                ser.write(uuuu.encode('utf-8'))
                # args.status = 0
                time.sleep(0.002)
                break
            else:
                user_input = input("Inserisci comando > ")
            
            # Condizione di uscita
            if user_input.lower() == 'exit':
                print("Chiusura in corso...")
                break
                
            # Invia il comando all'Arduino aggiungendo il carattere di Nuova Linea (\n)
            if user_input:
                command = user_input + "\n"
                ser.write(command.encode('utf-8'))
                
    except serial.SerialException as e:
        print(f"Errore di connessione seriale: {e}")
        print(f"{GIALLO}[DEBUG]{RESET} Try SERIAL_PORT = /dev/ttyACM0 or /dev/ttyACM0")
    except KeyboardInterrupt:
        print("\nProgramma interrotto dall'utente.")
    finally:
        # Assicura la chiusura della porta alla fine
        if 'ser' in locals() and ser.is_open:
            ser.close()
        print("Porta seriale chiusa.")

if __name__ == "__main__":
    main()
