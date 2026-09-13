import unittest
from unittest.mock import patch

from desktop_app import BindingFreeEnergyApp


class _FakeVar:
    def __init__(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class DesktopAppTests(unittest.TestCase):
    def _build_app(self, kd_value: str, temp_value: str) -> BindingFreeEnergyApp:
        app = BindingFreeEnergyApp.__new__(BindingFreeEnergyApp)
        app.kd_var = _FakeVar(kd_value)
        app.temp_var = _FakeVar(temp_value)
        app.result_var = _FakeVar("ΔG =")
        return app

    def test_calculate_sets_result_text_for_valid_values(self):
        app = self._build_app("1e-6", "298.15")
        with patch("desktop_app.messagebox.showerror") as showerror:
            app.calculate()
        self.assertRegex(app.result_var.get(), r"^ΔG = -?\d+\.\d{4} kcal/mol$")
        showerror.assert_not_called()

    def test_calculate_shows_field_specific_error_for_non_numeric_input(self):
        app = self._build_app("abc", "298.15")
        with patch("desktop_app.messagebox.showerror") as showerror:
            app.calculate()
        self.assertEqual(app.result_var.get(), "ΔG =")
        showerror.assert_called_once_with("Input error", "Kd must be a numeric value.")

    def test_calculate_shows_field_specific_error_for_non_positive_input(self):
        app = self._build_app("0", "298.15")
        with patch("desktop_app.messagebox.showerror") as showerror:
            app.calculate()
        self.assertEqual(app.result_var.get(), "ΔG =")
        showerror.assert_called_once_with("Input error", "Kd must be greater than 0.")

    def test_calculate_shows_temperature_error_for_non_positive_input(self):
        app = self._build_app("1e-6", "-1")
        with patch("desktop_app.messagebox.showerror") as showerror:
            app.calculate()
        self.assertEqual(app.result_var.get(), "ΔG =")
        showerror.assert_called_once_with(
            "Input error", "Temperature must be greater than 0."
        )


if __name__ == "__main__":
    unittest.main()
