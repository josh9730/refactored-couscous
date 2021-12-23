from atlassian import Confluence, Jira
from jinja2 import Environment, FileSystemLoader
import yaml
import keyring
from checks import *
from cerberus import Validator
import shutil
import os


class Utils:
    def __init__(self, _yaml_file, schema_type):
        """Pass yaml_file to check_yaml, and initialize variables"""

        self._schema_type = schema_type
        self.check_yaml(_yaml_file, self._schema_type)

        if any(v is not None for v in _yaml_file['login_vars'].values()):
            data = _yaml_file["login_vars"]

        else:
            try:
                self.path = _yaml_file["login_path"]
                with open(self.path, "r") as file:
                    data = yaml.safe_load(file)
                file.close()
                self.check_yaml(data, "vars")
            except:
                raise KeyError("Either 'path' or local variables must be defined")

        self.username = data["cas"]
        self.jira_url = data["jira_url"]
        self.confluence_url = data["confluence_url"]
        self.ic_url = _yaml_file.get("ic_url")

    def conf_login(self):
        password = keyring.get_password("cas", self.username)
        confluence = Confluence(
            url=self.confluence_url, username=self.username, password=password
        )
        return confluence

    def jira_login(self):
        password = keyring.get_password("cas", self.username)
        jira = Jira(url=self.jira_url, username=self.username, password=password)
        return jira

    def check_yaml(self, yaml_file, mop_type):
        """Pass supplied yaml through schema"""

        schema = eval(open(f"schemas/{mop_type}_schema.py", "r").read())

        v = Validator(schema, allow_unknown=True)
        v.validate(yaml_file)
        if v.errors:
            print(v.errors)
            exit(1)

    def move_yaml(self, _yaml_file, page_title):
        """Copy YAML to repo."""

        print(f'\tMoving YAML to storage: {_yaml_file["mop_repo"]}')
        page_title = page_title.replace(" ", "_")
        shutil.copy(
            f"{os.path.dirname(__file__)}/{self._schema_type}.yaml",
            f'{_yaml_file["mop_repo"]}{self._schema_type}/{page_title}.yaml',
        )


def yaml_defaults(_yaml_file, file_type):
    """Reset cd/mop.yaml files, keeping mop_repo and login_vars"""

    mop_repo = _yaml_file.get("mop_repo")
    path = _yaml_file.get("login_path")
    ic_url = _yaml_file.get("ic_url")
    yaml_vars = _yaml_file.get("login_vars")

    yaml_vars.update({"login_path": path})
    yaml_vars.update({"ic_url": ic_url})
    yaml_vars.update({"mop_repo": mop_repo})

    if yaml_vars["confluence_url"] == None:
        yaml_vars.update({"confluence_url": ""})
        yaml_vars.update({"jira_url": ""})
        yaml_vars.update({"cas": ""})

    env = Environment(
        loader=FileSystemLoader("defaults/"), trim_blocks=True, lstrip_blocks=True
    )
    template = env.get_template(f"{file_type}_defaults.j2")
    output = template.render(yaml_vars)

    with open(f"{file_type}.yaml", "w") as file:
        file.write(output)
    file.close()
