#!/bin/bash

REPO_NAME=pirate-audio-orac
REPO_URL=https://github.com/wangpy/$REPO_NAME.git
APP_DIR=/usr/local/pirate-audio-orac

pushd $HOME
sudo apt-get update
sudo apt-get install -y git \
	python3-rpi.gpio python3-spidev python3-pip python3-pil python3-numpy

rm -rf $REPO_NAME
git clone $REPO_URL
cd $REPO_NAME
pip3 install -r requirements.txt
sudo rm -rf $APP_DIR
sudo mkdir $APP_DIR
sudo cp -R pirate-audio-orac.py $APP_DIR
sudo install -v -m 644 pirate-audio-orac.service /usr/lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pirate-audio-orac.service
sudo systemctl start pirate-audio-orac.service

popd # $HOME

echo "*** Installation Complete."
