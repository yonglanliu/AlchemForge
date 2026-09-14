from pathlib import Path

CURRENT_DIR = Path(__file__).parent.resolve()

def save_yaml(data, file_path):
    import yaml
    file_path = Path(file_path)
    with open(file_path, 'w') as f:
        yaml.safe_dump(data, f)