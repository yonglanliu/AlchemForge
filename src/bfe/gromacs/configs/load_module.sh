#!/usr/bin/env bash
# ============================================================
# Activate AlchemForge environment
# ============================================================

echo "============================================================"
echo "Loading AlchemForge environment"
echo "============================================================"

source /data/${USER}/conda/etc/profile.d/conda.sh

conda activate /vf/users/liuy48/conda/envs/.alchemforge

echo "Python: $(which python)"
echo "Conda environment: ${CONDA_PREFIX}"

# GROMACS

module load gromacs/2024.4-gcc11.3
export GMX="gmx"

# PMX

PMX_PATH="$(python -c 'import pmx, os; print(os.path.dirname(pmx.__file__))')"
export GMXLIB="${PMX_PATH}/data/mutff"

echo
echo "GROMACS: $(command -v gmx)"
echo "AmberTools: $(command -v tleap)"
echo "PMX: ${PMX_PATH}"
echo "GMXLIB: ${GMXLIB}"
echo
echo "Environment setup completed."
echo "============================================================"
