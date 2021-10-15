from nautobot.dcim.models import (
    Device,
    DeviceRole,
    DeviceType,
    DeviceBay,
    Site,
    Rack,
    RearPort,
    Cable,
)
from nautobot.tenancy.models import Tenant
from nautobot.extras.models import Status
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
    Fiber_Type = ChoiceVar(choices=FIBER_CHOICES)

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
            if data["Fiber_Type"] == "mmf":
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
                device_role=DeviceRole.objects.get(name="Hubsite - Patch Panels"),
                name=f"(C-{cassette_type[0]}){panel.name}--S1",
                status=Status.objects.get(slug="active"),
                tenant=tenant,
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
            type=data["Fiber_Type"],
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
        label = 'Rack A',
        model = Rack,
        query_params = {
            'site_id': '$site_name'
        }
    )
    tenant = Tenant.objects.get(name="CENIC Hubsite").id
    panel_role = DeviceRole.objects.get(name="Hubsite - Patch Panels").id
    panel_1 = ObjectVar(
        label = 'Cassette A',
        model = Device,
        query_params= {
            'rack_id': '$rack_1',
            # 'tenant_id': tenant,
            'device_role_id': panel_role
        }
    )
    # cassette_1 = ObjectVar(
    #     label = 'Cassette A',
    #     model = Device,
    #     query_params = {
            
    #     }
    # )
    #port_1 = ChoiceVar(
    #    label = 'Port',
    #    description = 'Port in Cassette ID A',
    #    query_params = -ports free in cassette??
    #)
    # cassette_1_port = IntegerVar(
    #     label = 'Port Number'
    # )
    # device_1_port = Inte
    # rack_2 = ObjectVar(
    #     label = 'Rack B',
    #     model = Rack,
    #     query_params = {
    #         'site_id': '$site_name'
    #     }
    # )
    # cassette_2 = ObjectVar(
    #     label = 'Cassette ID B',
    #     description = 'Cassette ID for Rack B',
    #     query_params = {
    #         'rack_id': '$rack_2'
    #     }
    # )
    # clr = IntegerVar(
    #     label = 'CLR',
    #     description = 'CLR or label for the LC jumpers'
    # )
    # get fiber type from cassette
    # get hub ports from the far end cassette ports
    # get list of available interfaces per device
    # get list of availabe front ports per cassette

    def run(self, data, commit):


        output = data['cassette_1']

        return output
