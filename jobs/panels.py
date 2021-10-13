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
        label="Rack B Position",
        description="Lowest RU filled by the new panel",
        min_value=1,
        max_value=40,
    )
    vendor_1_id = StringVar(
        label="Rack A Vendor ID", description="Vendor name for panel", required=False
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
    vendor_2_id = StringVar(
        label="Rack B Vendor ID", description="Vendor name for panel", required=False
    )
    clr = IntegerVar(
        label="CLR",
        description="CLR or label for MPO-MPO trunk connection",
    )
    FIBER_CHOICES = (
        ("",""),
        ("mmf", "Multimode Fiber"),
        ("smf", "Singlemode Fiber")
    )
    Fiber_Type = ChoiceVar(choices=FIBER_CHOICES)

    def run(self, data, commit):

        enclosure = "FHD Enclosure, Sliding"
        cassette_list = []
        for i in range(1, 3):

            # Create panel enclosures, defaults to Sliding
            panel = Device(
                site=data["site_name"],
                rack=data[f"rack_{i}"],
                position=data[f"rack_{i}_position"],
                face="front",
                device_type=DeviceType.objects.get(model=enclosure),
                device_role=DeviceRole.objects.get(name="Hubsite - Patch Panels"),
                name=f'PP--{data["site_name"]}--{data[f"rack_{i}"]}--U{data[f"rack_{i}_position"]}',
                status=Status.objects.get(slug="active"),
                _custom_field_data={"vendor_device": data[f"vendor_{i}_id"]},
            )
            panel.validated_save()
            self.log_success(
                obj=panel,
                message=f'Created new panel: `{panel.name}`.\n\nSite: {data["site_name"]}\nRack: {data[f"rack_{i}"]}\nPosition: {data[f"rack_{i}_position"]}',
            )

            # Create Cassettes
            if data["Fiber_Type"] == "mmf":
                cassette_type = "FHD MPO-24/LC OM4 Cassette Type A"
            else:
                cassette_type = "FHD MPO-24/LC OS2 Cassette Type A"
            if i == 1:
                cassette_type = cassette_type + "F"

            cassette = Device(
                site=data["site_name"],
                rack=data[f"rack_{i}"],
                device_type=DeviceType.objects.get(model=cassette_type),
                device_role=DeviceRole.objects.get(name="Hubsite - Patch Panels"),
                name=f"(C){panel.name}--S1",
                status=Status.objects.get(slug="active"),
                # parent_device = Device.objects.get(name=panel.name)
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
        mpo = Cable(
            termination_a_id=RearPort.objects.get(device_id=cassette_a_uuid).id,
            termination_b_id=RearPort.objects.get(device_id=cassette_b_uuid).id,
            termination_a_type_id=50,
            termination_b_type_id=50,
            status=Status.objects.get(slug="connected"),
            type=data["Fiber_Type"],
            label="CLR-" + str(data["clr"]),
        )
        mpo.validated_save()
        self.log_success(
            obj=mpo,
            message=f"Created new MPO between `{cassette_list[0]}` and `{cassette_list[0]}`",
        )


class JumperCassette(Job):

    class Meta:
        name = 'Paired Cassette Jumper Run'
        description = 'Run jumpers across two pairs of MPO-LC cassette panels. This is for connecting one device to another via a 'hub' rack. See Confluence patch panel docs for details.'
        
    site_name = ObjectVar(label='Site Name', model=Site)
    rack_1 = ObjectVar(
        label = 'Rack A',
        model = Rack,
        query_params = {
            'site_id': '#site_name'
        }
    )
    cassette_1 = ObjectVar(
        label = 'Cassette ID A',
        description = 'Cassette ID for Rack A',
        query_params = {
            'rack_id': '$rack_1'
        }
    )
    device_1 = ObjectVar(
        label = 'Device A',
        description = 'Device for jumper termination in Rack A',
        query_params = {
            'rack_id': '$rack_1'
        }
    )
    
    #port_1 = ChoiceVar(
    #    label = 'Port',
    #    description = 'Port in Cassette ID A',
    #    query_params = -ports free in cassette??
    #)
    cassette_1_port = IntegerVar(
        label = 'Port Number'
    )
    device_1_port = Inte
    rack_2 = ObjectVar(
        label = 'Rack B',
        model = Rack,
        query_params = {
            'site_id': '#site_name'
        }
    )
    cassette_2 = ObjectVar(
        label = 'Cassette ID B',
        description = 'Cassette ID for Rack B',
        query_params = {
            'rack_id': '$rack_2'
        }
    )
    clr = IntegerVar(
        label = 'CLR',
        description = 'CLR or label for the LC jumpers'
    )
    # get fiber type from cassette
    # get hub ports from the far end cassette ports
    # get list of available interfaces per device
    # get list of availabe front ports per cassette
         
        
        
        
        
        
        
        