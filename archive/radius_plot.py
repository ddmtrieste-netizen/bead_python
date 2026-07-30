import pandas as pd
import matplotlib.pyplot as plt

data = pd.read_csv("data/processed/track_20260526_175614.csv")
plt.rcParams.update({"font.size": 24})
plt.figure(figsize=(56, 32))
plt.plot(data["t"], data["radius"])
plt.show()

print(data["area"][50])
