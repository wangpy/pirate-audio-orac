# pirate-audio-orac
ORAC Controller for Pimoroni Pirate Audio

[![](http://img.youtube.com/vi/QDBVFwmH3f0/0.jpg)](http://www.youtube.com/watch?v=QDBVFwmH3f0 "Pirate Audio + Keybow = ORAC Fun")

## Features
* Full ORAC controlling via OSC /Kontrol messages
  - MEC needs to be patched to send resources correctly upon connection. Refer to this [PR](https://github.com/TheTechnobear/MEC/pull/23)
* Device status (network IP) display and maintenance (shutdown)

## Installation
The following steps are for [**Patchbox OS**](https://blokas.io/patchbox-os/)

Enable **ORAC** module using `patchbox module config`.

To support changing module / preset, MEC needs to be patched and rebuilt. Refer to this [PR](https://github.com/TheTechnobear/MEC/pull/23)

Set up Pirate Audio according to it's [documentation](https://github.com/pimoroni/pirate-audio), or add the following config to `/boot/config.txt`:
```
dtparam=spi=on
dtoverlay=hifiberry-dac
gpio=25=op,dh
```

Select **hifibery-dac** as the jack audio interface: Run `patchbox` -> **jack** -> **config** and select **sndrpihifiberry** (48000/128/2 config should work)

Run the following command to install the controller:
```sh
curl https://raw.githubusercontent.com/wangpy/pirate-audio-orac/main/install.sh | bash
```

For using with [pi-top\[4\]](https://www.pi-top.com/products/pi-top-4) enclosure, please use **dev/pi-top4** branch:
```sh
curl https://raw.githubusercontent.com/wangpy/pirate-audio-orac/main/install.sh dev/pi-top4 | bash
```

The contoller interface should start running when installation completes. The service runs when the device boots.

## Navigation
* **A** button: **Move up** cursor
  - In module / preset selection menu: **Select Item**
* **X** button: **Move down** cursor 
  - In module / preset selection menu: **Select Item**
* **A+X** button: **Switch** between main pages or **quit** module / preset selection menu
* **B** button: **Decrease** parameter / previous page / toggle / perform 
  - In module / preset selection menu: **Move up** cursor
* **Y** button: **Increase** parameter / next page / toggle / perform 
  - In module / preset selection menu: **Move down** cursor
