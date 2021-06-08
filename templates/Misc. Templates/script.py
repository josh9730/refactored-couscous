from jinja2 import Environment, FileSystemLoader
import yaml

env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)
template_xr = env.get_template("xr-mpls.j2")
template_junos = env.get_template("junos-mpls.j2")

with open("data.yaml") as file: 
    data_file = yaml.full_load(file)

open('output.txt', 'w').close()
file = open('output.txt', 'a')

for i in data_file['routers']:

    if i['type'] == 'iosxr':
        file.write(template_xr.render(i))
    else:
        file.write(template_junos.render(i))

file.close()