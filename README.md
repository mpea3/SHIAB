# SHIAB: Smart Home in a Box
SHIAB is a self-hostable smart home platform, similar to Home Assistant, but more lightweight and easily customisable. Instead of having many different configurations, SHIAB focuses on the essentials, and then allows users to extend functionality via 'modules' which are Python files that can extend functionality.

## Built in modules
- Weather (OpenWeatherAPI)
- Time/Date
- Calendar
- Bluetooth
- Wifi (IP) (for camera's, etc)

## External modules
- Zigbee
- TP Link Tapo (if possible)

## Architecture
- Python + FastAPI for backend
- Frontend HTML/CSS for simplicity
- 'In-a-box' functionality through Ansible (Ubuntu/Debian etc) or Docker
- Tracked through Git

## Design
The frontend should be minimal, but elegant, we want to focus on clean dashboard design that is readable on both desktop and mobile. The UI should be extendable via CSS themes that can edit the classes, and there should be documentation about designing CSS themes for SHIAB also. The extension via modules is also very important.