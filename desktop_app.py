"""Minimal desktop app for binding free energy calculation."""

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from alchemforge import binding_free_energy_from_kd


class BindingFreeEnergyApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AlchemForge - Binding Free Energy")
        self.root.resizable(False, False)

        frame = ttk.Frame(root, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Kd (M):").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.kd_var = tk.StringVar(value="1e-6")
        ttk.Entry(frame, textvariable=self.kd_var, width=18).grid(row=0, column=1, pady=4)

        ttk.Label(frame, text="Temperature (K):").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self.temp_var = tk.StringVar(value="298.15")
        ttk.Entry(frame, textvariable=self.temp_var, width=18).grid(row=1, column=1, pady=4)

        ttk.Button(frame, text="Calculate", command=self.calculate).grid(
            row=2, column=0, columnspan=2, pady=(10, 4)
        )

        self.result_var = tk.StringVar(value="ΔG =")
        ttk.Label(frame, textvariable=self.result_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

    def calculate(self) -> None:
        try:
            kd = float(self.kd_var.get().strip())
            temperature = float(self.temp_var.get().strip())
            dg = binding_free_energy_from_kd(kd, temperature)
            self.result_var.set(f"ΔG = {dg:.4f} kcal/mol")
        except ValueError as exc:
            self.result_var.set("ΔG =")
            messagebox.showerror("Input error", str(exc))


def main() -> None:
    root = tk.Tk()
    BindingFreeEnergyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
