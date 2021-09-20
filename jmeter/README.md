# Kiwix Offspot load testing

Kiwix Offspot load test runs with [Apache
JMeter](https://jmeter.apache.org/).

## Install JMeter

1. Go to https://jmeter.apache.org/download_jmeter.cgi
2. Download the latest release and unpack it.
3. Go to the `bin` directory and start `./jmeter`

## Load configuration

Once you have started the GUI version of JMeter, open the menu "File"
> "Open". Choose the configuration file `offspot.jmx`.

## Run the load test

Once you have open the configuration, click on the top item in the
left sidebar tree-view. On the right panel, you should have the list
of variables. Change them accordingly to your setup.

## Headless run

JMeter can as well be started in non GUI mode with:
```bash
$jmeter -n -t offspot.jmx
```
