# AlchemForge

AlchemForge is a PyQt5 desktop application for setting up alchemical free-energy workflows, including residue-alchemical FEP calculations.

## Requirements

- Python 3.10 or newer
- GROMACS
- AmberTools, including `tleap`
- ACPYPE
- PMX

On an HPC system, load the site-specific GROMACS and AmberTools modules before running the workflow. The application does not install system-level GROMACS or AmberTools packages.

## Installation

Create and activate a virtual environment:

```bash
python3 -m venv .alchemforge_env
source .alchemforge_env/bin/activate
python -m pip install --upgrade pip wheel
```

Install AlchemForge in editable mode:

```bash
python -m pip install -e .
```

Install PMX:

```bash
git clone https://github.com/deGrootLab/pmx.git
cd pmx
python -m pip install --no-build-isolation .
cd ..
```

Install ACPYPE in the same environment if it is not provided by your system:

```bash
python -m pip install acpype
```

## Run

```bash
source .alchemforge_env/bin/activate
alchemforge
```

The desktop application provides project management, residue mutation setup, simulation settings, task creation, SLURM submission, and job monitoring.

## ResAlchemFEP Workflow

The generated task workflow consists of:

1. Local ligand parameterization with ACPYPE.
2. Local system preparation with GROMACS and PMX.
3. FEP simulation submitted to SLURM with GPU resources.

Task files and logs are written under the configured working directory. The workflow uses a task-local `mdp` directory containing `ions.mdp` and `fep_base.mdp`.

## Development

Run the available tests with:

```bash
python -m pytest
```

Check Python syntax with:

```bash
python -m py_compile src/alchemforge/main.py
```

## License

See [LICENSE](LICENSE).








