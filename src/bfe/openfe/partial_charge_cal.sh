# Load/activate env
source ~/bin/myconda
conda activate openfe_m

module purge
module load CUDA/11.8.0
module load cuDNN/8.9.2/CUDA-11

sdf_path="/data/liuy48/openfe_m/simulation/rbfe/PDE4B/A33/inputs"
input_sdf=${sdf_path}/A33_v17_p_2.sdf
output_sdf=${sdf_path}/charged_A33_v17_p_2.sdf

openfe charge-molecules -M ${input_sdf} -o ${output_sdf} -n 4 -s /data/liuy48/openfe_m/bash/charge_settings.yaml --overwrite-charges