import yaml

with open('sites.yaml') as file:
    data = yaml.full_load(file)

print(data['ccc'])