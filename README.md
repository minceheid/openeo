# openeo
Cloudless software install for the EO Mini 2 EV charger

<p align="center">
<img src="https://github.com/user-attachments/assets/e4592063-7f7b-485f-af75-c6b6009f6c96" style="width:25%; height:auto;"  />
<img src="https://github.com/user-attachments/assets/1e6d8d2f-df0d-4b3b-8647-fd621d5297e4" style="width:25%; height:auto;"  />
</p>

## Install Instructions
This software can be installed onto a Raspberry OS Lite install. We recommend that you keep your original EO SD card safe and separate, so that you can revert easily, should things don't work out for you.

1. Obtain a 8GB (or larger) SD card
2. Flash the SD card with the Raspberry PI imager (Device: Raspberry Pi Zero, Operating System: Raspberry PI OS Lite (32 bit))

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
6. Open the EO mini by loosening the four captive screws that are visible on the front of the case (you may need to remove the four rubber covers, if they are fitted), and you will see the RPi Zero inside. You can now switch the SD cards, keeping the original safe.

<p align="center">
<img src="https://github.com/user-attachments/assets/5488462c-a5c6-44c0-843b-16ec874e846a" style="width:25%; height:auto;" />
<img src="https://github.com/user-attachments/assets/791a735f-6907-45ce-a0b4-738466f55b5b" style="width:25%; height:auto;" />
</p>

7. Close the EO enclosure, and apply power to it. The RPi Zero should boot, and if you got the configuration correct in step #3 above, it will then join your wireless network and you can log in with SSH (you should be able to find the RPi IP address from your broadband router). Note that the first time that you power up with a fresh SD card, it will take 10-15 minutes to fully boot before it is seen on the network.
8. Log onto your account on the RPi Zero via SSH over the WiFi network, and run the following three commands. This will download a deployment script from github, run it to install the software onto your RPi, then reboots your RPi to allow the software to finish configuring and start up.

To download the latest

~~~~
wget https://raw.githubusercontent.com/minceheid/openeo/refs/heads/main/deploy.bash
bash deploy.bash
sudo reboot
~~~~

To download a specific version (you will need to migrate your config.json by hand)

~~~~
wget https://raw.githubusercontent.com/minceheid/openeo/refs/heads/main/deploy.bash
bash deploy.bash v0.4
sudo reboot
~~~~

Once the RPi Zero reboots, it should all be working. You should be able to point your browser at the IP address (or you can use mDNS to navigate to _hostname_.local - where _hostname_ is whichever hostname you set in step 3 above). You should see the configuration web page, showing the charger status, and giving you control.

*Note* - at this time, only the **_Schedule_** mode and **_Manual_** mode is available. We will be adding **_Remote_** (OCPP) shortly.

## Important Notes
The openeo charger cannot currently accommodate the following features:

* Total current limiting at the mains fuse ("load balancing").  If this charger is used on a looped supply, a small fuse, or shares a supply with another charger, it might require load balancing to avoid a failure of the main incoming fuse.  This would result in a total power outage to the home should it occur, and would require your DNO to visit to correct the failure.   We will look to introduce load balancing in the near future, but for now, *DO NOT* use this software if you depend upon that.  

* Solar system integration (except for Victron systems via the `victron_ess` plugin).  This means the openeo charger won't start charging when there is an excess of solar being exported to the grid.  This is also a feature we are looking to add in the future and we are interested in hearing from users who have systems like this that we can test the openeo software on.

* Control is currently only possible locally via the web interface and some phones when connected to the same wireless network as the charger.  Whilst it is possible to expose your openeo instance to the public internet, we strongly advise that you do not do so, since the application has not been audited for security vulnerabilities yet.  This also means you can't (yet) control charging remotely, though we will be releasing Home Assistant support in the near future which should allow this.

Disclaimer:  The software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection with the software or the use or other dealings in the software.   Please see the important terms and conditions in the `LICENSE.txt` file.   The software has been developed by clean-room reverse engineering of the existing EO software and no copyrighted EO code is used in this application.  
