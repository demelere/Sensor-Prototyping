# Lucid Triton Camera Setup - Raspberry Pi 5

Setup guide for Lucid Triton TRI054S-CC GigE Vision camera with RPi5 running Ubuntu 22.04.

## Prerequisites

**Hardware**
- Raspberry Pi 5 or NVIDIA Jetson Orin Nano
- Lucid Triton camera
- Ethernet cable (Cat5e+)
- Camera power supply
- MicroSD with Ubuntu 22.04

**Software**
- Arena SDK for ARM64 from Lucid's site

---

## Initial Setup

### Install Prerequisites

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-dev build-essential ethtool
```

These are compilation tools and network utilities needed by Arena SDK.

### Install Arena SDK

```bash
cd ~/Downloads
tar -xzf ArenaSDK_*.tar.gz
cd ArenaSDK_Linux_ARM64/
sudo sh Arena_SDK_ARM64.conf
```

Installs camera drivers and libraries.

### Install Python Bindings (optional)

```bash
sudo python3 -m pip install arena_api-*.whl --break-system-packages
```

---

## Network Configuration

The camera uses Link-Local addressing (169.254.x.x range) - a private network space that doesn't route to internet. Pi and camera need matching configuration to communicate.

### Find Ethernet Interface

```bash
ip link show
```

Look for `eth0` or similar (not `lo` or `wlan0`). Use this name in all commands below.

### Configure Network Settings

**Enable jumbo frames** - allows 9000 byte packets vs standard 1500, reduces CPU load and improves streaming performance:
```bash
sudo ip link set eth0 mtu 9000
```

**Increase ring buffer** - more hardware buffer space prevents dropped frames:
```bash
sudo ethtool -g eth0  # Check max
sudo ethtool -G eth0 rx 8192  # Set to max (use your actual max)
```

**Increase socket buffers** - Linux defaults are tiny, this sets to 1MB:
```bash
sudo sh -c "echo 'net.core.rmem_default=1048576' >> /etc/sysctl.conf"
sudo sh -c "echo 'net.core.rmem_max=1048576' >> /etc/sysctl.conf"
sudo sysctl -p
```

**Disable reverse path filtering** - Linux blocks Link-Local IPs by default as security measure:
```bash
# Temporary
sudo sysctl -w net.ipv4.conf.default.rp_filter=0
sudo sysctl -w net.ipv4.conf.all.rp_filter=0
sudo sysctl -w net.ipv4.conf.eth0.rp_filter=0

# Permanent
sudo nano /etc/sysctl.d/10-network-security.conf
```

Comment out these lines with `#`:
```
#net.ipv4.conf.default.rp_filter=1
#net.ipv4.conf.all.rp_filter=1
```

**Configure firewall** - GigE Vision uses port 3956 and UDP for streaming:
```bash
sudo ufw allow from 169.254.0.0/16 to any port 3956 proto tcp
sudo ufw allow from 169.254.0.0/16 to any port 3956 proto udp
sudo ufw allow from 169.254.0.0/16 proto udp
sudo ufw reload
```

**Set Pi's IP address**:
```bash
sudo ip addr add 169.254.0.1/16 dev eth0
```

Pi gets 169.254.0.1, camera will auto-assign something in same range.

### Verify Configuration

```bash
ip addr show eth0  # Should show 169.254.0.1/16
ip link show eth0  # Should show state UP
sysctl net.ipv4.conf.all.rp_filter  # Should show = 0
sysctl net.ipv4.conf.eth0.rp_filter  # Should show = 0
```

---

## Camera Discovery

### Connect Camera

Plug ethernet cable into Pi's ethernet port, power on camera. Wait 20-30 seconds for boot.

**LED indicators**:
- Flashing red = powered but no ethernet link
- Flashing green = ethernet connected, waiting for communication
- Solid green = actively streaming

### Discover Camera

```bash
cd ~/Downloads/ArenaSDK_v0.1.78_Linux_ARM64/ArenaSDK_Linux_ARM64/precompiledExamples/
sudo ./IpConfigUtility /list
```

Output:
```
[index]    MAC             IP              SUBNET          GATEWAY             IP CONFIG
[0]    1C0FAFCC1B89    169.254.0.10    255.255.0.0     0.0.0.0             DHCP= 0 Persistent Ip= 1 LLA = 1
```

### Set Persistent IP (optional but recommended)

Without this, camera picks random IP each boot. With it, always uses 169.254.0.10:

```bash
sudo ./IpConfigUtility /persist -i 0 -p true -a 169.254.0.10 -s 255.255.0.0 -g 0.0.0.0
sudo ./IpConfigUtility /config -i 0 -p true
```

---

## Making Configuration Persistent

Network settings reset after reboot by default. Make them permanent:

### Pi's IP Address

```bash
sudo mkdir -p /etc/network/interfaces.d
sudo nano /etc/network/interfaces.d/eth0
```

Add:
```
auto eth0
iface eth0 inet static
    address 169.254.0.1
    netmask 255.255.0.0
    mtu 9000
    post-up ethtool -G eth0 rx 8192 || true
```

Sets Pi IP, enables jumbo frames, increases ring buffer on boot.

### Prevent NetworkManager Interference

```bash
sudo nano /etc/NetworkManager/NetworkManager.conf
```

Add under `[main]`:
```
[keyfile]
unmanaged-devices=interface-name:eth0
```

Tells NetworkManager to ignore eth0.

### Already Persistent

- Socket buffers (in `/etc/sysctl.conf`)
- Reverse path filtering (in `/etc/sysctl.d/10-network-security.conf`)
- Firewall rules (ufw persists)
- Camera persistent IP (in camera firmware)

### Test

```bash
sudo reboot
```

After reboot:
```bash
ip addr show eth0 | grep 169.254.0.1
cd ~/Downloads/ArenaSDK_v0.1.78_Linux_ARM64/ArenaSDK_Linux_ARM64/precompiledExamples/
sudo ./IpConfigUtility /list
```

If camera appears, configuration is persistent.

---

## Testing Camera

### Quick Python Test

```python
python3
>>> from arena_api.system import system
>>> device = system.create_device()[0]
>>> print(f"Camera: {device.nodemap['DeviceModelName'].value}")
>>> device.start_stream()
>>> image = device.get_buffer()
>>> print(f"Captured: {image.width}x{image.height} pixels")
>>> device.requeue_buffer(image)
>>> device.stop_stream()
>>> system.destroy_device()
>>> exit()
```

### Live Preview Script

Save as `camera_preview.py`:

```python
from arena_api.system import system
import numpy as np
import cv2

devices = system.create_device()
device = devices[0]

print(f"Connected to: {device.nodemap['DeviceModelName'].value}")

device.start_stream()

try:
    while True:
        image = device.get_buffer()
        img_array = np.array(image.data).reshape((image.height, image.width))
        cv2.imshow('Camera Preview', img_array)
        device.requeue_buffer(image)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
except KeyboardInterrupt:
    print("\nStopping...")

finally:
    device.stop_stream()
    system.destroy_device()
    cv2.destroyAllWindows()
```

Run: `python3 camera_preview.py` (press 'q' to quit)

---

## Troubleshooting

Debug in sequence:

### 1. Check Physical Connection

```bash
ip link show eth0  # Should show "state UP"
```

If DOWN: check cable, try different cable, verify camera power LED.

### 2. Check Camera LED

- Flashing red: powered but no ethernet link (cable issue)
- Flashing green: link established, waiting for communication (software issue)
- Solid green: actively streaming (working)
- Off: not powered

### 3. Verify Pi's IP

```bash
ip addr show eth0  # Should show 169.254.0.1/16
```

If missing: `sudo ip addr add 169.254.0.1/16 dev eth0`

### 4. Check Network Settings

```bash
sysctl net.ipv4.conf.all.rp_filter  # Should be 0
sysctl net.ipv4.conf.eth0.rp_filter  # Should be 0
ip link show eth0 | grep mtu  # Should be 9000
sudo ethtool -g eth0  # Check RX buffer
```

If wrong, re-run network configuration.

### 5. Check Firewall

```bash
sudo ufw status  # Should show rules allowing 169.254.0.0/16
```

If missing, re-run firewall configuration.

### 6. Scan for Camera

```bash
sudo nmap -sn 169.254.0.0/16  # Find all devices
sudo nmap -p 3956 169.254.0.10  # Check GigE port
```

Camera MAC starts with `1C:0F:AF`. Port 3956 should be "open" or "filtered", not "closed".

### 7. Power Cycle

Unplug camera power, wait 10 seconds, plug back in. Wait 30 seconds, then try `sudo ./IpConfigUtility /list`.

### 8. Force Camera Reset

If camera has wrong IP:

```bash
sudo ./IpConfigUtility /force -m 1C0FAFCC1B89 -a 169.254.0.10 -s 255.255.0.0 -g 0.0.0.0
```

Replace MAC with your camera's actual MAC.

### 9. Check System Logs

```bash
dmesg | grep -i eth
journalctl -u NetworkManager | tail -20
```

### Common Issues

| Problem | Solution |
|---------|----------|
| IpConfigUtility finds nothing | Check Pi IP is set to 169.254.0.1 |
| LED flashing red | Cable issue, verify link is UP |
| LED flashing green but not detected | Firewall blocking, re-run firewall config |
| Port 3956 closed | Power cycle camera |
| Config lost after reboot | Follow persistence section |
| Slow/choppy streaming | Verify MTU=9000, RX buffer at max |

---

## Quick Reference

**Camera discovery**:
```bash
cd ~/Downloads/ArenaSDK_v0.1.78_Linux_ARM64/ArenaSDK_Linux_ARM64/precompiledExamples/
sudo ./IpConfigUtility /list
```

**Check network**:
```bash
ip addr show eth0
ip link show eth0
sysctl net.ipv4.conf.eth0.rp_filter
sudo ethtool -g eth0
```

**Network scan**:
```bash
sudo nmap -sn 169.254.0.0/16
ping 169.254.0.10
```

**Reset network**:
```bash
sudo ip link set eth0 down
sudo ip link set eth0 up
sudo ip addr add 169.254.0.1/16 dev eth0
```

---

## Development Workflow

Once camera is working, develop on MacBook while camera runs on Pi:

### SSH + Visual Output on Pi Monitor

```bash
# From MacBook
ssh stephen@<pi-wifi-ip>
```

Write code on MacBook using Cursor/VS Code with Remote-SSH, run on Pi, view output on Pi's monitor.

### X11 Forwarding (View on MacBook)

```bash
ssh -X stephen@<pi-ip>
```

GUI applications appear on MacBook.

### Mount Pi Filesystem on MacBook

```bash
# Requires SSHFS on MacBook
sshfs stephen@<pi-ip>:/home/stephen ~/pi-mount
```

Edit files locally, changes reflected on Pi instantly.

---

*Last Updated: November 27, 2025*