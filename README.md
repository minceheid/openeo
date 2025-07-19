# openeo
Cloudless software install for the EO Mini 2 EV charger

<p align="center">
<img src="https://github.com/user-attachments/assets/e4592063-7f7b-485f-af75-c6b6009f6c96" style="width:25%; height:auto;"  />
<img src="https://github.com/user-attachments/assets/43ccdd18-a288-481f-b623-c05f28d6a6d3" style="width:25%; height:auto;"  />
</p>

## Install Instructions
This software can be installed onto a Raspberry OS Lite install. We recommend that you keep your original EO SD card safe and separate, so that you can revert easily, should things don't work out for you.

1. Obtain a 8GB (or larger) SD card
2. Flash the SD card with the Raspberry PI imager (Device: Raspberry Pi Zero, Operating System: Raspberry PI OS Lite (32 bit))

<p align="center">
<img src="https://github.com/user-attachments/assets/58fc15c4-ed2e-403d-b8f1-7e83a6c8c2b7" style="width:25%; height:auto;" />
<img src="https://github.com/user-attachments/assets/db492985-58e3-4b18-8bb2-5eb0fb31cb6d" style="width:25%; height:auto;" />
</p>

3. In the Raspberry PI imager "General" settings - set your Hostname, Username/Password, Wirelss LAN and Locale settings as appropriate. There are no restrictions on what to set your hostname and username, though I tend to go with "eo".

<p align="center"><img alt="Screenshot 2025-07-19 142812" src="https://github.com/user-attachments/assets/f3db2cc0-9055-4817-b135-2864c760de57" style="width:25%; height:auto;" /></p>

4. In the Raspberry PI imager "Services" settings - ensure that SSH is enabled, and I would recommend that public-key authentication is enabled, and you should add your SSH public key as approprate.

<p align="center"><img alt="Screenshot 2025-07-19 142824" src="https://github.com/user-attachments/assets/d4768f5d-19f3-4355-a44e-6216e492dc30" style="width:25%; height:auto;" />
</p>

5. *IMPORTANT* Once the new SD card has been created, remove power to your EO box by disconnecting it or by switching off the relevant breaker in your consumer unit. Please ensure that it is completely isolated from the mains electricity. *If you are unsure that the electricity is fully disconnected, then do not proceed*.
6. Open the EO mini by loosening the four captive screws that are visible on the front of the case (you may need to remove the four rubber covers, if they are fitted), and you will see the RPi Zero inside. You can now switch the SD cards, keeping the original safe.

<p align="center">
<img src="https://github.com/user-attachments/assets/5488462c-a5c6-44c0-843b-16ec874e846a" style="width:25%; height:auto;" />
<img src="https://github.com/user-attachments/assets/791a735f-6907-45ce-a0b4-738466f55b5b" style="width:25%; height:auto;" />
</p>

8. Close the EO enclosure, and apply power to it. The RPi Zero should boot, and if you got the configuration correct in step #3 above, it will then join your wireless network and you can log in with SSH. Note that the first time that you power up with a fresh SD card, it will take 10-15 minutes to fully boot before it is seen on the network.
9. Log onto your account on the RPi Zero via SSH over the WiFi network, and run the following commands:

~~~~
wget https://github.com/minceheid/openeo/archive/refs/heads/main.zip
unzip main.zip
mv openeo-main openeo
openeo/deploy.bash
sudo reboot
~~~~

Once the RPi Zero reboots, it should all be working. You should be able to point your browser at the IP address (which you will be able to find from your router, or you can use mDNS to navigate to _hostname_.local - where _hostname_ is whichever hostname you set in step 3 above). You should see the configuration web page, showing the charger status, and giving you control.

*Note* - at this time, only the **_Schedule_** mode and **_Manual_** mode is available. We will be adding **_Remote_** (OCPP) shortly.

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

