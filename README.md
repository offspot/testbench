# Offspot testbench

A tool to validate Kiwix Hotspot's feature set and performances

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
