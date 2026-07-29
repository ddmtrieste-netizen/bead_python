import serial
import threading

# Cosmetics

ROSSO   = "\033[31m"
VERDE   = "\033[32m"
GIALLO  = "\033[33m"
BLU     = "\033[34m"
RESET   = "\033[0m"
VIOLA   = "\033[35m"

# Sostituisci con la tua porta e il tuo baud rate dell'Arduino
SERIAL_PORT = '/dev/ttyACM1'
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
    try:
        # Inizializzazione della porta seriale
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"{VERDE}Connesso a {SERIAL_PORT} a {BAUD_RATE} baud.{RESET}")
        print("Digita un comando e premi INVIO. Scrivi 'exit' per uscire.\n")
        
        # Avvia il thread per la lettura continua
        read_thread = threading.Thread(target=read_from_arduino, args=(ser,), daemon=True)
        read_thread.start()
        
        # Loop principale per prendere l'input del terminale in maniera continua
        while True:
            # Prende l'input dall'utente
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
    except KeyboardInterrupt:
        print("\nProgramma interrotto dall'utente.")
    finally:
        # Assicura la chiusura della porta alla fine
        if 'ser' in locals() and ser.is_open:
            ser.close()
        print("Porta seriale chiusa.")

if __name__ == "__main__":
    main()
