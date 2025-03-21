import datetime
import time
from abc import ABC
from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    wait,
)
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from queue import Empty, Queue
from typing import Any, NamedTuple

from testbench.context import Context
from testbench.utils.dns import verify_dns_for, verify_dns_within_for
from testbench.utils.http import assert_url_contains
from testbench.utils.wlan import (
    WirelessDevice,
    connect_device,
    ping_host,
)

context = Context.get()
logger = context.logger


@dataclass
class IntegrationTestResult:
    name: str
    on: datetime.datetime
    ifname: str
    params: dict[str, Any]
    succeeded: bool
    feedback: str

    def __bool__(self) -> bool:
        return self.succeeded

    @classmethod
    def using(
        cls,
        *,
        succeeded: bool,
        device: WirelessDevice,
        params: dict[str, Any],
        feedback: str = "",
        on: datetime.datetime | None = None,
        name: str | None = None,
    ) -> "IntegrationTestResult":
        if on is None:
            on = datetime.datetime.now(datetime.UTC)
        if name is None:
            name = cls.__name__
        return cls(
            name=name,
            on=on,
            ifname=device.ifname,
            params=params,
            succeeded=succeeded,
            feedback=feedback,
        )


class DNSQuery(NamedTuple):
    domain: str
    expected: str


class IntegrationTest(ABC):
    name: str
    # /!\ you must define your params using annotations

    def __init__(self, device: WirelessDevice, **kwargs: dict[str, Any]) -> None:
        super().__init__()
        self.device = device
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __str__(self) -> str:
        return self.name

    def run(self) -> IntegrationTestResult: ...

    def get_params(self) -> dict[str, Any]:
        annotations = {
            key: value
            for key, value in type(self).__dict__.get("__annotations__", {}).items()
            if key not in ("name",)
        }
        return {key: getattr(self, key) for key in annotations}

    def get_result(
        self, *, succeeded: bool, feedback: str = ""
    ) -> IntegrationTestResult:
        return IntegrationTestResult(
            succeeded=succeeded,
            ifname=self.device.ifname,
            feedback=feedback,
            name=str(self),
            params=self.get_params(),
            on=datetime.datetime.now(datetime.UTC),
        )


class WiFiConnectionTest(IntegrationTest):
    name: str = "Can connect"

    ssid: str
    passphrase: str

    def run(self) -> IntegrationTestResult:
        logger.debug(f"Connecting to {self.ssid} using {self.device.ifname}")
        ps = connect_device(
            ifname=self.device.ifname, ssid=self.ssid, passphrase=self.passphrase
        )
        self.device.refresh()
        return self.get_result(
            succeeded=ps.returncode == 0,
            feedback=("" if ps.returncode == 0 else f"{ps.returncode}: {ps.stdout}"),
        )


def retrieve_iplink(device: WirelessDevice, timeout: int | None = None) -> bool:
    """await a maximum of timeout seconds to get an IP link (assuming post-connect)"""
    if timeout is None:
        timeout = context.dhcp_timeout
    end = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=timeout)
    while datetime.datetime.now(datetime.UTC) <= end:
        device.refresh()
        if device.ip4 is not None:
            return True
        time.sleep(1)
    device.refresh()
    return bool(device.ip4)


class HasExpectedAddressTest(IntegrationTest):
    name: str = "Valid IP"

    address_network: IPv4Network
    dhcp_timeout: int

    def run(self) -> IntegrationTestResult:
        is_valid = (
            retrieve_iplink(device=self.device, timeout=self.dhcp_timeout)
            and bool(self.device.ip4)
            and self.device.ip4.address in self.address_network
        )
        return self.get_result(succeeded=is_valid, feedback="")


class HasExpectedGatewayTest(IntegrationTest):
    name: str = "Expected Gateway"

    gateway_address: IPv4Address

    def run(self) -> IntegrationTestResult:
        is_valid = (
            bool(self.device.ip4) and self.device.ip4.gateway == self.gateway_address
        )
        return self.get_result(succeeded=is_valid, feedback="")


class HasExpectedDNSTest(IntegrationTest):
    name: str = "Expected DNS"

    dns_address: IPv4Address

    def run(self) -> IntegrationTestResult:
        is_valid = bool(self.device.ip4) and self.device.ip4.dns == self.dns_address
        return self.get_result(succeeded=is_valid, feedback="")


class CanPingTest(IntegrationTest):
    name: str = "Can Ping"

    ping_address: IPv4Address

    def run(self) -> IntegrationTestResult:
        success, output = ping_host(self.device.ifname, str(self.ping_address))
        return self.get_result(succeeded=success, feedback=output)


class ResolvesFQDNProperlyTest(IntegrationTest):
    name: str = "DNS"

    fqdn: str
    fqdn_answer: str

    def run(self) -> IntegrationTestResult:
        is_valid = verify_dns_for(
            source_addr=str(self.device.ip4link.address),
            server=str(self.device.ip4link.dns),
            domain=self.fqdn,
            dest_address=self.fqdn_answer,
        )
        return self.get_result(succeeded=is_valid, feedback=self.fqdn_answer)

    def __str__(self) -> str:
        return f"DNS {self.fqdn}"


class ResolvesServiceDomainProperlyTest(IntegrationTest):
    name: str = "DNS"

    svc_fqdn: str
    svc_fqdn_answer: str

    def run(self) -> IntegrationTestResult:
        is_valid = verify_dns_for(
            source_addr=str(self.device.ip4link.address),
            server=str(self.device.ip4link.dns),
            domain=self.svc_fqdn,
            dest_address=self.svc_fqdn_answer,
        )
        return self.get_result(succeeded=is_valid, feedback=self.svc_fqdn_answer)

    def __str__(self) -> str:
        return f"DNS {self.svc_fqdn}"


class ResolvesExternalDomainProperlyTest(IntegrationTest):
    name: str = "DNS"

    external_fqdn: str
    external_fqdn_answer: str

    def run(self) -> IntegrationTestResult:
        is_valid = verify_dns_for(
            source_addr=str(self.device.ip4link.address),
            server=str(self.device.ip4link.dns),
            domain=self.external_fqdn,
            dest_address=self.external_fqdn_answer,
        )
        return self.get_result(succeeded=is_valid, feedback=self.external_fqdn_answer)

    def __str__(self) -> str:
        return f"DNS {self.external_fqdn}"


class ResolvesExternalDomainOnlineTest(IntegrationTest):
    name: str = "DNS 🌐"

    external_fqdn: str
    external_fqdn_answer_network: IPv4Network

    def run(self) -> IntegrationTestResult:
        is_valid = verify_dns_within_for(
            source_addr=self.device.ip4link.address,
            server=self.device.ip4link.dns or IPv4Address("1.1.1.1"),
            domain=self.external_fqdn,
            dest_network=self.external_fqdn_answer_network,
        )
        return self.get_result(
            succeeded=is_valid, feedback=str(self.external_fqdn_answer_network)
        )

    def __str__(self) -> str:
        return f"DNS 🌐 {self.external_fqdn}"


class HTTPGetDashboardTest(IntegrationTest):
    name: str = "HTTP Dashboard"

    fqdn: str
    dns_address: IPv4Address

    def run(self) -> IntegrationTestResult:
        return self.get_result(
            succeeded=assert_url_contains(
                device=self.device,
                dns_server=self.dns_address,
                url=f"http://{self.fqdn}/",
                title="<title>Kiwix Hotspot</title>",
            ),
            feedback=str(self.fqdn),
        )


class HTTPGetZimManagerTest(IntegrationTest):
    name: str = "HTTP zim-manager"

    zim_manager_fqdn: str
    dns_address: IPv4Address

    def run(self) -> IntegrationTestResult:
        return self.get_result(
            succeeded=assert_url_contains(
                device=self.device,
                dns_server=self.dns_address,
                url=f"http://{self.zim_manager_fqdn}/",
                title="<title>File Manager</title>",
            ),
            feedback=str(self.zim_manager_fqdn),
        )


def get_tests_collection(*, assume_online: bool) -> list[type[IntegrationTest]]:
    tests: list[type[IntegrationTest]] = [
        WiFiConnectionTest,
        HasExpectedAddressTest,
        HasExpectedGatewayTest,
        HasExpectedDNSTest,
        CanPingTest,
        ResolvesFQDNProperlyTest,
        ResolvesServiceDomainProperlyTest,
    ]
    http_tests: list[type[IntegrationTest]] = [
        HTTPGetDashboardTest,
        HTTPGetZimManagerTest,
    ]
    offline_tests: list[type[IntegrationTest]] = [ResolvesExternalDomainProperlyTest]
    online_tests: list[type[IntegrationTest]] = [ResolvesExternalDomainOnlineTest]
    tests.extend(online_tests if assume_online else offline_tests)
    tests.extend(http_tests)
    return tests


def get_test_params(
    test: type[IntegrationTest], all_params: dict[str, Any]
) -> dict[str, Any]:
    annotations = {
        key: value
        for key, value in test.__dict__.get("__annotations__", {}).items()
        if key not in ("name",)
    }
    for param_name, param_type in annotations.items():
        if not isinstance(all_params.get(param_name), param_type):
            raise ValueError(
                f"{test.name} param `{param_name}` must be `{param_type}`"
                f", not `{type(all_params.get(param_name))}`"
            )
    return {
        key: value for key, value in all_params.items() if key in annotations.keys()
    }


def run_for_ifname(
    collection: list[type[IntegrationTest]],
    device: WirelessDevice,
    all_params: dict[str, Any],
    stack: Queue[IntegrationTestResult],
) -> None:
    skip: bool = False
    for test_cls in collection:
        params = get_test_params(test_cls, all_params)
        test = test_cls(device, **params)
        if skip:
            stack.put(
                item=IntegrationTestResult.using(
                    succeeded=False,
                    device=device,
                    params=params,
                    feedback="Skipped",
                    name=test_cls.name,
                )
            )
            continue
        try:
            res = test.run()
        except Exception as exc:
            skip = True
            res = IntegrationTestResult.using(
                succeeded=False,
                device=device,
                params=params,
                feedback=str(exc),
                name=test_cls.name,
            )
        finally:
            stack.put(item=res)  # pyright: ignore [reportPossiblyUnboundVariable]


class IntegrationTestsRunner:
    """runs integration tests outside the main loop

    - allows UI to query progress
    - allows tests to be run concurrently (per device)
    - records results and return them on finish
    """

    def __init__(
        self,
        devices: list[WirelessDevice],
        collection: list[type[IntegrationTest]],
        params: dict[str, Any],
    ):
        self.running: bool = False

        self.devices = devices
        self.collection = collection
        self.all_params = params

        self.nb_devices = len(devices)
        self.nb_test_per_device = len(self.collection)
        self.nb_tests = self.nb_devices * self.nb_test_per_device
        self.nb_sucessful_tests = 0
        self.nb_failed_tests = 0

        # temp queue to store results as they are produced
        self.all_results: Queue[IntegrationTestResult] = Queue(maxsize=self.nb_tests)

        # map of results grouped by ifname then maped from test-name to result
        self.results: dict[str, dict[str, IntegrationTestResult]] = {
            device.ifname: {} for device in self.devices
        }

        self.executor: ThreadPoolExecutor
        # tmp list of future to be able to query the executor
        self.futures: list[Future[None]] = []
        self.started_on = self.ended_on = datetime.datetime.now(datetime.UTC)

    def start(self):
        self.running = True
        self.started_on = datetime.datetime.now(datetime.UTC)

        # use one worker per device
        # only submit one task per device.
        # a task runs all the tests over that device as those have to follow one another
        self.executor = ThreadPoolExecutor(max_workers=len(self.devices))
        for device in self.devices:
            self.futures.append(
                self.executor.submit(
                    run_for_ifname,
                    collection=self.collection,
                    all_params=self.all_params,
                    device=device,
                    stack=self.all_results,
                )
            )

    def tick(self, timeout: int | float | None = None) -> None:
        """query status of runner"""
        # consume and record all pending results from queue
        while True:
            try:
                self.record_result(self.all_results.get(block=False))
            except Empty:
                break
            else:
                self.all_results.task_done()

        # consume done futures from executor (done futures ~= a device)
        # in order to clean up the futures list
        try:
            done, _ = wait(self.futures, timeout=timeout, return_when=FIRST_COMPLETED)
            for future in done:
                self.futures.remove(future)
        except TimeoutError:
            return None
        finally:

            # an empty futures list means we are done processing
            if not self.futures:
                self.running = False
                self.ended_on = datetime.datetime.now(datetime.UTC)

    def record_result(self, result: IntegrationTestResult):
        self.results[result.ifname][result.name] = result
        if result.succeeded:
            self.nb_sucessful_tests += 1
        else:
            self.nb_failed_tests += 1

    def record_all_remainings(self):
        while not self.all_results.empty():
            self.record_result(self.all_results.get())
            self.all_results.task_done()

    @property
    def nb_completed_tests(self) -> int:
        return self.nb_sucessful_tests + self.nb_failed_tests

    @property
    def all_succeeded(self) -> bool:
        if self.running:
            raise OSError("Runner still running")
        return self.nb_sucessful_tests == self.nb_tests

    @property
    def duration(self) -> float:
        return (self.ended_on - self.started_on).total_seconds()

    def shutdown(self, *, wait: bool = True, cancel_futures: bool = False):
        self.executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        self.record_all_remainings()
        self.all_results.join()
