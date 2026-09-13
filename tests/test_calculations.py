import math
import unittest

from alchemforge.calculations import binding_free_energy_from_kd


class BindingFreeEnergyTests(unittest.TestCase):
    def test_one_molar_has_zero_delta_g(self):
        self.assertAlmostEqual(binding_free_energy_from_kd(1.0), 0.0, places=10)

    def test_submicromolar_is_negative(self):
        self.assertLess(binding_free_energy_from_kd(1e-9), 0.0)

    def test_formula_matches_expected_value(self):
        expected = 1.98720425864083e-3 * 300.0 * math.log(1e-6)
        self.assertAlmostEqual(binding_free_energy_from_kd(1e-6, 300.0), expected, places=12)

    def test_invalid_kd_raises(self):
        with self.assertRaisesRegex(ValueError, "Kd must be greater than 0"):
            binding_free_energy_from_kd(0.0)

    def test_invalid_temperature_raises(self):
        with self.assertRaisesRegex(ValueError, "Temperature must be greater than 0 K"):
            binding_free_energy_from_kd(1e-6, 0.0)


if __name__ == "__main__":
    unittest.main()
