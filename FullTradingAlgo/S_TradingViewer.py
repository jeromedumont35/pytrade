import os
import pickle
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import pandas as pd
import re

PANDA_DIR = "panda"

class PandaViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📊 Visualiseur de données Panda")

        self.combo = ttk.Combobox(root, state="readonly", width=80)
        self.combo.pack(side="top", fill="x", padx=10, pady=10)
        self.combo.bind("<<ComboboxSelected>>", self.display_chart)

        self.files = [f for f in os.listdir(PANDA_DIR) if f.endswith(".panda")]
        self.combo['values'] = self.files

        self.frame_plot = tk.Frame(root)
        self.frame_plot.pack(side="top", fill="both", expand=True)

        # Figure avec 3 axes : prix, RSI, hammers
        self.fig, (self.ax_p1, self.ax_p2, self.ax_p3) = plt.subplots(
            3, 1, figsize=(10, 9), gridspec_kw={'height_ratios': [3, 1, 0.7]}, sharex=True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame_plot)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self.frame_plot)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.frame_plot.rowconfigure(0, weight=1)
        self.frame_plot.columnconfigure(0, weight=1)

    def display_chart(self, event):
        selected_file = self.combo.get()
        filepath = os.path.join(PANDA_DIR, selected_file)

        with open(filepath, "rb") as f:
            df = pickle.load(f)

        self.ax_p1.clear()
        self.ax_p2.clear()
        self.ax_p3.clear()

        # Axe secondaire pour BTC_
        self.ax_p1_btc = self.ax_p1.twinx()

        # Définir les codes couleurs abrégés valides
        valid_colors = {'b', 'g', 'r', 'c', 'm', 'y', 'k', 'w'}

        # --- AXE GAUCHE (classique) ---
        P1_cols = [col for col in df.columns if col.endswith("_P1") and not col.startswith("BTC_")]

        for col in P1_cols:
            if col[-5] == '_' and col[-6] == '_':  # "__x_P1"
                color_code = col[-4]
                if color_code in valid_colors:
                    self.ax_p1.plot(df.index, df[col], label=col, color=color_code, linewidth=1)
            elif col[-5] == '_' and col[-6] == '*':  # "*_x_P1"
                color_code = col[-4]
                if color_code in valid_colors:
                    self.ax_p1.scatter(df.index, df[col], marker="*", color=color_code, label=col, s=40)

        self.ax_p1.set_ylabel("Prix")
        self.ax_p1.legend(loc="upper left")
        self.ax_p1.grid(True)

        # --- AXE DROIT (BTC_) ---
        P1_btc_cols = [col for col in df.columns if col.startswith("BTC_") and col.endswith("_P1")]

        for col in P1_btc_cols:
            if col[-5] == '_' and col[-6] == '_':  # "__x_P1"
                color_code = col[-4]
                if color_code in valid_colors:
                    self.ax_p1_btc.plot(df.index, df[col], label=col, color=color_code, linewidth=1, linestyle="--")
            elif col[-5] == '_' and col[-6] == '*':  # "*_x_P1"
                color_code = col[-4]
                if color_code in valid_colors:
                    self.ax_p1_btc.scatter(df.index, df[col], marker="*", color=color_code, label=col, s=40)

        self.ax_p1_btc.set_ylabel("Prix BTC")
        self.ax_p1_btc.legend(loc="upper right")

        # Titre de l'axe principal
        self.ax_p1.set_title(f"📈 Données : {selected_file}")

        # --- RSI subplot ---
        rsi_cols = [col for col in df.columns if "rsi" in col.lower()]
        colors_rsi = ['purple', 'blue', 'green', 'magenta', 'brown', 'cyan']
        if rsi_cols:
            for i, col in enumerate(sorted(rsi_cols)):
                self.ax_p2.plot(df.index, df[col], label=col.upper(), color=colors_rsi[i % len(colors_rsi)])
            self.ax_p2.axhline(70, color='red', linestyle='--', linewidth=0.8)
            self.ax_p2.axhline(30, color='green', linestyle='--', linewidth=0.8)
            self.ax_p2.set_ylabel("RSI")
            self.ax_p2.set_xlabel("Temps")
            self.ax_p2.set_ylim(0, 100)
            self.ax_p2.legend()
            self.ax_p2.grid(True)
        else:
            self.ax_p2.text(0.5, 0.5, "Pas de RSI disponible", ha='center', va='center',
                            transform=self.ax_p2.transAxes)
            self.ax_p2.set_xticks([])
            self.ax_p2.set_yticks([])

        # --- Hammers subplot ---
        P3_cols = [col for col in df.columns if "_P3" in col]
        if P3_cols:
            for col in P3_cols:
                self.ax_p3.scatter(df.index, df[col], label=col.upper(), s=10)
            self.ax_p3.set_ylabel("detection")
            self.ax_p3.set_yticks([-1, 0, 1])
            self.ax_p3.grid(True)
            self.ax_p3.legend()
        else:
            self.ax_p3.text(0.5, 0.5, "Pas de Hammers", ha='center', va='center',
                            transform=self.ax_p3.transAxes)
            self.ax_p3.set_xticks([])
            self.ax_p3.set_yticks([])

        self.fig.tight_layout()
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x700")
    app = PandaViewerApp(root)
    root.mainloop()
