# pirate-audio-orac
ORAC Controller for Pimoroni Pirate Audio

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

Select **hifibery-dac** as the jack audio interface: Run `patchbox jack config` and select **hifiberry-dac** (48000/128/2 config should work)

Run the following command to install the controller:
```sh
curl https://raw.githubusercontent.com/wangpy/pirate-audio-orac/main/install.sh | bash
```

The contoller interface should start running when installation completes. The service runs when the device boots.

## Navigation
* A button: move cursor up
  - "SELECT ITEM" in module / preset selection menu
* X button: move cursor up 
  - "SELECT ITEM" in module / preset selection menu
* A+X button: switch pages
* B button: decrease parameter / previous page / toggle / perform 
  - "MOVE CURSOR DOWN in module / preset selection menu
* Y: button: increase parameter / next page / toggle / perform 
  - "MOVE CURSOR DOWN in module / preset selection menu
