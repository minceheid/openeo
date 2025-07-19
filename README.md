# openeo
Cloudless software install for EO Mini 2 EV charger

## Install Instructions
This software can be installed onto a Raspberry OS Lite install. We recommend that you keep your original EO SD card safe and separate, so that you can revert easily. if things don't work out for you.

1. Obtain a 8GB (or larger) SD card
2. Flash the SD card with the Raspberry PI imager (Device: Raspberry Pi Zero, Operating System: Raspberry PI OS Lite (32 bit))
3. In the Raspberry PI imager "General" settings - set your Hostname, Username/Password, Wirelss LAN and Locale settings as appropriate. There are no restrictions on what to set your hostname and username, though I tend to go with "eo"
4. In the Raspberry PI imager "Services" settings - ensure that SSH is enabled, and I would recommend that public-key authentication is enabled, and you should add your SSH public key as approprate
5. *IMPORTANT* Once the new SD card has been created, remove power to your EO box by disconnecting it, or by switching off the relevant breaker in your consumer unit. Please ensure that it is completely isolated from the mains electricity. If you are unsure that the electricity is fully disconnected, then do not proceed.
6. Open the EO mini by loosening the four captive screws that are visible on the front of the case (you may need to remove the four rubber covers, if they are fitted), and you will see the RPi Zero inside. You can now switch the SD cards, keeping the original safe.
7. Close the EO enclosure, and apply power to it. The RPi Zero should boot, and if you have got the configuration correct, it will join your wireless network and you can log in with SSH
8. Log onto your account on the RPi Zero via SSH over the WiFi network, and run the following commands:

~~~~
sudo apt-get -y install git
git clone https://github.com/minceheid/openeo
openeo/deploy.bash
sudo reboot
~~~~

Once the RPi Zero reboots, it should all be working. You should be able to point your browser at the IP address (which you will be able to find from your router, or you can use mDNS to navigate to <hostname>.local). You will see the configuration web page, showing status, and giving you control.

## Configuration
The software is configured by a json configuration file, an example is provided. The main functions are provided by plugin modules, each of which must be listed in the json config file, along with the configuration parameters. See the source of the module in the eo/openeo/ directory for more information on each module. If a configuration file does not initially exist, a default configuration will be generated and saved for you.

~~~~
{
  "scheduler" : { "enabled" : False, "schedule" : [{"start" : "2200", "end" : "0400", "amps" : 32}] },
  "switch" : { "enabled" : True, "on" : True, "amps" : 32 },
  "configserver": { "enabled": True, "port": 80 },
  "chargeroptions" : { "mode" : "switch" },
  "logger": {
      "enabled": True,
      "hires_interval": 2,        # 2 seconds
      "hires_maxage": 60*10,      # 10 minutes
      "lowres_interval": 60*5,    # 5 minutes
      "lowres_maxage": 60*60*48   # 48 hours
  },
}

~~~~
