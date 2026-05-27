# Cosa devo fare;
# 1. Esplorazione visiva dei grafici
# 2. Estrarre frequenza della bead togliendo transiente sporco
# 3. Dedurre frequenza motore da comando imposto e conversione
# plot simil Dickson

import argparse
import sys
import csv
from numpy import fft
import numpy as np

import matplotlib.pyplot as plt
from pathlib import Path


def load_csv(filename):
    t = []
    x = []
    y = []
    radius = []
    area = []

    with open(filename, "r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            t.append(float(row["t"]))
            x.append(float(row["x"]))
            y.append(float(row["y"]))
            radius.append(float(row["radius"]))
            area.append(float(row["area"]))

    return t, x, y, radius, area


def apply_screen_scale(scale):
    plt.rcParams.update({
        "font.size": 14 * scale,
        "axes.titlesize": 18 * scale,
        "axes.labelsize": 16 * scale,
        "xtick.labelsize": 13 * scale,
        "ytick.labelsize": 13 * scale,
        "legend.fontsize": 13 * scale,
        "lines.linewidth": 2.0 * scale,
        "grid.linewidth": 0.8 * scale,
    })


def main():
    parser = argparse.ArgumentParser(description="Explore data and produce RPM - RPM plot.")
    parser.add_argument("--mode", type=str, default="PRODUCE", help="Select working mode.")
    parser.add_argument("--speed", type=int, default=None, help="Select speed to plot.")
    parser.add_argument("--scale", type=float, default=1.6, help="Visual scale factor.")

    args = parser.parse_args()

    if args.mode.lower() == "explore":
        explore = True
    elif args.mode.lower() == "produce":
        explore = False
    else:
        print("Not valid mode.\n  Usage: \"explore\" to see the plots relative to \"speed\" ")
        sys.exit()

    apply_screen_scale(args.scale)

    if explore:
        # Produce un singolo plot di una run singola
        if args.speed is None: args.speed = 5

        args.input = f"./data/mapping_RPM_submerged/mapping_RMP/{args.speed}_RPM.csv"
        t, x, y, radius, area = load_csv(args.input)
        if len(t) == 0:
            print("No data found.")
            return

        plt.figure(figsize=(14, 8))

        plt.plot(x, y)
        plt.xlabel("x [px]")
        plt.ylabel("y [px]")
        plt.axis("equal")
        plt.grid(True)
        plt.title("Bead trajectory")

        plt.figure(figsize=(14, 8))

        plt.plot(t, x, label="x")
        plt.plot(t, y, label="y")
        plt.xlabel("t [s]")
        plt.ylabel("position [px]")
        plt.grid(True)
        plt.legend()
        plt.title("Position vs time")

        plt.show()

    else:

        # Calcola e plotta Dickson like plot
        if args.speed is None:
            args.input = Path("./data/mapping_RPM_submerged/mapping_RMP/")
            for file_path in args.input.glob("*.csv"):
                pass
        else:
            args.input = f"./data/mapping_RPM_submerged/mapping_RMP/{args.speed}_RPM.csv"
            file_path = args.input
            t, x, y, radius, area = load_csv(file_path)
            if len(t) == 0:
                print(f"No data found for {file_path}.")
                sys.exit()

            N = len(t)
            if  N % 2 == 1:
                x = x[0:N - 2]
                t = t[0:N - 2]
            dt = t[2] - t[1]
            X_f = fft.fft( np.array(x) - np.mean(x) )
            X_mod = fft.fftshift(np.abs(X_f))
            X_mod  = X_mod[N//2 : N - 1]
            
            fff = np.arange(1, N//2, 1) / (N * dt)
                
            freq_max = fff[np.argmax(X_mod)]

            print(f"il massimo e' {freq_max} Hz  /  {freq_max*60} RPM")

            plt.figure(figsize=(14, 8))

            plt.plot(fff, X_mod)
            plt.xlabel("freq [1/s]")
            plt.ylabel("X_f")
            plt.grid(True)
            plt.title("Bead trajectory")

            plt.show()
        return
            



if __name__ == "__main__":
    main()