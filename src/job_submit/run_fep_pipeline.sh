#!/usr/bin/env bash

#SBATCH --job-name=rbfe_fep_pipeline
#SBATCH --partition=norm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:10:00

#SBATCH --output=logs/fep_master_%j.out
#SBATCH --error=logs/fep_master_%j.err


# ============================================================
# SAFETY GUARD
#
# Do not source this script.
#
# Correct:
#
#     sbatch scripts/run_fep_pipeline.sh
#
# ============================================================

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then

    echo
    echo "ERROR: Do not source run_fep_pipeline.sh"
    echo
    echo "Use:"
    echo
    echo "    sbatch scripts/run_fep_pipeline.sh"
    echo

    return 1
fi


# ============================================================
# Error handling
# ============================================================

set -e


# ============================================================
# Project root
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
ENV_SCRIPT="${SCRIPT_DIR}/load_module.sh"

cd "${ROOT}"


# ============================================================
# Load environment
# ============================================================


if [[ -f "${ROOT}/pmx_env/bin/activate" ]]; then
    source "${ROOT}/pmx_env/bin/activate"
fi

CONFIG_FILE="${1:-${ROOT}/${JOB_NAME}/${JOB_NAME}_config.inp}"

source "${CONFIG_FILE}"

# SLURM may execute a submitted copy from /var/spool. Resolve task files
# from the persistent project directory instead of BASH_SOURCE.
SCRIPT_DIR="${ROOT}/${JOB_NAME}"
ENV_SCRIPT="${SCRIPT_DIR}/load_module.sh"
LIGAND_SCRIPT="${SCRIPT_DIR}/01_para_ligand.sh"
SYSTEM_SCRIPT="${SCRIPT_DIR}/02_system_setup.sh"
FEP_SCRIPT="${SCRIPT_DIR}/ResAlchemFEP.sh"


# ============================================================
# Required configuration
# ============================================================

: "${JOB_NAME:?JOB_NAME must be defined in ?CONFIG_FILE}"

: "${START_REP:?START_REP must be defined in ?CONFIG_FILE}"

: "${NREP:?NREP must be defined in ?CONFIG_FILE}"

: "${NLAMBDA:?NLAMBDA must be defined in ?CONFIG_FILE}"

: "${MAX_FEP_JOBS:?MAX_FEP_JOBS must be defined in ?CONFIG_FILE}"

: "${FEP_DT_PS:?FEP_DT_PS must be defined in ?CONFIG_FILE}"

: "${FEP_NVT_PS:?FEP_NVT_PS must be defined in ?CONFIG_FILE}"

: "${FEP_NPT_PS:?FEP_NPT_PS must be defined in ?CONFIG_FILE}"

: "${FEP_PROD_NS:?FEP_PROD_NS must be defined in ?CONFIG_FILE}"

: "${FEP_NVT_STEPS:?FEP_NVT_STEPS must be defined in ?CONFIG_FILE}"

: "${FEP_NPT_STEPS:?FEP_NPT_STEPS must be defined in ?CONFIG_FILE}"

: "${FEP_PROD_STEPS:?FEP_PROD_STEPS must be defined in ?CONFIG_FILE}"

: "${FEP_LAMBDA_FUNCTION:?FEP_LAMBDA_FUNCTION must be defined in ?CONFIG_FILE}"


# ============================================================
# Derived replicate range
#
# Example:
#
# START_REP=4
# NREP=2
#
# -> run rep_4 and rep_5
# ============================================================

END_REP=$(( START_REP + NREP - 1 ))


# ============================================================
# Project directories
# ============================================================

PROJECT_DIR="${ROOT}/${JOB_NAME}"

LOG_DIR="${PROJECT_DIR}/logs"

mkdir -p "${LOG_DIR}"


# ============================================================
# Header
# ============================================================

echo
echo "============================================================"
echo "Equilibrium FEP master pipeline"
echo "============================================================"
echo "Date:          $(date)"
echo "Root:          ${ROOT}"
echo "Job name:      ${JOB_NAME}"
echo "Project dir:   ${PROJECT_DIR}"
echo "Master job:    ${SLURM_JOB_ID:-manual}"
echo "============================================================"


# ============================================================
# Pipeline scripts
# ============================================================

check_script() {
    local script="$1"

    if [[ ! -r "${script}" ]]; then
        echo "ERROR: Workflow script not found or not readable: ${script}"
        exit 1
    fi
}

check_script "${FEP_SCRIPT}"

if [[ "${RUN_PREPARATION:-0}" == "1" ]]; then
    check_script "${LIGAND_SCRIPT}"
    check_script "${SYSTEM_SCRIPT}"
    check_script "${ENV_SCRIPT}"
    source "${ENV_SCRIPT}"

    echo "Running ligand parameterization..."
    source "${LIGAND_SCRIPT}" "${CONFIG_FILE}"

    echo "Running system setup..."
    source "${SYSTEM_SCRIPT}" "${CONFIG_FILE}"
fi


# ============================================================
# Helper: check script
# ============================================================


# ============================================================
# Helper: check file
# ============================================================

check_file() {

    local file="$1"
    local description="$2"

    if [[ ! -s "${file}" ]]; then

        echo
        echo "ERROR: ${description} missing or empty:"
        echo "    ${file}"

        exit 1
    fi
}


# ============================================================
# Helper: safe SLURM submission
# ============================================================

submit_job() {

    local raw_job_id
    local job_id


    if ! raw_job_id=$(sbatch --parsable "$@"); then

        echo
        echo "ERROR: SLURM job submission failed." >&2

        printf "Command: sbatch" >&2

        for arg in "$@"
        do
            printf " %q" "${arg}" >&2
        done

        printf "\n" >&2

        return 1
    fi


    job_id="${raw_job_id%%;*}"


    if [[ -z "${job_id}" ]]; then

        echo "ERROR: sbatch returned an empty job ID." >&2

        return 1
    fi


    if [[ ! "${job_id}" =~ ^[0-9]+$ ]]; then

        echo "ERROR: Invalid SLURM job ID:"
        echo "    ${job_id}"

        return 1
    fi


    echo "${job_id}"
}


# ============================================================
# Validate workflow script
# ============================================================

echo
echo "Checking FEP workflow files..."


check_script "${FEP_SCRIPT}"


check_file \
    "${ROOT}/${JOB_NAME}/mdp/fep_base.mdp" \
    "base FEP MDP"


echo "Workflow script QC: PASS"


# ============================================================
# Configuration sanity checks
# ============================================================

if (( START_REP < 1 )); then

    echo "ERROR: START_REP must be >= 1"

    exit 1
fi


if (( NREP < 1 )); then

    echo "ERROR: NREP must be >= 1"

    exit 1
fi


if (( NLAMBDA < 2 )); then

    echo "ERROR: NLAMBDA must be >= 2"

    exit 1
fi


if (( MAX_FEP_JOBS < 1 )); then

    echo "ERROR: MAX_FEP_JOBS must be >= 1"

    exit 1
fi


if (( FEP_NVT_STEPS < 1 )); then

    echo "ERROR: FEP_NVT_STEPS must be >= 1"

    exit 1
fi


if (( FEP_NPT_STEPS < 1 )); then

    echo "ERROR: FEP_NPT_STEPS must be >= 1"

    exit 1
fi


if (( FEP_PROD_STEPS < 1 )); then

    echo "ERROR: FEP_PROD_STEPS must be >= 1"

    exit 1
fi


# ============================================================
# Validate prepared systems
#
# Only check requested replicate range:
#
#     START_REP ... END_REP
# ============================================================

echo
echo "============================================================"
echo "Checking prepared replicate systems"
echo "============================================================"


for LEG in apo bound
do

    for REP in $(seq "${START_REP}" "${END_REP}")
    do

        SETUP="${PROJECT_DIR}/${LEG}/rep_${REP}/setup"

        echo
        echo "Checking:"
        echo "    ${LEG} rep_${REP}"


        check_file \
            "${SETUP}/system.gro" \
            "${LEG} rep_${REP} system.gro"


        check_file \
            "${SETUP}/topol.top" \
            "${LEG} rep_${REP} topol.top"


        echo "    PASS"

    done

done


echo
echo "Prepared-system QC: PASS"


# ============================================================
# Calculate FEP array size
#
# NREP means number of NEW replicates to submit.
#
# Example:
#
# START_REP = 4
# NREP      = 2
# NLAMBDA   = 17
#
# Replicates:
#     rep_4
#     rep_5
#
# Total tasks:
#
#     2 legs × 2 replicates × 17 lambda
#     = 68 tasks
# ============================================================

N_LEGS=2

TASKS_PER_REP="${NLAMBDA}"

TASKS_PER_LEG=$(( NREP * NLAMBDA ))

N_FEP_TASKS=$(( N_LEGS * NREP * NLAMBDA ))

FEP_ARRAY_MAX=$(( N_FEP_TASKS - 1 ))


# ============================================================
# SLURM array
# ============================================================

FEP_ARRAY="0-${FEP_ARRAY_MAX}%${MAX_FEP_JOBS}"


# ============================================================
# Configuration summary
# ============================================================

echo
echo "============================================================"
echo "FEP configuration"
echo "============================================================"


echo
echo "Project:"
echo "    Job name:                ${JOB_NAME}"
echo "    Project directory:       ${PROJECT_DIR}"


echo
echo "Mutation:"
echo "    Chain:                   ${CHAIN:-NA}"
echo "    Residue:                 ${RESID:-NA}"
echo "    Mutation:                ${MUT:-NA}"


echo
echo "Replicates:"
echo "    Starting replicate:      ${START_REP}"
echo "    Ending replicate:        ${END_REP}"
echo "    Number to run:           ${NREP}"


echo
echo "Sampling:"
echo "    Lambda mode:             ${LAMBDA_MODE:-single}"
echo "    Lambda states:           ${NLAMBDA}"
echo "    Lambda function:         ${FEP_LAMBDA_FUNCTION}"
echo "    Lambda power:            ${FEP_LAMBDA_POWER:-NA}"


echo
echo "Integration:"
echo "    FEP timestep:            ${FEP_DT_PS} ps"


echo
echo "Equilibration:"
echo "    NVT:                     ${FEP_NVT_PS} ps"
echo "    NVT steps:               ${FEP_NVT_STEPS}"
echo "    NPT:                     ${FEP_NPT_PS} ps"
echo "    NPT steps:               ${FEP_NPT_STEPS}"


echo
echo "Production:"
echo "    Production / window:     ${FEP_PROD_NS} ns"
echo "    Production steps:        ${FEP_PROD_STEPS}"


echo
echo "SLURM:"
echo "    Legs:                    ${N_LEGS}"
echo "    Tasks / replicate:       ${TASKS_PER_REP}"
echo "    Tasks / leg:             ${TASKS_PER_LEG}"
echo "    Total FEP tasks:         ${N_FEP_TASKS}"
echo "    Maximum simultaneous:    ${MAX_FEP_JOBS}"
echo "    Array:                   ${FEP_ARRAY}"


echo
echo "============================================================"


# ============================================================
# Submit parallel FEP array
#
# No preparation dependency.
# No automatic analysis job.
# ============================================================

echo
echo "============================================================"
echo "Submit parallel FEP array"
echo "============================================================"


FEP_SUBMIT_ARGS=(
    --job-name="${JOB_NAME}_fep"
    --partition="${FEP_PARTITION:-gpu}"
    --gres="gpu:${FEP_GPUS:-1}"
    --cpus-per-task="${FEP_CPUS_PER_TASK:-1}"
    --output="${LOG_DIR}/fep_%A_%a.out"
    --error="${LOG_DIR}/fep_%A_%a.err"
    --array="${FEP_ARRAY}"
)

if [[ -n "${PREVIOUS_JOB_ID:-}" ]]; then
    FEP_SUBMIT_ARGS+=(--dependency="afterok:${PREVIOUS_JOB_ID%%;*}")
fi

FEP_SUBMIT_ARGS+=("${FEP_SCRIPT}" "${CONFIG_FILE}")
FEP_JOB=$(submit_job "${FEP_SUBMIT_ARGS[@]}")


echo
echo "FEP array submitted:"
echo "    ${FEP_JOB}"

echo
echo "Array:"
echo "    ${FEP_ARRAY}"

echo
echo "Replicate range:"
echo "    rep_${START_REP} through rep_${END_REP}"

echo
echo "Dependency:"
echo "    ${PREVIOUS_JOB_ID:-none}"


# ============================================================
# Save pipeline job information
# ============================================================

PIPELINE_JOB_FILE="${PROJECT_DIR}/pipeline_jobs.txt"


cat > "${PIPELINE_JOB_FILE}" <<EOF
submission_date=$(date)

job_name=${JOB_NAME}

fep_job=${FEP_JOB}

start_rep=${START_REP}
end_rep=${END_REP}
nrep=${NREP}

nlambda=${NLAMBDA}
n_fep_tasks=${N_FEP_TASKS}

max_fep_jobs=${MAX_FEP_JOBS}

fep_array=${FEP_ARRAY}
EOF


# ============================================================
# Final summary
# ============================================================

echo
echo "============================================================"
echo "Equilibrium FEP pipeline submitted successfully"
echo "============================================================"


echo
echo "Project:"
echo "    ${JOB_NAME}"


echo
echo "Replicates:"
echo "    rep_${START_REP} through rep_${END_REP}"


echo
echo "FEP array:"
echo "    Job ID: ${FEP_JOB}"
echo "    Array:  ${FEP_ARRAY}"


echo
echo "Analysis:"
echo "    not submitted automatically"


echo
echo "Monitor:"
echo
echo "    sjobs"


echo
echo "Detailed FEP status:"
echo
echo "    sacct -j ${FEP_JOB} \\"
echo "        --format=JobID,JobName,State,ExitCode,Elapsed"


echo
echo "Failed FEP tasks:"
echo
echo "    sacct -j ${FEP_JOB} \\"
echo "        --format=JobID,State,ExitCode,Elapsed \\"
echo "        | grep FAILED"


echo
echo "Pipeline job IDs:"
echo "    ${PIPELINE_JOB_FILE}"


echo
echo "============================================================"