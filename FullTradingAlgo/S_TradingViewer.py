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
        self.fig, (self.ax_main, self.ax_rsi, self.ax_hammers) = plt.subplots(
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

        self.ax_main.clear()
        self.ax_rsi.clear()
        self.ax_hammers.clear()

        # Tracer close
        self.ax_main.plot(df.index, df["close"], label="Close", color="blue", linewidth=1)
        #self.ax_main.plot(df.index, df["close_4h_HA"], label="Close_4H_HA", color="red", linewidth=1)

        # Tracer high et low en étoiles (red/noir)
        self.ax_main.scatter(df.index, df["high"], marker="*", color="red", label="High *", s=40)
        self.ax_main.scatter(df.index, df["low"], marker="*", color="black", label="Low *", s=40)

        # Toutes colonnes EMA
        ema_cols = [col for col in df.columns if re.match(r"ema\d+", col, re.IGNORECASE)]
        colors_ema = ['orange', 'green', 'magenta', 'cyan', 'purple', 'brown']
        for i, col in enumerate(sorted(ema_cols)):
            self.ax_main.plot(df.index, df[col], label=col.upper(), color=colors_ema[i % len(colors_ema)], linewidth=1)

        self.ax_main.set_title(f"📈 Données : {selected_file}")
        self.ax_main.set_ylabel("Prix")
        self.ax_main.legend()
        self.ax_main.grid(True)

        # RSI subplot
        rsi_cols = [col for col in df.columns if "rsi" in col.lower()]
        colors_rsi = ['purple', 'blue', 'green', 'magenta', 'brown', 'cyan']
        if rsi_cols:
            for i, col in enumerate(sorted(rsi_cols)):
                self.ax_rsi.plot(df.index, df[col], label=col.upper(), color=colors_rsi[i % len(colors_rsi)])
            self.ax_rsi.axhline(70, color='red', linestyle='--', linewidth=0.8)
            self.ax_rsi.axhline(30, color='green', linestyle='--', linewidth=0.8)
            self.ax_rsi.set_ylabel("RSI")
            self.ax_rsi.set_xlabel("Temps")
            self.ax_rsi.set_ylim(0, 100)  # Fixe l'axe Y entre 0 et 40
            self.ax_rsi.legend()
            self.ax_rsi.grid(True)
        else:
            self.ax_rsi.text(0.5, 0.5, "Pas de RSI disponible", ha='center', va='center',
                             transform=self.ax_rsi.transAxes)
            self.ax_rsi.set_xticks([])
            self.ax_rsi.set_yticks([])

        # Hammers subplot
        if "jap_hammers_5m" in df.columns:
            colors = df["jap_hammers_5m"].map({1: "green", -1: "red", 0: "gray"})
            self.ax_hammers.scatter(df.index, df["jap_hammers_5m"], c=colors, label="Hammers 5m", s=10)
            self.ax_hammers.set_ylabel("Hammers")
            self.ax_hammers.set_yticks([-1, 0, 1])
            self.ax_hammers.grid(True)
            self.ax_hammers.legend()
        else:
            self.ax_hammers.text(0.5, 0.5, "Pas de Hammers", ha='center', va='center',
                                 transform=self.ax_hammers.transAxes)
            self.ax_hammers.set_xticks([])
            self.ax_hammers.set_yticks([])

        self.fig.tight_layout()
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x700")
    app = PandaViewerApp(root)
    root.mainloop()
