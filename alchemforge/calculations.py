"""Core binding free energy calculations."""

from math import log

R_KCAL_PER_MOL_K = 1.98720425864083e-3


def binding_free_energy_from_kd(kd_molar: float, temperature_k: float = 298.15) -> float:
    """Return binding free energy (kcal/mol) from Kd in molar units.

    Uses the standard relation:
        ΔG = R * T * ln(Kd / 1 M)
    """
    if kd_molar <= 0:
        raise ValueError("Kd must be greater than 0.")
    if temperature_k <= 0:
        raise ValueError("Temperature must be greater than 0 K.")
    return R_KCAL_PER_MOL_K * temperature_k * log(kd_molar)
