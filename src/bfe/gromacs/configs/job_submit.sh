#!/usr/bin/env bash


# ============================================================
# Activate AlchemForge environment
# ============================================================

source /data/${USER}/conda/etc/profile.d/conda.sh

conda activate /vf/users/liuy48/conda/envs/.alchemforge

echo "Python:"
echo "    $(which python)"

echo "Conda environment:"
echo "    ${CONDA_PREFIX}"


# ============================================================
# Locate workflow files
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LIGAND_SCRIPT="${SCRIPT_DIR}/01_para_ligand.sh"
SYSTEM_SCRIPT="${SCRIPT_DIR}/02_system_setup.sh"
FEP_SCRIPT="${SCRIPT_DIR}/03_run_fep_pipeline.sh"

CONFIG_FILE="${SCRIPT_DIR}/$(basename "${SCRIPT_DIR}")_config.inp"


# ============================================================
# Validate config
# ======================================================~=====

if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "ERROR: Configuration file not found:" >&2
    echo "    ${CONFIG_FILE}" >&2
    exit 1
fi


CONFIG_FILE="$(readlink -f "${CONFIG_FILE}")"

echo
echo "Configuration file:"
echo "    ${CONFIG_FILE}"


# ============================================================
# Load config
# ============================================================

source "${CONFIG_FILE}"


: "${WORK_DIR:?WORK_DIR must be defined in CONFIG_FILE}"
: "${JOB_NAME:?JOB_NAME must be defined in CONFIG_FILE}"


# ============================================================
# Project directory
# ============================================================

PROJECT_DIR="${WORK_DIR}/${JOB_NAME}"

mkdir -p "${PROJECT_DIR}/logs"


# ============================================================
# Validate workflow scripts
# ============================================================

for script in \
    "${LIGAND_SCRIPT}" \
    "${SYSTEM_SCRIPT}" \
    "${FEP_SCRIPT}"
do

    if [[ ! -f "${script}" ]]; then
        echo "ERROR: Workflow script not found:" >&2
        echo "    ${script}" >&2
        exit 1
    fi

done


# ============================================================
# Ligand parameterization
# ============================================================

echo
echo "============================================================"
echo "Submitting ligand parameterization"
echo "============================================================"


LIGAND_JOB=$(
    sbatch \
        --parsable \
        --export="ALL,CONFIG_FILE=${CONFIG_FILE}" \
        "${LIGAND_SCRIPT}" \
        "${CONFIG_FILE}"
)


LIGAND_JOB="${LIGAND_JOB%%;*}"


if [[ ! "${LIGAND_JOB}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Invalid ligand job ID:" >&2
    echo "    ${LIGAND_JOB}" >&2
    exit 1
fi


echo "Ligand job:"
echo "    ${LIGAND_JOB}"


# ============================================================
# System setup
# ============================================================

echo
echo "============================================================"
echo "Submitting system setup"
echo "============================================================"


SYSTEM_JOB=$(
    sbatch \
        --parsable \
        --dependency="afterok:${LIGAND_JOB}" \
        --export="ALL,CONFIG_FILE=${CONFIG_FILE}" \
        "${SYSTEM_SCRIPT}" \
        "${CONFIG_FILE}"
)


SYSTEM_JOB="${SYSTEM_JOB%%;*}"


if [[ ! "${SYSTEM_JOB}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Invalid system job ID:" >&2
    echo "    ${SYSTEM_JOB}" >&2
    exit 1
fi


echo "System job:"
echo "    ${SYSTEM_JOB}"


# ============================================================
# FEP pipeline
# ============================================================

echo
echo "============================================================"
echo "Submitting FEP pipeline"
echo "============================================================"


FEP_JOB=$(
    sbatch \
        --parsable \
        --dependency="afterok:${SYSTEM_JOB}" \
        --export="ALL,CONFIG_FILE=${CONFIG_FILE}" \
        "${FEP_SCRIPT}" \
        "${CONFIG_FILE}"
)


FEP_JOB="${FEP_JOB%%;*}"


if [[ ! "${FEP_JOB}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Invalid FEP job ID:" >&2
    echo "    ${FEP_JOB}" >&2
    exit 1
fi


echo "FEP pipeline job:"
echo "    ${FEP_JOB}"


# ============================================================
# Summary
# ============================================================

echo
echo "============================================================"
echo "Workflow submitted successfully"
echo "============================================================"

echo
echo "Ligand parameterization:"
echo "    ${LIGAND_JOB}"

echo
echo "System setup:"
echo "    ${SYSTEM_JOB}"
echo "    dependency: afterok:${LIGAND_JOB}"

echo
echo "FEP pipeline:"
echo "    ${FEP_JOB}"
echo "    dependency: afterok:${SYSTEM_JOB}"

echo
echo "============================================================"