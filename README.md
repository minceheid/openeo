# Cloudless software for the EO Smart Home Hub/Mini and Mini Pro 2 EV charger
EO Charging announced in July 2025 that their EO Smart Home app is being discontinued on November 30th 2025. This disables the ability for owners to set automated timed schedules and to directly manage their device, which will then operate purely as a "plug & play" charger. This project aims to provide an alternate, open source software that can be directly installed on these devices to allow control from the local WiFi network without the use of the EO Cloud. 

<p align="center">
<img src="https://github.com/user-attachments/assets/e4592063-7f7b-485f-af75-c6b6009f6c96" style="width:25%; height:auto;"  />
<img src="https://github.com/user-attachments/assets/1e6d8d2f-df0d-4b3b-8647-fd621d5297e4" style="width:25%; height:auto;"  />
</p>

## Compatibility
This project has been designed to be compatible with the EO Smart Home Hub/Mini and EO "Mini Pro 2" devices. It does **not** support "Mini Pro 3"

### [Smart Home Hub/Mini](https://github.com/user-attachments/files/22066221/EO_Home_Hub.pdf)
<p align="center">
<img src="https://github.com/user-attachments/assets/1ad1ba51-ef88-4cb6-9a99-9f922e32f02c" style="width:25%; height:auto;" />
<img src="https://github.com/user-attachments/assets/62a2e6cc-128f-49bd-8265-9c09de2d08fe" style="width:25%; height:auto;" />
  
</p>

### [Mini Pro 2](https://github.com/user-attachments/files/22066224/eo-mini-pro-2-installation-and-userguide.pdf)
<p align="center">
<img src="https://github.com/user-attachments/assets/5488462c-a5c6-44c0-843b-16ec874e846a" style="width:25%; height:auto;" />
</p>

## Install Instructions
This software can be installed onto a Raspberry OS Lite install. We recommend that you keep your original EO SD card safe and separate, so that you can revert easily, should things don't work out for you.

1. Obtain a 8GB (or larger) SD card
2. Flash the SD card with the Raspberry PI imager (Device: Raspberry Pi 3 for Home Hub and Raspberry Pi Zero for Mini Pro 2, Operating System: Raspberry PI OS Lite (32 bit))

<p align="center">
<img src="https://github.com/user-attachments/assets/58fc15c4-ed2e-403d-b8f1-7e83a6c8c2b7" style="width:25%; height:auto;" />
<img src="https://github.com/user-attachments/assets/db492985-58e3-4b18-8bb2-5eb0fb31cb6d" style="width:25%; height:auto;" />
</p>

3. In the Raspberry PI imager "General" settings - set your Hostname, Username/Password, Wirelss LAN and Locale settings as appropriate. There are no restrictions on what to set your hostname, but you must create a user of "pi"

<p align="center"><img  alt="image" src="https://github.com/user-attachments/assets/da0e365a-141b-4f70-8be8-5f23a900dfa3" style="width:25%; height:auto;"/></p>

4. In the Raspberry PI imager "Services" settings - ensure that SSH is enabled, and I would recommend that public-key authentication is enabled, and you should add your SSH public key as approprate.

<p align="center"><img alt="Screenshot 2025-07-19 142824" src="https://github.com/user-attachments/assets/d4768f5d-19f3-4355-a44e-6216e492dc30" style="width:25%; height:auto;" />
</p>

5. *IMPORTANT* Once the new SD card has been created, remove power to your EO box by disconnecting it or by switching off the relevant breaker in your consumer unit. Please ensure that it is completely isolated from the mains electricity. *If you are unsure that the electricity is fully disconnected, then do not proceed*.
6. Open the Smart Hub or Mini Pro 2 box by loosening the four captive screws that are visible on the front of the case (you may need to remove the four rubber covers, if they are fitted), and you will see the Raspberry Pi inside (Smart Hub is a Raspberry Pi 3, and the Mini Pro 2 is a smaller Raspberry Pi Zero). You can now switch the SD cards, keeping the original safe. Whilst you are doing this, on the Mini Pro 2, take care to not accidentally dislodge the cables connecting the raspberry pi board with the main control board in the lid of the unit.

<table style="width:80%"><tr><td>
<p align="center">
<figure>
<img src="https://github.com/user-attachments/assets/d6a89cbe-7f8c-448c-9222-654200d533d4" style="width:50%; height:auto;" />
<br><figcaption>Smart Hub</figcaption>
</figure>
</td><td>
<figure>
<img src="https://github.com/user-attachments/assets/791a735f-6907-45ce-a0b4-738466f55b5b" style="width:50%; height:auto;" />
<br><figcaption>Mini Pro 2</figcaption>
</figure>
</p>
</td></tr></table>
7. Close the EO enclosure, and apply power to it. The Raspberry Pi should boot, and if you got the configuration correct in step #3 above, it will then join your wireless network and you can log in with SSH (you should be able to find the RPi IP address from your broadband router). Note that the first time that you power up with a fresh SD card, it will take about five minutes to fully boot before it is seen on the network.
8. Log onto your account on the RPi via SSH (e.g. PuTTY) over the WiFi network, and run the following commands. This will download the software from github and run the installation process, then reboots your RPi to allow the software to finish configuring and start up.

~~~~
curl -sSL https://github.com/minceheid/openeo/raw/refs/heads/main/openeo_download.py | python3 -
sudo reboot
~~~~

Once the Raspberry Pi reboots, it should all be working. You should be able to point your browser at the IP address (or you can use mDNS to navigate to _hostname_.local - where _hostname_ is whichever hostname you set in step 3 above). You should see the configuration web page, showing the charger status, and giving you control.

*Note* - at this time, only the **_Schedule_** mode and **_Manual_** mode is available. We will be adding **_Remote_** (OCPP) shortly.

## Home Assistant and Prometheus
openeo is designed to allow the export of data for visualisation through home automation toolsets such as Home Assistant and Prometheus. The following endpoints are available:

* ```/metrics```: Prometheus exporter
* ```/api```: Home Assistant exporter

## Statistics
Full visualisation of the chargers operations is available by selecting the "Statistics" option in the menu.

<p align="center">
<img alt="newplot (3)" src="https://github.com/user-attachments/assets/fde895b3-f1b9-412e-b4d5-4eb02fb3200a" style="width:50%; height:auto;"/>
</p>

## Solar Integration
Where there is a CT clamp measuring solar generation, openeo can control vehicle charge, based on the solar generation. To enable this feature, select the "Solar Charging Enabled" options in the settings. Additionally, you can optionally set a solar reservation value. As an example, if your CT clamp is reporting 10A of solar generation, and your Solar Reservation is set at 3A, then your vehicle will charge at 7A. This may allow you to reduce grid consumption for power requirements elsewhere in your home. The operation of solar charging **does not** require the manual override or a schedule to be active for it to charge the vehicle. To ensure that you make the most of solar generation, it is permanently active when this setting is enabled.

## Load Balancing
If this charger is used on a looped supply, a small fuse, or shares a supply with another charger, you may wish to consider reviewing the Load Management settings to avoid a failure of the main incoming fuse, which would result in a total power outage to the home, and would require your electricity supplier to visit and correct the failure. The load balancing feature is included for testing purposes but for now, *DO NOT* use this software if you **depend** upon that feature.
The Load Balancing feature requires the use of a CT clamp on your inbound electricity supply, usually located at your meter. The settings page allows to set a site maximum current draw (the default is 60A). Vehicle charging will be limited to prevent openeo from exceeding this limit. As an example, if your site limit is set to 80A, and your site CT is reading 74A, then the maximum that openeo will allow you to charge your vehicle at is 6A.

## CT Calibration
Current Transformer (CT) meter readings sometimes require additional calibration to compensate for minor inaccuracies. This may have been a procedure that your EO installation engineer carried out when your charger was installed. If necessary, you can also set the CT calibration on openeo by visiting the "CT calibration" menu item. 
It is recommended that you do this from a larger screen (tablet or laptop), as the larger screen will be useful. This page shows a rolling chart of the last 15 minutes of CT readings from each of the three possible CT meters that can be connected to the charger. Each reading can be calibrated by adjusting an offset and a scaling factor to suit your circumstances:
* Offset: This figure will be added to the CT reading - configurable values are between -2A and +2A
* Scaling: This figure will be multiplied to the CT reading - configurable values are between 0.8 and 1.2 (-20% and +20%)

Simply use the sliders at the top of the page, and observe the visual changes in the charts on the screen. When you're happy with the setting, hit "Save" for it to become fixed.

<p align="center">
<img alt="image" src="https://github.com/user-attachments/assets/82ba7e4e-536d-4c29-9d55-d6973e2bc0b3" style="width:50%; height:auto;"/>
</p>

## Updating
From time to time, we will update the software. When a new release is tagged on GitHub, your openeo installation can be updated by simply repeating the install procedure. This will retrieve the latest release, install and activate it:
~~~~
curl -sSL https://github.com/minceheid/openeo/raw/refs/heads/main/openeo_download.py | python3 -
sudo reboot
~~~~

## Configuration
On first start, the default configuration will be loaded into the configuration database (stored in /home/pi/etc/config.db) - any settings changes (schedule timing, mode change, etc) are retained by updating this configuration database. To revert entirely to defaults, the /home/pi/etc/config.db file can be deleted, and the software restarted.

New configuration can be manually added by creating a JSON file called /home/pi/etc/config.json. This file is read at startup, and if sucessfully merged into the configuration database, it is renamed to config.json_loaded

Example ```~pi/etc/config.json``` file to set the default log level to debug (normally "info")
```
{"chargeroptions":{"log_level":"debug"}}
```

## Troubleshooting
After installation - it is normal to sometimes briefly recieve a "Controller Error" message on startup. This is simply the software establishing communications with the charger. If the red "Controller Error" message persists for more than a minute, then this indicates that the Raspberry Pi has not been able to establish serial communication with the charger contol board. We recommend that you doublecheck the connection within the unit (these instructions assume Mini Pro 2)

<p align="center"><img src="https://github.com/user-attachments/assets/bcc180dc-f8c1-4e36-a994-a1190989f947" style="width:50%; height:auto;"/></p>

1. turn power to the charger off at the consumer unit
2. take the cover off
3. check carefully that the cable that runs between the Raspberry Pi board and the power board (the one with the big relay) is fully and correctly seated on both ends
4. assembly is the reverse of disassembly

## openeo_download.py
The openeo_download.py program helps to manage the download and deployment of the software. Run with no parameters, it will locate and download/install the latest release from GitHub. Parameters available to further assist are:
* ```--list``` : list available releases or branches (for dev use only)
* ```--release <name>```: install the given release. This might allow for install of an earlier release, for example. The ```<name>``` can also be a branch name, in which case it will download and try to deploy the head of the named branch, though this is intended for development use only.   

## Important Notes
The openeo charger cannot currently accommodate the following features:

* Control is currently only possible locally via the web interface and some phones when connected to the same wireless network as the charger.  Whilst it is possible to expose your openeo instance to the public internet, we strongly advise that you do not do so, since the application has not been audited for security vulnerabilities yet.  This also means you can't (yet) control charging remotely, though we will be releasing Home Assistant support in the near future which should allow this.

## Disclaimer
The software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection with the software or the use or other dealings in the software.   Please see the important terms and conditions in the `LICENSE.txt` file.   The software has been developed by clean-room reverse engineering of the existing EO software and no copyrighted EO code is used in this application.  
