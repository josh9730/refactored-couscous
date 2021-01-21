from jinja2 import Environment, FileSystemLoader
import yaml

env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)
template = env.get_template("jumper.j2")

with open("jumper.yaml") as file: 
    interface_file = yaml.full_load(file)

open('output.txt', 'w').close()

file = open('output.txt', 'a')
file.write(template.render(interface_file))
file.close()
