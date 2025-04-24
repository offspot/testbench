# Offspot testbench

A tool to validate Kiwix Hotspot's feature set and performances

[![CodeFactor](https://www.codefactor.io/repository/github/openzim/_python-bootstrap/badge)](https://www.codefactor.io/repository/github/openzim/_python-bootstrap)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![codecov](https://codecov.io/gh/offspot/testbench/branch/main/graph/badge.svg)](https://codecov.io/gh/offspot/testbench)
![Python Version](https://img.shields.io/badge/Python-3.11-blue)

## Objectives

- Identify behavioral and performance regressions before release
- Document our core feature set
- Document capacity/performance for identified scenarios

---

The testbench is a suite of integration and load tests that are run from a physical device, targetting a Kiwix Hotspot.

![testbench](https://github.com/user-attachments/assets/bd356722-4777-4f9c-a3d5-7edd75543c0a)


## Requirements

- A running Kiwix Hotspot as target
- A Raspberry Pi 5 4GB as test host
  - Connected to Internet via Ethernet or with an hardware clock (for time accuracy)
  - Running RaspiOS on an NVMe disk for better performance (you dont want the host to slow down the tests)
  - Powered, external USB hub. We use 2 x [i-tec USB3 16 port charging Hub](https://i-tec.pro/en/produkt/u3chargehub16-2/)
  - Several USB WiFi dongles. We use 32 x [TP-Link TL-WN725N](https://www.tp-link.com/en/home-networking/adapter/tl-wn725n/)


## Tools

### WiFI Capacity

Because of limitations in the 802.11 chipset firmwares used and their compatibility with OS, we specifically tests

- How many concurrent WiFi clients can connect? *its result configures the integration tests*.
- Max WiFi throughtput

### Integration validation

- Can connect to specific SSID (`Kiwix Hotspot`).
- Receives an IPv4 in specified range (`192.168.2.128/25`)
- Receives a specific IPv4 gateway (`192.168.2.1`)
- Receives a specific IPv4 DNS server (`192.168.2.1`)
- Can ping gateway
- Can resolve specific hotspot domains (`kiwix.hotspot`, `goto.kiwix.hotspot`)
- Can reach gateway via HTTP (`http://192.168.2.1`)
- Captive portal is running on specified ports (`http://192.168.2.1:2080` and `https://192.168.2.1:2443`) 
- HTTP request to both `kiwix.hotspot` and public domain is captured
- Can register to the captive-portal (`GET /register-hotspot/`)
- Further requests (`http://kiwix.hotspot/`) are not captured
- `kiwix-serve`
  - Served on `browse.kiwix.hotspot`
  - Can get a suggestion
  - Can get full-text search result
  - Can query random article
- Additional per-service tests

These behavior test can be tested from a single interface, serving as integration tests but also concurrently to validate that the number of concurrent client means *concurrent working clients*.

### Performance validation

Those consists in an orchestration of parallel tests simulating real traffic from pre-defined scenarios.

## Setup

Assuming a bookworm raspbian host

```sh
# you'll most likely be using it over SSH
systemctl enable --now ssh

# update packages
apt update && apt upgrade

# setup/fix locale (en_US.UTF-8)
dpkg-reconfigure locales

# set a country for WiFi regulations to apply (mandatory!)
raspi-config nonint do_wifi_country ML

# Install Apache JMeter
curl -L -o /tmp/jmeter.tgz https://dlcdn.apache.org//jmeter/binaries/apache-jmeter-5.6.3.tgz
tar --strip-components 1 -C /usr/local -x -f /tmp/jmeter.tgz
rm -rf /tmp/jmeter.tgz
```

Install testbench

```sh
# you'll want to install in isolated virtual env
python3 -m .venv
source .venv/bin/activate
```

```sh
# should you want a release
pip install offspot-testbench
```

```sh
# using the trunk
git clone https://github.com/offspot/testbench.git
pip install -e testbench
```

Run the testbench

```py
testbench --help
```

## Usage

There are three sub-commands to the `testbench` program, serving different needs:

| Command       | Description                                                            |
| ---           | ---                                                                    |
| `status`      | Lists the available 802.11 (WiFi) devices available on the host        |
| `integration` | Runs the integration test-suite in parallel over all requested devices |
| `perf`        | Runs JMeter Test Plan with all requested devices                       |

### `status`

Use this only to find out about your setup. You'll get the list of all WiFi devices connected.

You can use it to tweak the *exclude* filters to get a list of devices you'll use with next commands.

## `integration`

Always run this when testing a new Hotspot/version to ensure the Hotspot behaves properly with one client or more. Those tests are simple and a failing test is easier to diagnose than JMeter results.

This command is also your way to find out how many concurrent WiFi clients the Hotspot can accept (and sustain to some extent).

## `perf`

Use this to find out the limit of your Hotspot regarding concurrent access.

The tool connects each requested devices, then runs JMeter and provides very basic statistics. It's up to you to dig into the JMeter results CSV.

## Notes

### When in doubt, reboot

You don't want to be in an unknown state, wondering why stuff are not working the way they should.

- After a JMeter crash, reboot host.
- After a JMeter hang, reboot target.

When you overwhelm an Hotspot, it can freeze due to lack of memory (there's no swap). In this case, even though the Pi light is green, the Pi is not responding and even the ACPI power button is not working. Unplug-replug the target Pi. If the JMX is not timed-out properly, JMeter can hang forever.

### Be cautious with JMX editing

The summary tables post-JMeter are built by reading the results CSV file.

When using your own JMX, make sure not to generate Test Status message that spans multiple lines as the CSV parsing is quite primitive.

---

testbench adheres to openZIM's [Contribution Guidelines](https://github.com/openzim/overview/wiki/Contributing).

testbench has implemented openZIM's [Python bootstrap, conventions and policies](https://github.com/openzim/_python-bootstrap/docs/Policy.md) **v1.0.0**.
