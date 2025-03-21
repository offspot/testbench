from pydantic import BaseModel

from testbench.context import Context
from testbench.utils.wlan import get_wireless_devices

context = Context.get()
logger = context.logger


class SimpleWirelessDevice(BaseModel):
    ifname: str
    vendor: str
    hwaddr: str


class WirelessDevicesList(BaseModel):
    excluding_broadcom: bool
    excluding_ifnames: list[str]
    excluding_vendors: list[str]
    excluding_hwaddrs: list[str]
    count: int
    devices: list[SimpleWirelessDevice]


def get_all_wireless_devices(
    *,
    excluding_broadcom: bool,
    excluding_ifnames: list[str] | None = None,
    excluding_vendors: list[str] | None = None,
    excluding_hwaddrs: list[str] | None = None,
    max_devices: int,
) -> WirelessDevicesList:
    devices = get_wireless_devices(
        excluding_ifnames=excluding_ifnames or [],
        excluding_vendors=excluding_vendors or [],
        excluding_hwaddrs=excluding_hwaddrs or [],
        max_devices=max_devices,
    )

    return WirelessDevicesList(
        excluding_broadcom=excluding_broadcom,
        excluding_ifnames=excluding_ifnames or [],
        excluding_vendors=excluding_vendors or [],
        excluding_hwaddrs=excluding_hwaddrs or [],
        count=len(devices),
        devices=[
            SimpleWirelessDevice(
                ifname=ifname, hwaddr=device.hwaddr, vendor=device.vendor
            )
            for ifname, device in devices.items()
        ],
    )
