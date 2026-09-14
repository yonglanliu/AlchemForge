# AlchemForge Installation

This setup uses Python 3.12 with Mamba for the scientific stack and keeps the HPC-provided GROMACS build separate.

## 1. Protect currently running SLURM jobs

If running SLURM jobs still use an older environment, do not rename, delete, or modify that environment while those jobs are active.

Deactivating the environment in your current shell does not affect already-running SLURM jobs.

## 2. Create the new Python 3.12 environment

From the AlchemForge project directory:

```bash
cd /vf/users/liuy48/AlchemForge

mamba env create     -p /vf/users/liuy48/conda/envs/.alchemforge     -f environment.yml
```

Activate it:

```bash
conda activate /vf/users/liuy48/conda/envs/.alchemforge
```

Verify:

```bash
which python
python --version
```

Expected:

```text
Python 3.12.x
```

## 3. CUDA

The environment installs:

```text
cuda-toolkit=12.6
```

The NVIDIA driver remains system-provided by the HPC cluster. Do not install your own NVIDIA kernel driver.

The tested node has:

```text
Tesla P100-PCIE-16GB
Driver 580.173.02
```

Because P100 is Pascal, keep CUDA on 12.x rather than CUDA 13.

Check:

```bash
nvcc --version
nvidia-smi --query-gpu=name,driver_version --format=csv
```

SLURM may place jobs on different GPU models, so CUDA 12.6 is used as a broadly compatible choice when P100 nodes remain possible.

## 4. Install AlchemForge

From the repository root:

```bash
cd /vf/users/liuy48/AlchemForge
python -m pip install -e .
```

Verify:

```bash
python -c "import alchemforge; print(alchemforge.__file__)"
```

## 5. Install PMX

PMX is installed separately because its packaging and C extension are older.

If the PMX source already exists:

```bash
cd /vf/users/liuy48/AlchemForge/pmx
```

In `setup.py`, remove the old setuptools pin if present:

```python
setup_requires=["setuptools~=46.0.0"],
```

Then install PMX using GNU17 to avoid the C23 `bool` conflict:

```bash
CFLAGS="-std=gnu17" python -m pip install -e . --no-build-isolation
```

Verify:

```bash
python -c "import pmx; print(pmx.__file__)"
```

If PMX was installed with `-e`, do not delete the PMX source directory.

For a non-editable installation:

```bash
python -m pip uninstall -y pmx

CFLAGS="-std=gnu17" python -m pip install . --no-build-isolation
```

After confirming PMX imports from `site-packages`, the source directory can be removed.

## 6. GROMACS

Use the HPC-optimized GROMACS module rather than installing another GROMACS build into the Mamba environment:

```bash
module load gromacs/2024.4-gcc11.3
which gmx
gmx --version
```

This keeps the cluster-specific MPI/compiler/GPU build separate from the Python environment.

## 7. AmberTools and ACPYPE

AmberTools is installed from `environment.yml`, so the HPC Amber module is normally unnecessary.

Verify:

```bash
which antechamber
which parmchk2
which tleap
which acpype
```

## 8. OpenFE / OpenFF / OpenMM

Verify:

```bash
python -c "import openfe; print('OpenFE:', openfe.__version__)"
python -c "import openff.toolkit; print('OpenFF:', openff.toolkit.__version__)"
python -c "import openmm; print('OpenMM:', openmm.__version__)"
python -c "import acpype; print('ACPYPE:', acpype.__file__)"
```

## 9. GUI and molecular viewer

The pip requirements install:

```text
PyQt5
PyQtWebEngine
QtPy
PyOpenGL
PyOpenGL_accelerate
ModernGL
PyVista
PyVistaQt
VTK
Pillow
Watchdog
```

`py3Dmol` is intentionally not included.

Verify:

```bash
python -c "from PyQt5.QtWidgets import QApplication; print('PyQt5 OK')"
python -c "import OpenGL; print('PyOpenGL:', OpenGL.__version__)"
python -c "import moderngl; print('ModernGL:', moderngl.__version__)"
python -c "import pyvista; print('PyVista:', pyvista.__version__)"
python -c "import pyvistaqt; print('PyVistaQt OK')"
python -c "import watchdog; print('Watchdog OK')"
```

For automatic GUI restart during development:

```bash
watchmedo auto-restart     --directory=.     --patterns="*.py"     --recursive     -- python liga.py
```

## 10. PMX force-field data for GROMACS

For residue alchemical workflows:

```bash
PMX_PATH="$(python -c 'import pmx, os; print(os.path.dirname(pmx.__file__))')"
export GMXLIB="${PMX_PATH}/data/mutff"
```

Verify:

```bash
echo "$PMX_PATH"
echo "$GMXLIB"
ls "$GMXLIB/amber99sb-star-ildn-mut.ff/forcefield.itp"
```

## 11. Suggested SLURM setup

```bash
#!/usr/bin/env bash

source /data/$USER/conda/etc/profile.d/conda.sh

if [ -f "/data/$USER/conda/etc/profile.d/mamba.sh" ]; then
    source /data/$USER/conda/etc/profile.d/mamba.sh
fi

conda activate /vf/users/liuy48/conda/envs/.alchemforge

module load gromacs/2024.4-gcc11.3
export GMX="gmx"

PMX_PATH="$(python -c 'import pmx, os; print(os.path.dirname(pmx.__file__))')"
export GMXLIB="${PMX_PATH}/data/mutff"

echo "Python:   $(command -v python)"
echo "GROMACS:  $(command -v gmx)"
echo "PMX:      ${PMX_PATH}"
echo "GMXLIB:   ${GMXLIB}"
```

## 12. Full verification

```bash
python - <<'PY'
import importlib

packages = [
    ("numpy", "NumPy"),
    ("scipy", "SciPy"),
    ("pandas", "Pandas"),
    ("matplotlib", "Matplotlib"),
    ("rdkit", "RDKit"),
    ("yaml", "PyYAML"),
    ("openfe", "OpenFE"),
    ("openff.toolkit", "OpenFF Toolkit"),
    ("openmm", "OpenMM"),
    ("acpype", "ACPYPE"),
    ("pmx", "PMX"),
    ("OpenGL", "PyOpenGL"),
    ("PyQt5", "PyQt5"),
    ("moderngl", "ModernGL"),
    ("pyvista", "PyVista"),
    ("pyvistaqt", "PyVistaQt"),
    ("watchdog", "Watchdog"),
    ("mpi4py", "mpi4py"),
]

for module, name in packages:
    try:
        m = importlib.import_module(module)
        version = getattr(m, "__version__", "OK")
        print(f"{name:20s} {version}")
    except Exception as exc:
        print(f"{name:20s} FAILED: {exc}")
PY
```

Also verify external executables:

```bash
which gmx
gmx --version

which antechamber
which parmchk2
which tleap

which nvcc
nvcc --version
```

## Dependency policy

Recommended split:

```text
Mamba / conda-forge:
    Python
    OpenFE
    OpenFF Toolkit
    OpenMM
    ACPYPE
    AmberTools
    RDKit
    OpenBabel
    scientific libraries
    CUDA toolkit

pip:
    AlchemForge editable install
    PyQt5 / viewer packages
    development tools
    PMX local source

HPC modules:
    GROMACS
    NVIDIA driver
```

Avoid blindly recreating exact package pins from the old Python 3.11 environment unless a specific compatibility issue requires them.
