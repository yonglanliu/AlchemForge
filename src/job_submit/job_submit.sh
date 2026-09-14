#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_SCRIPT="${SCRIPT_DIR}/load_module.sh"
LIGAND_SCRIPT="${SCRIPT_DIR}/01_para_ligand.sh"
SYSTEM_SCRIPT="${SCRIPT_DIR}/02_system_setup.sh"
FEP_SCRIPT="${SCRIPT_DIR}/03_run_fep_pipeline.sh"
CONFIG_FILE="${SCRIPT_DIR}/$(basename "${SCRIPT_DIR}")_config.inp"

source "${CONFIG_FILE}"

for script in "${ENV_SCRIPT}" "${LIGAND_SCRIPT}" "${SYSTEM_SCRIPT}"; do
    if [[ ! -f "${script}" ]]; then
        die "Required workflow script not found: ${script}"
    fi
done

PROJECT_DIR="${WORK_DIR}/${JOB_NAME}"
mkdir -p "${PROJECT_DIR}/logs"


export GROMACS_MODULE AMBER_MODULE="${AMBERTOOLS_MODULE}"
source "${ENV_SCRIPT}"
source "${LIGAND_SCRIPT}" "${CONFIG_FILE}"
source "${SYSTEM_SCRIPT}" "${CONFIG_FILE}"
sbatch --export="ALL,CONFIG_FILE=${CONFIG_FILE}" "${FEP_SCRIPT}"


create_batch_script() {
    local stage="$1"
    local nodes="$2"
    local cpus="$3"
    local gpus="$4"
    local walltime="$5"
    local partition="$6"
    local command="$7"
    local batch_file="${PROJECT_DIR}/${JOB_NAME}_${stage}.sbatch"

    cat > "${batch_file}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=${JOB_NAME}_${stage}
#SBATCH --nodes=${nodes}
#SBATCH --cpus-per-task=${cpus}
#SBATCH --partition=${partition:-gpu}
#SBATCH --time=${walltime}
#SBATCH --output=${PROJECT_DIR}/logs/${JOB_NAME}_${stage}_%j.out
#SBATCH --error=${PROJECT_DIR}/logs/${JOB_NAME}_${stage}_%j.err

set -euo pipefail
export GROMACS_MODULE="${GROMACS_MODULE}"
export AMBER_MODULE="${AMBERTOOLS_MODULE}"
${command}
EOF
    chmod +x "${batch_file}"
    printf '%s\n' "${batch_file}"
}

LIGAND_BATCH=$(create_batch_script ligand "${LIGAND_NODES}" "${LIGAND_CPUS_PER_TASK}" "${LIGAND_GPUS}" "${LIGAND_WALLTIME}" "${LIGAND_PARTITION:-gpu}" "source '${ENV_SCRIPT}'; source '${LIGAND_SCRIPT}' '${CONFIG_FILE}'")
LIGAND_JOB=$(sbatch --parsable "${LIGAND_BATCH}")

SYSTEM_BATCH=$(create_batch_script system "${SYSTEM_NODES}" "${SYSTEM_CPUS_PER_TASK}" "${SYSTEM_GPUS}" "${SYSTEM_WALLTIME}" "${SYSTEM_PARTITION:-gpu}" "source '${ENV_SCRIPT}'; source '${SYSTEM_SCRIPT}' '${CONFIG_FILE}'")
SYSTEM_JOB=$(sbatch --parsable --dependency="afterok:${LIGAND_JOB%%;*}" "${SYSTEM_BATCH}")

FEP_BATCH=$(create_batch_script fep "${FEP_NODES}" 1 0 "${FEP_WALLTIME}" "norm" "export PREVIOUS_JOB_ID='${SYSTEM_JOB%%;*}'; source '${ENV_SCRIPT}'; source '${FEP_SCRIPT}' '${CONFIG_FILE}'")
FEP_JOB=$(sbatch --parsable --dependency="afterok:${SYSTEM_JOB%%;*}" "${FEP_BATCH}")

echo "Ligand parameterization job: ${LIGAND_JOB}"
echo "System setup job:            ${SYSTEM_JOB}"
echo "FEP simulation job:          ${FEP_JOB}"
