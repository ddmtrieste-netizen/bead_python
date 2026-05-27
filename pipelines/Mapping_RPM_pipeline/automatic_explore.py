import subprocess

print("Avvio pipeline... \n")
# Ciclo da 1 a 56 (incluso)
for speed in range(1, 57):
    print(f"\n SPEED = {speed}")
    
    # Esegue il comando e si blocca finché non chiudi la finestra manualmente
    subprocess.run([
        "python3", 
        "pipelines/Mapping_RPM_pipeline/graphs_RPM.py", 
        "--mode", "explore", 
        "--speed", str(speed)
    ])