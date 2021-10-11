from nautobot.dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site, Rack
from nautobot.extras.models import Status
from nautobot.extras.jobs import *


class CreatePanelPair(Job):

    class Meta:
        name = 'Create Patch Panel Pair'
        description: 'Create a pair of patch panels between two racks.'
        # field_order = ['site_name', 'chassis', 'cassette_a', 'cassette_z']
        # commit_default = False

    site_name = ObjectVar(
        site = Site
    )
    manufacturer = ObjectVar(
        model = Manufacturer,
    )
    chassis = ObjectVar(
        model = DeviceType,
        query_params = {
            'manufacturer_id': '$manufacturer'
        }
    )
    rack_1 = ObjectVar(
        model = Rack,
        query_params = {
            'site': '$site'
        }
    )
    rack_a_pos = IntegerVar(
        min_value = 1,
        max_value = 40,
        description = 'Lowest RU filled by the new panel'
    )
    # cassette_a = ObjectVar(
    #     model = DeviceType,
    #     query_params = {
    #         'manufacturer_id': '$manufacturer'
    #     }
    # )
    # rack_b = ObjectVar(
    #     model = Rack,
    #     query_params = {
    #         'site': '$site'
    #     }
    # )
    # cassette_z = ObjectVar(
    #     model = DeviceType,
    #     query_params = {
    #         'manufacturer_id': '$manufacturer'
    #     }
    # )

    def run(self, data, commit):

        site_name = data['site']['name']
        rack_a = data['rack_a']['name']

        panel_a = Device(
            device_type = data['chassis'],
            name = f'{site_name}--{rack_a}--1',
            status = Status.objects.get(slug='active'),
            site = data['site'],
            device_role = DeviceRole.objects.get(name='Patch Panel'),
            position = data['rack_a_pos'],
            face = 'front'
        )

        panel_a.validated_save()
        self.log_success(obj=panel_a, message='Created new patch panel')

        # output = [
        #     'name', 'device_role', 'rack','site', 'position', 'rack_face', 'status'
        # ]

