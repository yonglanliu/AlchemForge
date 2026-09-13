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
cd /home/runner/work/AlchemForge/AlchemForge
python desktop_app.py
```

## Run tests

```bash
cd /home/runner/work/AlchemForge/AlchemForge
python -m unittest discover -s tests -v
```