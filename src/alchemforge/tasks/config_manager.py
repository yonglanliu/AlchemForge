from importlib.resources import files
from pathlib import Path
import shutil
import tomllib

import tomli_w


class TaskConfigManager:

    TEMPLATES = {
        "system_builder": "system_builder.toml",
        "ligand_mapping": "ligand_mapping.toml",
        "rbfe": "rbfe_setup.toml",
        "equilibration": "equilibration.toml",
        "production": "production.toml",
        "analysis": "analysis.toml",
    }

    @classmethod
    def get_template(cls, task_type):
        try:
            filename = cls.TEMPLATES[task_type]
        except KeyError:
            raise ValueError(
                f"Unknown task type: {task_type}"
            )

        return files("alchemforge.configs").joinpath(
            filename
        )

    @classmethod
    def create_task_config(
        cls,
        task_type,
        task_directory,
    ):
        """
        Copy the default configuration into a task directory.
        """

        task_directory = Path(task_directory)
        task_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = task_directory / "config.toml"

        template = cls.get_template(task_type)

        with template.open("rb") as src:
            with destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)

        return destination

    @staticmethod
    def load(config_file):
        config_file = Path(config_file)

        with config_file.open("rb") as f:
            return tomllib.load(f)

    @staticmethod
    def save(config_file, data):
        config_file = Path(config_file)

        with config_file.open("wb") as f:
            tomli_w.dump(data, f)