"""Minimal desktop app for binding free energy calculation."""

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter import messagebox
except ModuleNotFoundError:  # pragma: no cover - exercised in headless environments
    tk = None
    ttk = None

    class _MessageBox:
        @staticmethod
        def showerror(_title: str, _message: str) -> None:
            return None

    messagebox = _MessageBox()

from alchemforge import binding_free_energy_from_kd


class BindingFreeEnergyApp:
    def __init__(self, root) -> None:
        if tk is None or ttk is None:
            raise RuntimeError("tkinter is required to run the desktop app.")
        self.root = root
        self.root.title("AlchemForge - Binding Free Energy")
        self.root.resizable(False, False)

        frame = ttk.Frame(root, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Kd (M):").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.kd_var = tk.StringVar(value="1e-6")
        self.kd_entry = ttk.Entry(frame, textvariable=self.kd_var, width=18)
        self.kd_entry.grid(row=0, column=1, pady=4)

        ttk.Label(frame, text="Temperature (K):").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self.temp_var = tk.StringVar(value="298.15")
        self.temp_entry = ttk.Entry(frame, textvariable=self.temp_var, width=18)
        self.temp_entry.grid(row=1, column=1, pady=4)

        ttk.Button(frame, text="Calculate", command=self.calculate).grid(
            row=2, column=0, columnspan=2, pady=(10, 4)
        )

        self.result_var = tk.StringVar(value="ΔG =")
        ttk.Label(frame, textvariable=self.result_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        self.kd_entry.bind("<Return>", self.calculate)
        self.temp_entry.bind("<Return>", self.calculate)
        self.kd_entry.focus_set()

    def calculate(self, _event=None) -> None:
        try:
            kd = self._parse_positive_float(self.kd_var.get(), "Kd")
            temperature = self._parse_positive_float(self.temp_var.get(), "Temperature")
        except ValueError as exc:
            self.result_var.set("ΔG =")
            messagebox.showerror("Input error", str(exc))
            return

        try:
            dg = binding_free_energy_from_kd(kd, temperature)
        except ValueError as exc:
            self.result_var.set("ΔG =")
            messagebox.showerror("Input error", str(exc))
            return
        self.result_var.set(f"ΔG = {dg:.4f} kcal/mol")

    @staticmethod
    def _parse_positive_float(raw_value: str, field_name: str) -> float:
        value_text = raw_value.strip()
        try:
            value = float(value_text)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a numeric value.") from exc
        if value <= 0:
            raise ValueError(f"{field_name} must be greater than 0.")
        return value


def main() -> None:
    if tk is None:
        raise RuntimeError("tkinter is required to run the desktop app.")
    try:
        root = tk.Tk()
    except Exception as exc:
        raise RuntimeError(
            "Unable to initialize Tk desktop UI (display may be unavailable)."
        ) from exc
    BindingFreeEnergyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
