import json
from pathlib import Path


class ProjectManager:
    def __init__(self):
        self.project_file = None
        self.data = {
            "name": "",
            "working_directory": "",
            "settings": {},
        }

    def new_project(self, project_file, working_directory):
        project_file = Path(project_file)

        if project_file.suffix != ".afp":
            project_file = project_file.with_suffix(".afp")

        self.project_file = project_file

        self.data = {
            "name": project_file.stem,
            "working_directory": str(working_directory),
            "settings": {},
        }

        self.save()

    def open_project(self, project_file):
        project_file = Path(project_file)

        with open(project_file, "r") as f:
            self.data = json.load(f)

        self.project_file = project_file

        return self.data

    def save(self):
        if self.project_file is None:
            raise RuntimeError("No project file is currently open.")

        with open(self.project_file, "w") as f:
            json.dump(
                self.data,
                f,
                indent=4,
            )

    def save_as(self, project_file):
        project_file = Path(project_file)

        if project_file.suffix != ".afp":
            project_file = project_file.with_suffix(".afp")

        self.project_file = project_file
        self.data["name"] = project_file.stem

        self.save()