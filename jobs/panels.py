from nautobot.dcim.models import (
    Device,
    DeviceRole,
    DeviceType,
    DeviceBay,
    Site,
    Rack,
    FrontPort,
    RearPort,
    Cable,
    Interface,
)
from nautobot.tenancy.models import Tenant
from nautobot.extras.models import Status, Tag
from nautobot.extras.jobs import *

name = "Patch Panel Jobs"


class CreatePanelPair(Job):
    """Maintained By: Josh Dickman (jdickman@cenic.org)
    Use flake8 & black for formatting
    """

    class Meta:
        name = "Paired Patch Panel Creation"
        description = "Create pair of FS breakout panels with MPO connectivity"

    site_name = ObjectVar(label="Site Name", model=Site)
    rack_1 = ObjectVar(
        label="Rack A",
        description="Rack ID where the Type AF cassette is installed",
        model=Rack,
        query_params={"site_id": "$site_name"},
    )
    rack_1_position = IntegerVar(
        label="Rack A Position",
        description="Lowest RU filled by the new panel",
        min_value=1,
        max_value=40,
    )
    facility_1_id = StringVar(
        label="Panel A Facility ID",
        description="Facility name for panel",
        required=False,
    )
    rack_2 = ObjectVar(
        label="Rack B",
        description="Rack ID where the Type A cassette is installed",
        model=Rack,
        query_params={"site_id": "$site_name"},
    )
    rack_2_position = IntegerVar(
        label="Rack B Position",
        description="Lowest RU filled by the new panel",
        min_value=1,
        max_value=40,
    )
    facility_2_id = StringVar(
        label="Panel B Facility ID",
        description="Facility name for panel",
        required=False,
    )
    clr = IntegerVar(
        label="CLR",
        description="CLR or label for MPO-MPO trunk connection. If blank, a default will be created.",
        required=False,
    )
    FIBER_CHOICES = (("", ""), ("mmf", "Multimode Fiber"), ("smf", "Singlemode Fiber"))
    fiber_type = ChoiceVar(choices=FIBER_CHOICES)

    def run(self, data, commit):

        enclosure = "FHD Enclosure, Sliding"
        cassette_list = []
        for i in range(1, 3):

            # Create panel enclosures, defaults to Sliding
            rack = data[f"rack_{i}"].name.split(" (")[0]
            tenant = Tenant.objects.get(name="CENIC Hubsite")
            panel = Device(
                site=data["site_name"],
                rack=data[f"rack_{i}"],
                position=data[f"rack_{i}_position"],
                face="front",
                device_type=DeviceType.objects.get(model=enclosure),
                device_role=DeviceRole.objects.get(name="Hubsite - Patch Panels"),
                name=f'PP--{data["site_name"]}--{rack}--U{data[f"rack_{i}_position"]}',
                status=Status.objects.get(slug="active"),
                _custom_field_data={"facility_device_id": data[f"facility_{i}_id"]},
                comments=f"**Patch Panel enclosure for cassettes. To check ports, see 'Device Bays' and select the desired Cassette.**",
                tenant=tenant,
            )
            panel.validated_save()
            self.log_success(
                obj=panel,
                message=f'Created new panel: `{panel.name}`.\n\nSite: {data["site_name"]}\nRack: {rack}\nPosition: {data[f"rack_{i}_position"]}',
            )

            # Create Cassettes
            if data["fiber_type"] == "mmf":
                cassette_model = "FHD MPO-24/LC OM4 Cassette Type A"
            else:
                cassette_model = "FHD MPO-24/LC OS2 Cassette Type A"
            if i == 1:
                cassette_model = cassette_model + "F"
            cassette_type = cassette_model.split(" ")[-1:]

            cassette = Device(
                site=data["site_name"],
                rack=data[f"rack_{i}"],
                device_type=DeviceType.objects.get(model=cassette_model),
                device_role=DeviceRole.objects.get(name="Hubsite - Patch Panel Cassettes"),
                name=f'(C-{data["fiber_type"].upper()}){panel.name}--S1',
                status=Status.objects.get(slug="active"),
                tenant=tenant,
                tags=Tag.objects.get(name="Cassette"),
                comments=f'{data["fiber_type"].upper()} MPO-LC Breakout Cassette, Type {cassette_type[0]}'
            )
            cassette.validated_save()
            self.log_success(
                obj=cassette, message=f"Created new cassette: `{cassette.name}`."
            )
            cassette_list.append(cassette.name)

            # Assign Cassettes to enclosure
            assign_bay = DeviceBay.objects.create(
                device=Device.objects.get(name=panel.name),
                name="Slot 1",
                installed_device=Device.objects.get(name=cassette.name),
            )
            assign_bay.validated_save()
            self.log_success(
                obj=assign_bay,
                message=f"Added `{cassette.name}` to `{panel.name}` in Device Bay Slot 1.",
            )

        # Create MPO - MPO cable between the two cassettes.
        cassette_a_uuid = Device.objects.get(name=cassette_list[0]).id
        cassette_b_uuid = Device.objects.get(name=cassette_list[1]).id
        if not data["clr"]:
            clr = f"{cassette_list[0]}--RP1 <--> {cassette_list[1]}--RP1"
        else:
            clr = data["clr"]
        mpo = Cable(
            termination_a_id=RearPort.objects.get(device_id=cassette_a_uuid).id,
            termination_b_id=RearPort.objects.get(device_id=cassette_b_uuid).id,
            termination_a_type_id=50,
            termination_b_type_id=50,
            status=Status.objects.get(slug="connected"),
            type=data["fiber_type"],
            label=clr,
        )
        mpo.validated_save()
        self.log_success(
            obj=mpo,
            message=f"Created new MPO between `{cassette_list[0]}` and `{cassette_list[0]}`",
        )


class JumperCassette(Job):

    class Meta:
        name = "Paired Cassette Jumper Run"
        description = "Run jumpers across two pairs of MPO-LC cassette panels. This is for connecting one device to another via a 'hub' rack. See Confluence patch panel docs for details."

    site_name = ObjectVar(label='Site Name', model=Site)
    rack_1 = ObjectVar(
        label = 'A-Side Rack',
        model = Rack,
        query_params = {
            'site_id': '$site_name'
        }
    )
    device_1 = ObjectVar(
        label = 'A-Side Device',
        model = Device,
        query_params = {
            'rack_id': '$rack_1'
        }
    )
    interface_1 = ObjectVar(
        label = 'A-Side Interface',
        model = Interface,
        query_params = {
            'device_id': '$device_1'
        }
    )
    cassette_1 = ObjectVar(
        label = 'A-Side Cassette',
        model = Device,
        query_params= {
            'rack_id': '$rack_1',
            'role_id': DeviceRole.objects.get(name="Hubsite - Patch Panel Cassettes").id,
        }
    )
    front_port_1 = ObjectVar(
       label = 'A-Side Cassette Port',
       model = FrontPort,
       query_params = {
           'device_id': '$cassette_1'
       }
    )
    rack_2 = ObjectVar(
        label = 'Z-Side Rack',
        model = Rack,
        query_params = {
            'site_id': '$site_name'
        }
    )
    cassette_2 = ObjectVar(
        label = 'Z-Side Cassette',
        model = Device,
        query_params= {
            'rack_id': '$rack_2',
            'role_id': DeviceRole.objects.get(name="Hubsite - Patch Panel Cassettes").id,
        }
    )
    front_port_2 = ObjectVar(
       label = 'Z-Side Cassette Port',
       model = FrontPort,
       query_params = {
           'device_id': '$cassette_2'
       }
    )
    device_2 = ObjectVar(
        label = 'Z-Side Device',
        model = Device,
        query_params = {
            'rack_id': '$rack_2'
        }
    )
    interface_2 = ObjectVar(
        label = 'Z-Side Interface',
        model = Interface,
        query_params = {
            'device_id': '$device_2'
        }
    )
    clr = IntegerVar(
        label = 'CLR',
        description = 'CLR or label for the LC jumpers'
    )
    # get hub ports from the far end cassette ports

    def run(self, data, commit):

        if 'SMF' in data['cassette_1'].name:
            fiber_type = 'smf'
        else:
            fiber_type = 'mmf'

        for i in range(1,3):

            interface_id = Interface.objects.get(name=data[f"interface_{i}"], device=data[f"device_{i}""]).id
            port_id = FrontPort.objects.get(name=data[f"front_port_{i}"], device=data[f"cassette_{i}"]).id
            cable = Cable(
                termination_a_id = interface_id,
                termination_b_id = port_id,
                termination_a_type_id = 37,
                termination_b_type_id = 35,
                status=Status.objects.get(slug="connected"),
                type = fiber_type,
                label = data['clr']
            )
            cable.validated_save()
            # dev_name = data['device_1'].name

            # self.log_success(
            #     obj=cable,
            #     message=f"Created new jumper between `{dev_name}`,
            # )
