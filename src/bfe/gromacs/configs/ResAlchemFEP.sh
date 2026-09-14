#!/usr/bin/env bash

#SBATCH --job-name=rbfe_fep
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --mem=8G
#SBATCH --time=06:00:00

# Placeholder only.
# run_fep_pipeline.sh overrides this with --array.
#SBATCH --array=0-0

# NOTE:
# Do not use shell variables such as ${WORK_DIR} or ${JOB_NAME}
# in #SBATCH --output/--error directives. The master submission
# script should pass --output and --error explicitly.

set -euo pipefail


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
# Required values from the master submission
# ============================================================

: "${CONFIG_FILE:?CONFIG_FILE was not passed by the master submission}"


# ============================================================
# Validate and load project config
# ============================================================

if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "ERROR: Project config not found:" >&2
    echo "    ${CONFIG_FILE}" >&2
    exit 1
fi

echo "Config file: ${CONFIG_FILE}"

source "${CONFIG_FILE}"

: "${WORK_DIR:?WORK_DIR must be defined in CONFIG_FILE}"
: "${JOB_NAME:?JOB_NAME must be defined in CONFIG_FILE}"


# ============================================================
# Project directory
# ============================================================

SCRIPT_DIR="${WORK_DIR}/${JOB_NAME}"

if [[ ! -d "${SCRIPT_DIR}" ]]; then
    echo "ERROR: Project directory not found:" >&2
    echo "    ${SCRIPT_DIR}" >&2
    exit 1
fi

cd "${SCRIPT_DIR}"


# ============================================================
# Load GROMACS module
# ============================================================
GROMACS_PATH="$(python -c 'import bfe.gromacs, os; print(os.path.dirname(bfe.gromacs.__file__))')"
echo "$GROMACS_PATH"
MODULE_LOAD_FILE_PATH="${GROMACS_PATH}/configs/load_module.sh"
echo "Loading GROMACS module from: ${MODULE_LOAD_FILE_PATH}"
source "${MODULE_LOAD_FILE_PATH}"


# ============================================================
# Locate GROMACS
# ============================================================

if [[ -n "${GMX:-}" ]]; then
    if ! command -v "${GMX}" >/dev/null 2>&1; then
        echo "ERROR: GMX is set but cannot be executed:" >&2
        echo "    GMX=${GMX}" >&2
        exit 1
    fi
elif command -v gmx >/dev/null 2>&1; then
    GMX="gmx"
elif command -v gmx_mpi >/dev/null 2>&1; then
    GMX="gmx_mpi"
else
    echo "ERROR: GROMACS executable was not found." >&2
    echo "Load GROMACS in ${MODULE_FILE}, or set GMX explicitly." >&2
    echo "PATH=${PATH}" >&2
    exit 1
fi

export GMX

echo "GROMACS executable: $(command -v "${GMX}")"
"${GMX}" --version

# ============================================================
# Required parameters
# ============================================================

: "${START_REP:?START_REP must be defined}"
: "${NREP:?NREP must be defined}"
: "${NLAMBDA:?NLAMBDA must be defined}"


END_REP=$(( START_REP + NREP - 1 ))


echo "============================================================"
echo "FEP array task configuration"
echo "============================================================"
echo "JOB_NAME:            ${JOB_NAME}"
echo "Config:              ${CONFIG_FILE}"
echo "START_REP:           ${START_REP}"
echo "END_REP:             ${END_REP}"
echo "NREP:                ${NREP}"
echo "NLAMBDA:             ${NLAMBDA}"
echo "SLURM_ARRAY_TASK_ID: ${SLURM_ARRAY_TASK_ID}"
echo "============================================================"


# ============================================================
# CPU / GPU
# ============================================================

OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"

export OMP_NUM_THREADS


# ============================================================
# Base FEP MDP
# ============================================================

BASE_FEP_MDP="${GROMACS_PATH}/mdp/fep_base.mdp"


if [[ ! -s "${BASE_FEP_MDP}" ]]; then

    echo
    echo "ERROR: Base FEP MDP missing:"
    echo "    ${BASE_FEP_MDP}"

    exit 1
fi


# ============================================================
# Generate coupled lambda schedule
# ============================================================

generate_lambda_schedule() {
    
    local function="$1"
    local n="$2"
    local power="$3"

    python - \
        "${function}" \
        "${n}" \
        "${power}" <<'PY'

import sys
import math


kind = sys.argv[1]

n = int(sys.argv[2])

power = float(sys.argv[3])


if n < 2:
    raise ValueError(
        "Number of lambda states must be >= 2"
    )


values = []


for i in range(n):

    x = i / (n - 1)


    if kind == "linear":

        lam = x


    elif kind == "cosine":

        lam = 0.5 * (
            1.0
            -
            math.cos(
                math.pi * x
            )
        )


    elif kind == "power":

        lam = x ** power


    else:

        raise ValueError(
            f"Unknown lambda function: {kind}"
        )


    values.append(lam)


print(
    " ".join(
        f"{v:.6f}"
        for v in values
    )
)

PY
}


# ============================================================
# Generate lambda vector
# ============================================================

FEP_LAMBDA_STRING=$(
    generate_lambda_schedule \
        "${FEP_LAMBDA_FUNCTION}" \
        "${NLAMBDA}" \
        "${FEP_LAMBDA_POWER}"
)


read -r -a FEP_LAMBDAS <<< "${FEP_LAMBDA_STRING}"


# ============================================================
# Lambda QC
# ============================================================
GENERATED_NLAMBDA="${#FEP_LAMBDAS[@]}"


if (( GENERATED_NLAMBDA != NLAMBDA )); then

    echo
    echo "ERROR: lambda count mismatch"

    echo "Configured:"
    echo "    ${NLAMBDA}"

    echo "Generated:"
    echo "    ${GENERATED_NLAMBDA}"

    exit 1
fi


# ============================================================
# SLURM array mapping
# ============================================================

TASK_ID="${SLURM_ARRAY_TASK_ID:-0}"


TASKS_PER_LEG=$(( NREP * NLAMBDA ))

TOTAL_TASKS=$(( 2 * TASKS_PER_LEG ))


if (( TASK_ID < 0 || TASK_ID >= TOTAL_TASKS )); then

    echo
    echo "ERROR: Invalid SLURM_ARRAY_TASK_ID"

    echo "Task ID:"
    echo "    ${TASK_ID}"

    echo "Expected range:"
    echo "    0-$(( TOTAL_TASKS - 1 ))"

    exit 1
fi


# ============================================================
# Determine thermodynamic leg
# ============================================================

LEG_INDEX=$(( TASK_ID / TASKS_PER_LEG ))

LOCAL_TASK=$(( TASK_ID % TASKS_PER_LEG ))


case "${LEG_INDEX}" in

    0)

        LEG="apo"

        ;;


    1)

        LEG="bound"

        ;;


    *)

        echo "ERROR: Invalid leg index:"
        echo "    ${LEG_INDEX}"

        exit 1

        ;;

esac


# ============================================================
# Determine replicate / lambda
#
# START_REP controls the first replicate number.
#
# Example:
#
#     START_REP=4
#     NREP=3
#
# gives:
#
#     REP_OFFSET=0 -> rep_4
#     REP_OFFSET=1 -> rep_5
#     REP_OFFSET=2 -> rep_6
# ============================================================

REP_OFFSET=$(( LOCAL_TASK / NLAMBDA ))

REP=$(( START_REP + REP_OFFSET ))

LAMBDA_STATE=$(( LOCAL_TASK % NLAMBDA ))


# ============================================================
# Replicate mapping QC
# ============================================================

if (( REP < START_REP || REP > END_REP )); then

    echo
    echo "ERROR: decoded replicate is outside requested range"
    echo "    START_REP:    ${START_REP}"
    echo "    END_REP:      ${END_REP}"
    echo "    REP_OFFSET:   ${REP_OFFSET}"
    echo "    REP:          ${REP}"
    echo "    LOCAL_TASK:   ${LOCAL_TASK}"
    echo "    NLAMBDA:      ${NLAMBDA}"

    exit 1
fi


CURRENT_LAMBDA="${FEP_LAMBDAS[$LAMBDA_STATE]}"


printf -v LAMBDA_DIR \
    "lambda_%02d" \
    "${LAMBDA_STATE}"


# ============================================================
# Velocity seed
#
# Unique for each replicate/lambda.
# ============================================================

GEN_SEED=$(( 100000 + REP * 1000 + LAMBDA_STATE ))


# ============================================================
# Input setup
# ============================================================

SETUP="${WORK_DIR}/${JOB_NAME}/${LEG}/rep_${REP}/setup"

TOP="${SETUP}/topol.top"

START_GRO="${SETUP}/system.gro"


if [[ ! -s "${TOP}" ]]; then

    echo
    echo "ERROR: topology missing:"
    echo "    ${TOP}"

    exit 1
fi


if [[ ! -s "${START_GRO}" ]]; then

    echo
    echo "ERROR: starting structure missing:"
    echo "    ${START_GRO}"

    exit 1
fi


# ============================================================
# Work directory
# ============================================================

WORKDIR="${WORK_DIR}/${JOB_NAME}/${LEG}/rep_${REP}/fep/${LAMBDA_DIR}"

mkdir -p "${WORKDIR}"

cd "${WORKDIR}"


# ============================================================
# Logging
#
# SLURM already captures stdout/stderr, so no exec/tee
# redirection is required here.
# ============================================================

LOG_DIR="${SCRIPT_DIR}/logs"

mkdir -p "${LOG_DIR}"


# ============================================================
# Header
# ============================================================

echo
echo "============================================================"
echo "Parallel equilibrium FEP"
echo "============================================================"

echo "Task ID:               ${TASK_ID}"
echo "Leg:                   ${LEG}"
echo "Replicate offset:      ${REP_OFFSET}"
echo "Replicate:             ${REP}"
echo "Lambda state:          ${LAMBDA_STATE}"
echo "Lambda value:          ${CURRENT_LAMBDA}"
echo "Total lambda states:   ${NLAMBDA}"

echo
echo "Lambda function:       ${FEP_LAMBDA_FUNCTION}"
echo "Lambda power:          ${FEP_LAMBDA_POWER}"

echo
echo "FEP timestep:          ${FEP_DT_PS} ps"

echo
echo "NVT:"
echo "    ${FEP_NVT_PS} ps"
echo "    ${FEP_NVT_STEPS} steps"

echo
echo "NPT:"
echo "    ${FEP_NPT_PS} ps"
echo "    ${FEP_NPT_STEPS} steps"

echo
echo "Production:"
echo "    ${FEP_PROD_NS} ns"
echo "    ${FEP_PROD_STEPS} steps"

echo
echo "Velocity seed:"
echo "    ${GEN_SEED}"

echo
echo "Work directory:"
echo "    ${WORKDIR}"

echo "============================================================"


# ============================================================
# Print lambda schedule
# ============================================================

echo
echo "Coupled lambda schedule:"
echo


printf "%-8s %-14s\n" \
    "STATE" \
    "LAMBDA"


echo "------------------------"


for (( i=0; i<NLAMBDA; i++ ))
do

    printf "%-8d %-14s" \
        "${i}" \
        "${FEP_LAMBDAS[$i]}"


    if (( i == LAMBDA_STATE )); then

        printf "  <-- current"

    fi


    printf "\n"

done


# ============================================================
# Save lambda schedule
# ============================================================

SCHEDULE_FILE="${WORKDIR}/lambda_schedule.tsv"


{
    printf "state\tlambda\n"

    for (( i=0; i<NLAMBDA; i++ ))
    do

        printf "%d\t%s\n" \
            "${i}" \
            "${FEP_LAMBDAS[$i]}"

    done

} > "${SCHEDULE_FILE}"


# ============================================================
# Save current-state metadata
# ============================================================

cat > "${WORKDIR}/lambda_state.txt" <<EOF
task_id=${TASK_ID}
leg=${LEG}
start_rep=${START_REP}
end_rep=${END_REP}
replicate_offset=${REP_OFFSET}
replicate=${REP}
lambda_state=${LAMBDA_STATE}
lambda=${CURRENT_LAMBDA}
total_lambda_states=${NLAMBDA}
lambda_function=${FEP_LAMBDA_FUNCTION}
lambda_power=${FEP_LAMBDA_POWER}
fep_dt_ps=${FEP_DT_PS}
velocity_seed=${GEN_SEED}
EOF


# ============================================================
# Generate stage-specific MDP
#
# $1 = output MDP
# $2 = stage
#
# Stages:
#
#     EM
#     NVT
#     NPT
#     PROD
# ============================================================

prepare_mdp() {

    local OUTPUT_MDP="$1"

    local STAGE="$2"


    # --------------------------------------------------------
    # Copy common base
    # --------------------------------------------------------

    cp "${BASE_FEP_MDP}" "${OUTPUT_MDP}"


    # --------------------------------------------------------
    # Remove parameters controlled by this script
    # --------------------------------------------------------

    sed -i \
        -e '/^[[:space:]]*integrator[[:space:]]*=/d' \
        -e '/^[[:space:]]*dt[[:space:]]*=/d' \
        -e '/^[[:space:]]*nsteps[[:space:]]*=/d' \
        -e '/^[[:space:]]*continuation[[:space:]]*=/d' \
        -e '/^[[:space:]]*gen_vel[[:space:]]*=/d' \
        -e '/^[[:space:]]*gen_temp[[:space:]]*=/d' \
        -e '/^[[:space:]]*gen_seed[[:space:]]*=/d' \
        -e '/^[[:space:]]*tcoupl[[:space:]]*=/d' \
        -e '/^[[:space:]]*tc-grps[[:space:]]*=/d' \
        -e '/^[[:space:]]*tau_t[[:space:]]*=/d' \
        -e '/^[[:space:]]*ref_t[[:space:]]*=/d' \
        -e '/^[[:space:]]*pcoupl[[:space:]]*=/d' \
        -e '/^[[:space:]]*pcoupltype[[:space:]]*=/d' \
        -e '/^[[:space:]]*tau_p[[:space:]]*=/d' \
        -e '/^[[:space:]]*ref_p[[:space:]]*=/d' \
        -e '/^[[:space:]]*compressibility[[:space:]]*=/d' \
        -e '/^[[:space:]]*emtol[[:space:]]*=/d' \
        -e '/^[[:space:]]*emstep[[:space:]]*=/d' \
        -e '/^[[:space:]]*init-lambda-state[[:space:]]*=/d' \
        -e '/^[[:space:]]*init-lambda[[:space:]]*=/d' \
        -e '/^[[:space:]]*delta-lambda[[:space:]]*=/d' \
        -e '/^[[:space:]]*fep-lambdas[[:space:]]*=/d' \
        -e '/^[[:space:]]*coul-lambdas[[:space:]]*=/d' \
        -e '/^[[:space:]]*vdw-lambdas[[:space:]]*=/d' \
        -e '/^[[:space:]]*bonded-lambdas[[:space:]]*=/d' \
        -e '/^[[:space:]]*mass-lambdas[[:space:]]*=/d' \
        -e '/^[[:space:]]*restraint-lambdas[[:space:]]*=/d' \
        -e '/^[[:space:]]*lincs_iter[[:space:]]*=/d' \
        -e '/^[[:space:]]*lincs_order[[:space:]]*=/d' \
        -e '/^[[:space:]]*lincs_warnangle[[:space:]]*=/d' \
        "${OUTPUT_MDP}"


    # --------------------------------------------------------
    # Common FEP settings
    # --------------------------------------------------------

    cat >> "${OUTPUT_MDP}" <<EOF


; ============================================================
; Coupled FEP lambda configuration
; ============================================================

free-energy             = yes

init-lambda-state       = ${LAMBDA_STATE}

delta-lambda            = 0

fep-lambdas             = ${FEP_LAMBDA_STRING}


; ============================================================
; LINCS
; ============================================================

lincs_iter              = 2

lincs_order             = 6

lincs_warnangle         = 30

EOF


    # --------------------------------------------------------
    # Stage-specific settings
    # --------------------------------------------------------

    case "${STAGE}" in


        # ====================================================
        # Energy minimization
        # ====================================================

        EM)

            cat >> "${OUTPUT_MDP}" <<EOF


; ============================================================
; Energy minimization
; ============================================================

integrator              = steep

nsteps                  = 50000

emtol                   = 500.0

emstep                  = 0.01

continuation            = no

tcoupl                  = no

pcoupl                  = no

gen_vel                 = no

EOF

            ;;


        # ====================================================
        # NVT
        # ====================================================

        NVT)

            cat >> "${OUTPUT_MDP}" <<EOF


; ============================================================
; NVT equilibration
; ============================================================

integrator              = md

dt                      = ${FEP_DT_PS}

nsteps                  = ${FEP_NVT_STEPS}

continuation            = no


; Temperature coupling

tcoupl                  = V-rescale

tc-grps                 = System

tau_t                   = 1.0

ref_t                   = ${TEMPERATURE}


; No pressure coupling

pcoupl                  = no


; Generate independent velocities

gen_vel                 = yes

gen_temp                = ${TEMPERATURE}

gen_seed                = ${GEN_SEED}

EOF

            ;;


        # ====================================================
        # NPT
        # ====================================================

        NPT)

            cat >> "${OUTPUT_MDP}" <<EOF


; ============================================================
; NPT equilibration
; ============================================================

integrator              = md

dt                      = ${FEP_DT_PS}

nsteps                  = ${FEP_NPT_STEPS}

continuation            = yes


; Temperature coupling

tcoupl                  = V-rescale

tc-grps                 = System

tau_t                   = 1.0

ref_t                   = ${TEMPERATURE}


; Pressure coupling

pcoupl                  = C-rescale

pcoupltype              = isotropic

tau_p                   = 5.0

ref_p                   = ${PRESSURE}

compressibility         = 4.5e-5


gen_vel                 = no

EOF

            ;;


        # ====================================================
        # Production
        # ====================================================

        PROD)

            cat >> "${OUTPUT_MDP}" <<EOF


; ============================================================
; FEP production
; ============================================================

integrator              = md

dt                      = ${FEP_DT_PS}

nsteps                  = ${FEP_PROD_STEPS}

continuation            = yes


; Temperature coupling

tcoupl                  = V-rescale

tc-grps                 = System

tau_t                   = 1.0

ref_t                   = ${TEMPERATURE}


; Pressure coupling

pcoupl                  = C-rescale

pcoupltype              = isotropic

tau_p                   = 5.0

ref_p                   = ${PRESSURE}

compressibility         = 4.5e-5


gen_vel                 = no

EOF

            ;;


        *)

            echo
            echo "ERROR: Unknown MDP stage:"
            echo "    ${STAGE}"

            exit 1

            ;;

    esac
}


# ============================================================
# Generate all MDP files
# ============================================================

prepare_mdp \
    "${WORKDIR}/em.mdp" \
    "EM"


prepare_mdp \
    "${WORKDIR}/nvt.mdp" \
    "NVT"


prepare_mdp \
    "${WORKDIR}/npt.mdp" \
    "NPT"


prepare_mdp \
    "${WORKDIR}/prod.mdp" \
    "PROD"


# ============================================================
# MDP QC
# ============================================================

echo
echo "============================================================"
echo "Generated MDP QC"
echo "============================================================"


for MDP in \
    em.mdp \
    nvt.mdp \
    npt.mdp \
    prod.mdp
do

    echo
    echo "---- ${MDP} ----"


    grep -E \
        '^[[:space:]]*(integrator|dt|nsteps|continuation|gen_vel|gen_temp|gen_seed|tcoupl|pcoupl|init-lambda-state|fep-lambdas|coul-lambdas|vdw-lambdas|lincs_iter|lincs_order)' \
        "${MDP}" \
        || true

done


# ============================================================
# Ensure staged lambda settings are absent
# ============================================================

for MDP in \
    em.mdp \
    nvt.mdp \
    npt.mdp \
    prod.mdp
do

    if grep -Eq \
        '^[[:space:]]*(coul-lambdas|vdw-lambdas)[[:space:]]*=' \
        "${MDP}"
    then

        echo
        echo "ERROR: staged lambda configuration remains in:"
        echo "    ${MDP}"

        exit 1
    fi

done


# ============================================================
# Full-window restart check
# ============================================================

if [[ -s prod.log && \
      -s prod.gro && \
      -s dhdl.xvg ]] && \
   grep -q "Finished mdrun" prod.log
then

    echo
    echo "FEP window already completed successfully:"
    echo "    ${WORKDIR}"

    exit 0
fi


# ============================================================
# STEP 1
# Energy minimization
# ============================================================

echo
echo "============================================================"
echo "STEP 1: Energy minimization"
echo "============================================================"


if [[ -s em.log && \
      -s em.gro ]] && \
   grep -q "Finished mdrun" em.log
then

    echo
    echo "EM already completed."

else

    rm -f \
        em.tpr \
        em.log \
        em.edr \
        em.trr \
        em.gro


    ${GMX} grompp \
        -f em.mdp \
        -c "${START_GRO}" \
        -p "${TOP}" \
        -o em.tpr \
        -maxwarn 1


    if [[ ! -s em.tpr ]]; then

        echo
        echo "ERROR: em.tpr was not generated"

        exit 1
    fi


    ${GMX} mdrun \
        -deffnm em \
        -ntomp "${OMP_NUM_THREADS}" \
        ${MDRUN_EM_OPTIONS:-}

fi


if [[ ! -s em.gro ]]; then

    echo
    echo "ERROR: em.gro missing"

    exit 1
fi


if [[ ! -s em.log ]] || \
   ! grep -q "Finished mdrun" em.log
then

    echo
    echo "ERROR: Energy minimization did not finish normally"

    exit 1
fi


# ============================================================
# STEP 2
# NVT equilibration
# ============================================================

echo
echo "============================================================"
echo "STEP 2: NVT equilibration"
echo "============================================================"


if [[ -s nvt.log && \
      -s nvt.gro && \
      -s nvt.cpt ]] && \
   grep -q "Finished mdrun" nvt.log
then

    echo
    echo "NVT already completed."

else

    rm -f \
        nvt.tpr \
        nvt.log \
        nvt.edr \
        nvt.xtc \
        nvt.trr \
        nvt.gro \
        nvt.cpt


    ${GMX} grompp \
        -f nvt.mdp \
        -c em.gro \
        -p "${TOP}" \
        -o nvt.tpr \
        -maxwarn 1


    if [[ ! -s nvt.tpr ]]; then

        echo
        echo "ERROR: nvt.tpr was not generated"

        exit 1
    fi


    ${GMX} mdrun \
        -deffnm nvt \
        -ntomp "${OMP_NUM_THREADS}" \
        ${MDRUN_MD_OPTIONS:-}

fi


if [[ ! -s nvt.gro ]]; then

    echo
    echo "ERROR: nvt.gro missing"

    exit 1
fi


if [[ ! -s nvt.cpt ]]; then

    echo
    echo "ERROR: nvt.cpt missing"

    exit 1
fi


if [[ ! -s nvt.log ]] || \
   ! grep -q "Finished mdrun" nvt.log
then

    echo
    echo "ERROR: NVT did not finish normally"

    exit 1
fi


# ============================================================
# STEP 3
# NPT equilibration
# ============================================================

echo
echo "============================================================"
echo "STEP 3: NPT equilibration"
echo "============================================================"


if [[ -s npt.log && \
      -s npt.gro && \
      -s npt.cpt ]] && \
   grep -q "Finished mdrun" npt.log
then

    echo
    echo "NPT already completed."

else

    rm -f \
        npt.tpr \
        npt.log \
        npt.edr \
        npt.xtc \
        npt.trr \
        npt.gro \
        npt.cpt


    ${GMX} grompp \
        -f npt.mdp \
        -c nvt.gro \
        -t nvt.cpt \
        -p "${TOP}" \
        -o npt.tpr \
        -maxwarn 1


    if [[ ! -s npt.tpr ]]; then

        echo
        echo "ERROR: npt.tpr was not generated"

        exit 1
    fi


    ${GMX} mdrun \
        -deffnm npt \
        -ntomp "${OMP_NUM_THREADS}" \
        ${MDRUN_MD_OPTIONS:-}

fi


if [[ ! -s npt.gro ]]; then

    echo
    echo "ERROR: npt.gro missing"

    exit 1
fi


if [[ ! -s npt.cpt ]]; then

    echo
    echo "ERROR: npt.cpt missing"

    exit 1
fi


if [[ ! -s npt.log ]] || \
   ! grep -q "Finished mdrun" npt.log
then

    echo
    echo "ERROR: NPT did not finish normally"

    exit 1
fi


# ============================================================
# STEP 4
# FEP production
# ============================================================

echo
echo "============================================================"
echo "STEP 4: FEP production"
echo "============================================================"

# ------------------------------------------------------------
# Case 1: Production already finished
# ------------------------------------------------------------
if [[ -s prod.log && \
      -s prod.gro && \
      -s dhdl.xvg ]] && \
   grep -q "Finished mdrun" prod.log
then

    echo
    echo "Production already completed."
    echo "Skipping production."

# ------------------------------------------------------------
# Case 2: Production interrupted -> resume
# ------------------------------------------------------------
elif [[ -s prod.cpt && -s prod.tpr ]]
then

    echo
    echo "Previous production run was interrupted."
    echo "$(pwd)/prod.cpt"
    echo
    echo "Resuming simulation..."

    ${GMX} mdrun \
        -deffnm prod \
        -cpi prod.cpt \
        -append \
        -ntomp "${OMP_NUM_THREADS}" \
        ${MDRUN_FEP_OPTIONS:-${MDRUN_MD_OPTIONS:-}}

# ------------------------------------------------------------
# Case 3: Production has not started -> start from completed NPT
# ------------------------------------------------------------
elif [[ -s npt.gro && -s npt.cpt ]]
then

    echo
    echo "Production has not started."
    echo "Starting production from NPT output."

    rm -f \
        prod.tpr \
        prod.log \
        prod.edr \
        prod.xtc \
        prod.trr \
        prod.gro \
        prod.cpt \
        dhdl.xvg

    ${GMX} grompp \
        -f prod.mdp \
        -c npt.gro \
        -t npt.cpt \
        -p "${TOP}" \
        -o prod.tpr \
        -maxwarn 1

    if [[ ! -s prod.tpr ]]; then

        echo
        echo "ERROR: prod.tpr was not generated"

        exit 1
    fi

    ${GMX} mdrun \
        -deffnm prod \
        -dhdl dhdl.xvg \
        -ntomp "${OMP_NUM_THREADS}" \
        ${MDRUN_FEP_OPTIONS:-${MDRUN_MD_OPTIONS:-}}

else

    echo
    echo "ERROR: Production cannot start."
    echo "NPT output is missing or incomplete."
    exit 1

fi

# ============================================================
# Production QC
# ============================================================

if [[ ! -s prod.log ]]; then

    echo
    echo "ERROR: prod.log missing"

    exit 1
fi


if ! grep -q "Finished mdrun" prod.log; then

    echo
    echo "ERROR: FEP production did not finish normally"

    exit 1
fi


if [[ ! -s prod.gro ]]; then

    echo
    echo "ERROR: prod.gro missing"

    exit 1
fi


if [[ ! -s dhdl.xvg ]]; then

    echo
    echo "ERROR: dhdl.xvg missing"

    exit 1
fi


# ============================================================
# Success
# ============================================================

echo
echo "============================================================"
echo "FEP window completed successfully"
echo "============================================================"


echo
echo "Leg:"
echo "    ${LEG}"

echo
echo "Replicate:"
echo "    ${REP}"

echo
echo "Lambda state:"
echo "    ${LAMBDA_STATE}"

echo
echo "Lambda:"
echo "    ${CURRENT_LAMBDA}"


echo
echo "Timestep:"
echo "    ${FEP_DT_PS} ps"


echo
echo "Stages:"
echo "    EM:    PASS"
echo "    NVT:   PASS"
echo "    NPT:   PASS"
echo "    PROD:  PASS"


echo
echo "Directory:"
echo "    ${WORKDIR}"


echo
echo "DHDL:"
echo "    ${WORKDIR}/dhdl.xvg"


echo
echo "Lambda schedule:"
echo "    ${SCHEDULE_FILE}"


echo
echo "============================================================"