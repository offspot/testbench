import re
from ipaddress import IPv4Address, IPv4Network

import dns
import dns.query

from testbench.context import Context

RE_DNS_ANSWER = re.compile(
    r"^(?P<domain>.+)\. (?P<ttl>\d+) IN A (?P<dest_address>[0-9\.]+)"
)
logger = Context.get().logger


def verify_dns_for(
    source_addr: str, server: str, domain: str, dest_address: str
) -> bool:
    """Whether DNS query from source_addr via server for domain returns des_address"""

    query = dns.message.make_query(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]
        domain,
        dns.rdatatype.A,  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
    )
    resp = dns.query.udp(  # pyright: ignore[reportUnknownArgumentType]
        query,  # pyright: ignore[reportUnknownArgumentType]
        where=server,
        source=source_addr,
    )
    return resp.answer[0].to_text() == f"{domain}. 0 IN A {dest_address}"


def get_dns_answer_for(
    source_addr: IPv4Address, server: IPv4Address, domain: str
) -> IPv4Address | None:
    """IP address for requested domain"""
    query = dns.message.make_query(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]
        domain,
        dns.rdatatype.A,  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
    )
    resp = dns.query.udp(  # pyright: ignore[reportUnknownArgumentType]
        query,  # pyright: ignore[reportUnknownArgumentType]
        where=str(server),
        source=str(source_addr),
    )
    m = RE_DNS_ANSWER.match(resp.answer[0].to_text())
    if not m or m.groupdict()["domain"] != domain:
        return None
    return IPv4Address(m.groupdict()["dest_address"])


def verify_dns_within_for(
    source_addr: IPv4Address,
    server: IPv4Address,
    domain: str,
    dest_address: IPv4Address | None = None,
    dest_network: IPv4Network | None = None,
) -> bool:
    """Whether DNS query from source_addr via server for domain is dest_address

    or an IP within dest_network"""
    if not dest_address and not dest_network:
        raise OSError("dest_address or dest_network must be set")
    answer_dest_address = get_dns_answer_for(
        source_addr=source_addr, server=server, domain=domain
    )
    if not answer_dest_address:
        return False
    if dest_address:
        return answer_dest_address == dest_address
    if dest_network:
        return answer_dest_address in dest_network
    return False
