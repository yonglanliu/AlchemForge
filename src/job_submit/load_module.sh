#!/usr/bin/env bash

echo "============================================================"
echo "Loading AlchemForge environment"
echo "============================================================"

# AmberTools

module load amber/22-ambertools23.gcc

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
