#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Helper: print error and exit
# ============================================================
die() {
    echo "ERROR: $*" >&2
    exit 1
}


# ============================================================
# Detect GROMACS
#
# Priority:
#   1. Existing gmx in PATH
#   2. User-specified module
#   3. Common HPC module names
#   4. User-installed GROMACS via GMXRC
# ============================================================

setup_gromacs() {

    # Already available?
    if command -v gmx >/dev/null 2>&1 && gmx --version >/dev/null 2>&1; then
        echo "Found GROMACS:"
        gmx --version | head -n 2
        return
    fi

    # User-installed GROMACS
    # Example:
    # export GROMACS_GMXRC=$HOME/software/gromacs/bin/GMXRC
    if [[ -n "${GROMACS_GMXRC:-}" && -f "${GROMACS_GMXRC}" ]]; then
        echo "Loading user-installed GROMACS:"
        echo "  ${GROMACS_GMXRC}"

        source "${GROMACS_GMXRC}"

        if command -v gmx >/dev/null 2>&1 && gmx --version >/dev/null 2>&1; then
            return
        fi
    fi

    # HPC module system available?
    if command -v module >/dev/null 2>&1 || type module >/dev/null 2>&1; then

        # GROMACS 2024.4-gcc11.3 requires the CUDA runtime for libcufft.
        if [[ -n "${CUDA_MODULE:-CUDA/12.1}" ]]; then
            echo "Trying CUDA module: ${CUDA_MODULE:-CUDA/12.1}"
            module load "${CUDA_MODULE:-CUDA/12.1}" || true
        fi

        # Explicit module supplied by user
        if [[ -n "${GROMACS_MODULE:-}" ]]; then
            echo "Trying GROMACS module: ${GROMACS_MODULE}"

            if module load "${GROMACS_MODULE}"; then
                if command -v gmx >/dev/null 2>&1 && gmx --version >/dev/null 2>&1; then
                    return
                fi
            fi
        fi

        # Common possibilities
        for mod in \
            gromacs/2024.4-gcc11.3 \
            gromacs/2024.4 \
            GROMACS/2024.4 \
            gromacs \
            GROMACS
        do
            if module load "$mod" >/dev/null 2>&1; then
                if command -v gmx >/dev/null 2>&1 && gmx --version >/dev/null 2>&1; then
                    echo "Loaded GROMACS module: $mod"
                    return
                fi
            fi
        done
    fi

    die "
GROMACS was not found.

You can provide it in one of these ways:

  1. Load an HPC module manually:
       module load <your-gromacs-module>

  2. Specify the module:
       export GROMACS_MODULE=gromacs/2024.4

  3. Use your own GROMACS installation:
       export GROMACS_GMXRC=\$HOME/software/gromacs/bin/GMXRC

  4. Install GROMACS in your own Conda/Micromamba environment.
"
}


# ============================================================
# Detect AmberTools
# ============================================================

setup_amber() {

    # AmberTools utilities commonly needed
    if command -v tleap >/dev/null 2>&1; then
        echo "Found AmberTools:"
        command -v tleap
        return
    fi

    # Custom Amber installation
    if [[ -n "${AMBERHOME:-}" && -f "${AMBERHOME}/amber.sh" ]]; then
        source "${AMBERHOME}/amber.sh"

        if command -v tleap >/dev/null 2>&1; then
            return
        fi
    fi

    # HPC module
    if command -v module >/dev/null 2>&1 || type module >/dev/null 2>&1; then

        if [[ -n "${AMBER_MODULE:-}" ]]; then
            if module load "${AMBER_MODULE}"; then
                command -v tleap >/dev/null 2>&1 && return
            fi
        fi

        for mod in \
            amber/22-ambertools23.gcc \
            ambertools/23 \
            AmberTools/23 \
            amber \
            AmberTools
        do
            if module load "$mod" >/dev/null 2>&1; then
                if command -v tleap >/dev/null 2>&1; then
                    echo "Loaded AmberTools module: $mod"
                    return
                fi
            fi
        done
    fi

    die "
AmberTools was not found.

You can:

  1. Load the HPC module manually.

  2. Specify it:
       export AMBER_MODULE=amber/22-ambertools23.gcc

  3. Install AmberTools in your own Conda/Micromamba environment.
"
}


# ============================================================
# Check PMX
# ============================================================

setup_pmx() {

    if ! python -c "import pmx" >/dev/null 2>&1; then
        die "
Python package 'pmx' was not found.

Install pmx into your active Python environment before
running this workflow.
"
    fi

    PMX_PATH=$(python -c "import pmx; print(pmx.__path__[0])")

    export GMXLIB="${PMX_PATH}/data/mutff"

    if [[ ! -d "${GMXLIB}" ]]; then
        die "PMX mutation force-field directory not found: ${GMXLIB}"
    fi

    echo "PMX path: ${PMX_PATH}"
    echo "GMXLIB:    ${GMXLIB}"
}


# ============================================================
# Initialize environment
# ============================================================

setup_amber
setup_gromacs
setup_pmx

echo
echo "Environment successfully configured."