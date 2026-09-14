from pathlib import Path

CURRENT_DIR = Path(__file__).parent.resolve()
RBFE_CONFIG_PATH = CURRENT_DIR / "../configs/rbfe_conf.yaml"
SEPTOP_CONFIG_PATH = CURRENT_DIR / "../configs/septop_conf.yaml"
ABFE_CONFIG_PATH = CURRENT_DIR / "../configs/abfe_conf.yaml"

def load_yaml(file_path):
    import yaml
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"YAML file not found: {file_path}")
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def load_rbfe_config(RBFE_CONFIG_PATH=RBFE_CONFIG_PATH):
    return load_yaml(RBFE_CONFIG_PATH)

def load_septop_config(SEPTOP_CONFIG_PATH=SEPTOP_CONFIG_PATH):
    return load_yaml(SEPTOP_CONFIG_PATH)

def load_abfe_config(ABFE_CONFIG_PATH=ABFE_CONFIG_PATH):
    return load_yaml(ABFE_CONFIG_PATH)