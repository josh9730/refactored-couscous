from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)
template = env.get_template("misc.txt.j2")

# with open("config.yaml") as file: 
#     interface_file = yaml.full_load(file)

open('output.txt', 'w').close()

file = open('output.txt', 'a')
file.write(template.render())
file.close()

