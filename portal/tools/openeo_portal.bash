#!/bin/bash

if [ "$1" = "stop" ] ; then
	######
	# Shuts down Capitive portal
	nmcli conn del openeo-AP
	iw dev wlan1 del
	service dnsmasq stop
else
	############
	# Take a precaution and wait for the network to settle
	sleep 15

	echo "Creating virtual network interface"
	
	#iw dev wlan0 interface add wlan1 type __ap
	nmcli con add type wifi ifname wlan1 mode ap ...

	echo "NM Connections"
	nmcli conn del openeo-AP 2>/dev/null
	echo "Add and configure new connection"
	nmcli radio wifi on
	nmcli con add type wifi ifname wlan1 mode ap con-name openeo-AP ssid OpenEO autoconnect false
	nmcli connection modify openeo-AP remove wifi-sec
	nmcli con modify openeo-AP ipv6.method disabled
	nmcli con modify openeo-AP ipv4.method manual ipv4.address 192.168.4.1/24
	nmcli con up id openeo-AP

	sleep 5
	service dnsmasq start

	####
	# portal.py is listening on port 81 on all interfaces for the captive portal, deliberately
	# to avoid clashing with tcp/80 on the main user interface. We can't fix the main interface
	# to a known IP adress, because we don't know what the IP address will be, but we definately
	# want to access the captive portal through tcp/80, so probably easiest to use some iptables 
	# natting to fix this on the wlan1 interface
	# iptables usually saves its ruleset on server shutdown, and we may want to change this through
	# a deploy in the future, so no harm in flushing the ruleset and creating afresh at boot time

	iptables -t nat -L --line-numbers | \
		awk '/REDIRECT.*ports 81$/ {print $1}' | \
		xargs -L 1 -t iptables -t nat -D PREROUTING

	iptables -t nat -A PREROUTING -i wlan1 -p tcp --dport 80 -j REDIRECT --to-ports 81

fi
