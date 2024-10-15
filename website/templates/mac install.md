Installation and Setup Guide for Satori on macOS:

Install Docker:
if you haven't already Download Docker for your version of Mac:
<a href="https://desktop.docker.com/mac/main/arm64/Docker.dmg" target="_blank">Docker For Mac (Apple Silicon chip)</a>
<a href="https://desktop.docker.com/mac/main/amd64/Docker.dmg" target="_blank">Docker For Mac (Intel chip)</a>

Install wget:
Run these commands in your terminal:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install wget

Download Satori:
Use wget to download Satori:
wget https://satorinet.io/static/download/satori.zip

Unzip Satori:
Unzip the downloaded Satori package:
unzip satori.zip

Install Python and Dependencies:
Install pyenv:
brew install pyenv
Install Python 3.12:
pyenv install 3.12

Install Satori:
Navigate to the '.satori' directory:
cd .satori

Install Dependencies:  (replace these files with the ones provided earlier)
Run this command to install dependencies:
./install
If there are no errors, execute:
./install_service

Remember to start Docker (step 1) before proceeding with step 7. If Satori doesn't start automatically after a restart, you should find a desktop icon to launch it manually. 