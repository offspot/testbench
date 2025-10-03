import datetime
import math
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

"""
    --?
        print command line options and exit
    -h, --help
        print usage information and exit
    -v, --version
        print the version information and exit
    -p, --propfile <argument>
        the jmeter property file to use
    -q, --addprop <argument>
        additional JMeter property file(s)
    -t, --testfile <argument>
        the jmeter test(.jmx) file to run. "-t LAST" will load last
        used file
    -l, --logfile <argument>
        the file to log samples to
    -i, --jmeterlogconf <argument>
        jmeter logging configuration file (log4j2.xml)
    -j, --jmeterlogfile <argument>
        jmeter run log file (jmeter.log)
    -n, --nongui
        run JMeter in nongui mode
    -s, --server
        run the JMeter server
    -E, --proxyScheme <argument>
        Set a proxy scheme to use for the proxy server
    -H, --proxyHost <argument>
        Set a proxy server for JMeter to use
    -P, --proxyPort <argument>
        Set proxy server port for JMeter to use
    -N, --nonProxyHosts <argument>
        Set nonproxy host list (e.g. *.apache.org|localhost)
    -u, --username <argument>
        Set username for proxy server that JMeter is to use
    -a, --password <argument>
        Set password for proxy server that JMeter is to use
    -J, --jmeterproperty <argument>=<value>
        Define additional JMeter properties
    -G, --globalproperty <argument>=<value>
        Define Global properties (sent to servers)
        e.g. -Gport=123
         or -Gglobal.properties
    -D, --systemproperty <argument>=<value>
        Define additional system properties
    -S, --systemPropertyFile <argument>
        additional system property file(s)
    -f, --forceDeleteResultFile
        force delete existing results files and web report folder if
         present before starting the test
    -L, --loglevel <argument>=<value>
        [category=]level e.g. jorphan=INFO, jmeter.util=DEBUG or com
        .example.foo=WARN
    -r, --runremote
        Start remote servers (as defined in remote_hosts)
    -R, --remotestart <argument>
        Start these remote servers (overrides remote_hosts)
    -d, --homedir <argument>
        the jmeter home directory to use
    -X, --remoteexit
        Exit the remote servers at end of test (non-GUI)
    -g, --reportonly <argument>
        generate report dashboard only, from a test results file
    -e, --reportatendofloadtests
        generate report dashboard after load test
    -o, --reportoutputfolder <argument>
        output folder for report dashboard
"""


def get_workdir():
    return Path(tempfile.mkdtemp(dir=Path.cwd(), prefix="jmeter_"))


class JMeterRunner:

    def __init__(
        self,
        jmx: Path,
        ifnames: list[str],
        fqdn: str | None = None,
        kiwix_domain: str | None = None,
        dns_server: str | None = None,
        assume_online: str | None = None,
        content_id: str | None = None,
        user_values: dict[str, str] | None = None,
        workdir: Path | None = None,
    ):
        self.jmx = jmx
        self.ifnames = ifnames
        self.nb_users = len(ifnames)
        self.fqdn = fqdn
        self.kiwix_domain = kiwix_domain
        self.dns_server = dns_server
        self.assume_online = assume_online
        self.content_id = content_id
        self.user_values = user_values or {}
        self.workdir = workdir or get_workdir()
        self.write_ifnames()
        self.started_on = self.ended_on = datetime.datetime.now(datetime.UTC)

    def write_ifnames(self):
        # ifnames.csv contains the list of all the “clients” interfaces.
        # it is used as source device by jmeter to make actual use of those
        # ifaces when making requests.
        # as each defines a client, we also compute some “groups” that are
        # tied to each line.
        # group10 means that it's `true` for 10% of the clients
        # group40 means that it's `true` for 40% of the clients
        # etc
        # it's rounded up and includes at least one client.
        # allows one to easily condition tests to arbitrary (well those groups)
        # number of clients.
        total_clients = len(self.ifnames)
        groups: dict[str, list[str]] = {}
        print("")
        for gnum in range(10, 101, 10):
            name = f"group{gnum}"
            nb_clients = min(
                [max([math.ceil(total_clients / 100 * gnum), 1]), total_clients]
            )
            ifnames = list(self.ifnames)
            random.shuffle(ifnames)
            groups[name] = ifnames[:nb_clients]
        csv_lines: list[str] = [",".join(["ifname", *list(groups.keys())])]
        for ifname in self.ifnames:
            csv_lines.append(
                ",".join(
                    [
                        ifname,
                        *[
                            "true" if ifname in gifnames else "false"
                            for gifnames in groups.values()
                        ],
                    ]
                )
            )

        self.ifnames_csv_path.write_text("\n".join(csv_lines))

    def start(self):
        environ = os.environ.copy()
        environ.update({"JVM_ARGS": "-Xmx3g"})
        self.started_on = datetime.datetime.now(datetime.UTC)
        args: list[str] = [
            shutil.which("jmeter") or "/usr/bin/jmeter",
            "-n",
            "-t",
            str(self.jmx),
            f"-Jnb_users={self.nb_users}",
        ]
        for key in (
            "fqdn",
            "kiwix_domain",
            "dns_server",
            "assume_online",
            "content_id",
        ):
            if getattr(self, key):
                args.append(f"-J{key}={getattr(self, key)}")

        for key, value in self.user_values.items():
            args.append(f"-J{key}={value}")

        self.ps = subprocess.Popen(
            args=args,
            cwd=self.workdir,
            env=environ,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @property
    def succeeded(self) -> bool:
        return self.ps.returncode == 0

    @property
    def is_running(self) -> bool:
        if self.ps.poll() is not None:
            self.ended_on = datetime.datetime.now(datetime.UTC)
            return False
        return True

    @property
    def results_csv_path(self) -> Path:
        return self.workdir.joinpath("results.csv")

    @property
    def ifnames_csv_path(self) -> Path:
        return self.workdir.joinpath("ifnames.csv")

    @property
    def duration(self) -> float:
        return (self.ended_on - self.started_on).total_seconds()
