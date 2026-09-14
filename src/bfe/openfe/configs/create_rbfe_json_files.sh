#!/usr/bin/env bash

# Load/activate env
source ~/bin/myconda
conda activate openfe_m

module purge
module load CUDA/11.8.0
module load cuDNN/8.9.2/CUDA-11

JOB_DIR="$WORK_DIR/JOB_NAME"
CONF_DIR="$JOB_DIR/conf"
CONF_YAML="${CONF_DIR}/rbfe_conf.yaml"

WORKDIR=$(yq -r '.workdir' "${CONF_YAML}")
RESDIR=$(yq -r '.result_dir' "${CONF_YAML}")
JSONDIR=$(yq -r '.json_dir' "${CONF_YAML}")

mkdir -p "${WORKDIR}" "${RESDIR}" "${JSONDIR}"

BFE_PATH="$(python -c 'import bfe, pathlib; print(pathlib.Path(bfe.__file__).resolve().parent)')"

echo "$BFE_PATH"
SCRIPT_PATH="$BFE_PATH/openfe/rbfe_setup.py"

RUN_RBFE_SCRIPT="python $SCRIPT_PATH"

# Build command as array (safe for spaces)
CMD=(python "$SCRIPT_PATH" --conf_file "${CONF_YAML}")

# Run
echo "${CMD[@]}"
"${CMD[@]}"