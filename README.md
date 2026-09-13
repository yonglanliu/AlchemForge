# AlchemForge

AlchemForge now includes a minimal desktop interface for binding free energy calculation.

## What it does

Given:
- **Kd** in molar units (M)
- **Temperature** in Kelvin (K)

it computes binding free energy using:

\[
\Delta G = R \cdot T \cdot \ln(K_d / 1\text{ M})
\]

with output in **kcal/mol**.

## Run desktop app

```bash
# from the repository root
python desktop_app.py
```

## Run tests

```bash
# from the repository root
python -m unittest discover -s tests -v
```