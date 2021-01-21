from jinja2 import Environment, FileSystemLoader
import yaml

env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)
template = env.get_template("migration.txt.j2")

with open("migration_yaml/wave5.yaml") as file: 
    interface_file = yaml.full_load(file)

open('migration_output.txt', 'w').close()

file = open('migration_output.txt', 'a')
file.write(template.render(interface_file))
file.close()
