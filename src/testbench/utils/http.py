import socket
from http import HTTPStatus
from ipaddress import IPv4Address

# from urllib3 import PoolManager
from urllib3.contrib.resolver.protocols import BaseResolver, ProtocolResolver
from urllib3.poolmanager import PoolManager

from testbench.utils.dns import get_dns_answer_for
from testbench.utils.wlan import WirelessDevice

DEFAULT_TIMEOUT = 5


class DeviceResolver(BaseResolver):
    protocol = ProtocolResolver.MANUAL

    def __init__(self, device: WirelessDevice, dns_server: IPv4Address):
        super().__init__(server=str(dns_server), port=None)
        self.device = device
        self.dns_server = dns_server

    def getaddrinfo(
        self,
        host: bytes | str | None,
        port: str | int | None,
        family: socket.AddressFamily,
        type: socket.SocketKind,  # noqa: A002
        proto: int = 0,  # noqa: ARG002
        flags: int = 0,  # noqa: ARG002
        *,
        quic_upgrade_via_dns_rr: bool = False,  # noqa: ARG002
    ) -> list[
        tuple[
            socket.AddressFamily,
            socket.SocketKind,
            int,
            str,
            tuple[str, int] | tuple[str, int, int, int],
        ]
    ]:
        if host is None:
            host = "localhost"

        if port is None:
            port = 0
        if isinstance(port, str):
            port = int(port)
        if port < 0:
            raise socket.gaierror("Servname not supported for ai_socktype")
        if family == socket.AF_INET6:
            raise socket.gaierror("Address family for hostname not supported")

        dest_address: IPv4Address | None = get_dns_answer_for(
            source_addr=(
                self.device.ip4.address if self.device.ip4 else IPv4Address("1.1.1.1")
            ),
            server=self.dns_server,
            domain=host.decode("utf-8") if isinstance(host, bytes) else str(host),
        )
        host_addr: str = str(dest_address)
        return [
            (
                socket.AF_INET,
                type,
                6,
                "",
                (host_addr, port),
            )
        ]

    def close(self) -> None:
        pass  # no-op

    def is_available(self) -> bool:
        return True


def get_session_for(device: WirelessDevice, dns_server: IPv4Address) -> PoolManager:
    return PoolManager(resolver=DeviceResolver(device=device, dns_server=dns_server))


def assert_url_contains(
    device: WirelessDevice, dns_server: IPv4Address, url: str, title: str
) -> bool:
    session = get_session_for(device=device, dns_server=dns_server)
    resp = session.request("GET", url=url, timeout=DEFAULT_TIMEOUT, redirect=False)
    return resp.status == HTTPStatus.OK and title in resp.data.decode("utf-8")
