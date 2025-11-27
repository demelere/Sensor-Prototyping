#!/bin/bash

# Lucid Triton Camera Setup Script
# For Ubuntu 22.04/24.04 on Raspberry Pi 5 or Nvidia Jetson Orin Nano
# Run with: sudo bash setup_lucid_camera.sh

# Don't exit on error - handle errors gracefully
set +e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CAMERA_IP="169.254.0.10"
PI_IP="169.254.0.1"
SUBNET="255.255.0.0"
MTU=9000

# Track errors but continue
ERRORS=0

echo -e "${GREEN}=== Lucid Triton Camera Setup ===${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

# Get original user if script was run with sudo
ORIGINAL_USER="${SUDO_USER:-$USER}"
ORIGINAL_HOME=$(eval echo "~$ORIGINAL_USER")

# Step 1: Detect ethernet interface
echo -e "${YELLOW}Step 1: Detecting ethernet interface...${NC}"

# Try multiple detection methods
ETH_INTERFACE=""

# Method 1: Look for common interface names
for iface in eth0 enp3s0 enp0s31f6 eno1; do
    if ip link show "$iface" &>/dev/null; then
        ETH_INTERFACE="$iface"
        break
    fi
done

# Method 2: Find first non-loopback, non-wireless interface
if [ -z "$ETH_INTERFACE" ]; then
    ETH_INTERFACE=$(ip link show | grep -E '^[0-9]+: (eth|enp|eno)' | grep -v "wlan\|wlp\|lo" | head -1 | cut -d: -f2 | tr -d ' ')
fi

if [ -z "$ETH_INTERFACE" ]; then
    echo -e "${RED}Error: No ethernet interface found${NC}"
    echo "Available interfaces:"
    ip link show | grep "^[0-9]" | cut -d: -f2
    exit 1
fi

echo -e "${GREEN}Found ethernet interface: $ETH_INTERFACE${NC}"

# Verify interface is not wireless
if iw dev "$ETH_INTERFACE" info &>/dev/null; then
    echo -e "${RED}Warning: $ETH_INTERFACE appears to be wireless${NC}"
    echo "This script is for wired ethernet connections only."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""

# Step 2: Install prerequisites
echo -e "${YELLOW}Step 2: Installing prerequisites...${NC}"

# Update package list
if ! apt update 2>&1 | grep -q "Failed"; then
    echo -e "${GREEN}Package list updated${NC}"
else
    echo -e "${YELLOW}Warning: Package update had issues, continuing...${NC}"
    ((ERRORS++))
fi

# Install packages one by one for better error handling
PACKAGES="python3-pip python3-dev build-essential ethtool nmap"
for pkg in $PACKAGES; do
    if dpkg -l | grep -q "^ii  $pkg"; then
        echo -e "${GREEN}$pkg already installed${NC}"
    else
        if apt install -y "$pkg" &>/dev/null; then
            echo -e "${GREEN}Installed $pkg${NC}"
        else
            echo -e "${RED}Failed to install $pkg${NC}"
            ((ERRORS++))
        fi
    fi
done

echo ""

# Step 3: Check for Arena SDK
echo -e "${YELLOW}Step 3: Checking for Arena SDK...${NC}"
ARENA_SDK_PATH=""

# Common locations to check
SEARCH_PATHS=(
    "$ORIGINAL_HOME/Downloads/ArenaSDK_Linux_ARM64"
    "$ORIGINAL_HOME/ArenaSDK_Linux_ARM64"
    "/opt/ArenaSDK_Linux_ARM64"
    "$(pwd)/ArenaSDK_Linux_ARM64"
    "$ORIGINAL_HOME/Downloads/ArenaSDK_v0.1.78_Linux_ARM64/ArenaSDK_Linux_ARM64"
)

for path in "${SEARCH_PATHS[@]}"; do
    if [ -d "$path" ] && [ -f "$path/Arena_SDK_ARM64.conf" ]; then
        ARENA_SDK_PATH="$path"
        break
    fi
done

if [ -z "$ARENA_SDK_PATH" ]; then
    echo -e "${RED}Arena SDK not found. Please extract it to one of these locations:${NC}"
    echo "  - $ORIGINAL_HOME/Downloads/"
    echo "  - $ORIGINAL_HOME/"
    echo "  - /opt/"
    echo "  - Current directory"
    echo ""
    echo "Download from: https://thinklucid.com/downloads-hub/"
    exit 1
fi

echo -e "${GREEN}Found Arena SDK at: $ARENA_SDK_PATH${NC}"

# Install Arena SDK if not already installed
if [ ! -f "/usr/lib/libArena.so" ] && [ ! -f "/usr/local/lib/libArena.so" ]; then
    echo -e "${YELLOW}Installing Arena SDK...${NC}"
    cd "$ARENA_SDK_PATH"
    if sh Arena_SDK_ARM64.conf; then
        echo -e "${GREEN}Arena SDK installed${NC}"
    else
        echo -e "${RED}Arena SDK installation failed${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${GREEN}Arena SDK already installed${NC}"
fi

# Install Python bindings
echo -e "${YELLOW}Installing Python bindings...${NC}"
WHEEL_FILE=$(find "$ARENA_SDK_PATH" -name "arena_api-*.whl" | head -1)
if [ -n "$WHEEL_FILE" ]; then
    # Try installing for original user, not root
    if sudo -u "$ORIGINAL_USER" python3 -m pip install "$WHEEL_FILE" --break-system-packages &>/dev/null; then
        echo -e "${GREEN}Python bindings installed for $ORIGINAL_USER${NC}"
    elif python3 -m pip install "$WHEEL_FILE" --break-system-packages &>/dev/null; then
        echo -e "${GREEN}Python bindings installed${NC}"
    else
        echo -e "${YELLOW}Warning: Python bindings installation had issues${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}Warning: Python wheel file not found${NC}"
    ((ERRORS++))
fi
echo ""

# Step 4: Configure network
echo -e "${YELLOW}Step 4: Configuring network settings...${NC}"

# Bring interface up if down
if ! ip link show "$ETH_INTERFACE" | grep -q "state UP"; then
    ip link set "$ETH_INTERFACE" up
    sleep 2
fi

# Enable jumbo frames
if ip link set "$ETH_INTERFACE" mtu $MTU 2>/dev/null; then
    echo -e "${GREEN}Enabled jumbo frames (MTU=$MTU)${NC}"
else
    echo -e "${YELLOW}Warning: Could not set MTU to $MTU${NC}"
    ((ERRORS++))
fi

# Get max RX buffer
if command -v ethtool &>/dev/null; then
    MAX_RX=$(ethtool -g "$ETH_INTERFACE" 2>/dev/null | grep -A4 "Pre-set maximums" | grep "RX:" | head -1 | awk '{print $2}')
    if [ -n "$MAX_RX" ] && [ "$MAX_RX" -gt 0 ]; then
        if ethtool -G "$ETH_INTERFACE" rx "$MAX_RX" 2>/dev/null; then
            echo -e "${GREEN}Set RX buffer to maximum ($MAX_RX)${NC}"
        else
            echo -e "${YELLOW}Warning: Could not set RX buffer${NC}"
            ((ERRORS++))
        fi
    else
        echo -e "${YELLOW}Warning: Could not determine max RX buffer${NC}"
        MAX_RX=512  # Default fallback
    fi
else
    echo -e "${YELLOW}Warning: ethtool not available${NC}"
    MAX_RX=512
fi

# Increase socket buffers (only if not already set)
if ! grep -q "net.core.rmem_default=1048576" /etc/sysctl.conf 2>/dev/null; then
    echo "net.core.rmem_default=1048576" >> /etc/sysctl.conf
    echo "net.core.rmem_max=1048576" >> /etc/sysctl.conf
    sysctl -p &>/dev/null
    echo -e "${GREEN}Increased socket buffers${NC}"
else
    echo -e "${GREEN}Socket buffers already configured${NC}"
fi

# Disable reverse path filtering - CRITICAL for Link-Local
sysctl -w net.ipv4.conf.default.rp_filter=0 &>/dev/null
sysctl -w net.ipv4.conf.all.rp_filter=0 &>/dev/null
sysctl -w net.ipv4.conf."$ETH_INTERFACE".rp_filter=0 &>/dev/null

# Make reverse path filtering permanent
if [ -f /etc/sysctl.d/10-network-security.conf ]; then
    sed -i 's/^net.ipv4.conf.default.rp_filter=1/#net.ipv4.conf.default.rp_filter=1/' /etc/sysctl.d/10-network-security.conf
    sed -i 's/^net.ipv4.conf.all.rp_filter=1/#net.ipv4.conf.all.rp_filter=1/' /etc/sysctl.d/10-network-security.conf
    echo -e "${GREEN}Disabled reverse path filtering (persistent)${NC}"
else
    echo -e "${YELLOW}Note: 10-network-security.conf not found, settings temporary${NC}"
fi

echo ""

# Step 5: Configure firewall - CRITICAL
echo -e "${YELLOW}Step 5: Configuring firewall (CRITICAL)...${NC}"

# Check if ufw is installed and active
if command -v ufw &> /dev/null; then
    # Add rules (idempotent - won't duplicate)
    ufw allow from 169.254.0.0/16 to any port 3956 proto tcp comment "GigE Vision TCP" &>/dev/null
    ufw allow from 169.254.0.0/16 to any port 3956 proto udp comment "GigE Vision UDP" &>/dev/null
    ufw allow from 169.254.0.0/16 proto udp comment "GigE Vision streaming" &>/dev/null
    
    # Reload firewall
    if ufw reload &>/dev/null; then
        echo -e "${GREEN}Firewall rules configured and reloaded${NC}"
    else
        echo -e "${YELLOW}Warning: Firewall reload had issues${NC}"
        ((ERRORS++))
    fi
    
    # Verify rules were added
    if ufw status | grep -q "169.254"; then
        echo -e "${GREEN}Verified: Firewall rules active${NC}"
    else
        echo -e "${RED}Warning: Firewall rules not showing in status${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}UFW not installed - checking iptables...${NC}"
    
    # Check if iptables has restrictive policy
    if iptables -L INPUT -n | grep -q "policy DROP"; then
        echo -e "${RED}Warning: iptables has DROP policy but no tool to configure${NC}"
        echo "Install ufw: sudo apt install ufw"
        ((ERRORS++))
    fi
fi
echo ""

# Step 6: Set Pi's IP address
echo -e "${YELLOW}Step 6: Setting IP address...${NC}"

# Check if NetworkManager is running and interfering
NM_MANAGING=false
if systemctl is-active NetworkManager &>/dev/null; then
    if nmcli dev show "$ETH_INTERFACE" 2>/dev/null | grep -q "managed.*yes"; then
        NM_MANAGING=true
        echo -e "${YELLOW}NetworkManager is managing $ETH_INTERFACE - stopping temporarily${NC}"
        systemctl stop NetworkManager
        sleep 2
    fi
fi

# Flush any existing IPs on this interface
if ip addr show "$ETH_INTERFACE" | grep -q "inet "; then
    echo "Flushing existing IPs..."
    ip addr flush dev "$ETH_INTERFACE" 2>/dev/null
fi

# Set Link-Local IP
if ip addr add "$PI_IP/16" dev "$ETH_INTERFACE" 2>/dev/null; then
    echo -e "${GREEN}Set $ETH_INTERFACE to $PI_IP${NC}"
else
    # IP might already be set
    if ip addr show "$ETH_INTERFACE" | grep -q "$PI_IP"; then
        echo -e "${GREEN}$PI_IP already configured on $ETH_INTERFACE${NC}"
    else
        echo -e "${RED}Failed to set IP address${NC}"
        ((ERRORS++))
    fi
fi

# Ensure interface is up
ip link set "$ETH_INTERFACE" up

# Verify IP is set
if ip addr show "$ETH_INTERFACE" | grep -q "$PI_IP"; then
    echo -e "${GREEN}Verified: $PI_IP is active${NC}"
else
    echo -e "${RED}Error: IP not active on interface${NC}"
    ((ERRORS++))
fi

echo ""

# Step 7: Make configuration persistent
echo -e "${YELLOW}Step 7: Making configuration persistent...${NC}"

# Create network interfaces directory
mkdir -p /etc/network/interfaces.d

# Create interface configuration
cat > /etc/network/interfaces.d/"$ETH_INTERFACE" << EOF
auto $ETH_INTERFACE
iface $ETH_INTERFACE inet static
    address $PI_IP
    netmask $SUBNET
    mtu $MTU
    post-up ethtool -G $ETH_INTERFACE rx $MAX_RX || true
EOF

echo -e "${GREEN}Created persistent network configuration${NC}"

# Configure NetworkManager to ignore interface
if [ -f /etc/NetworkManager/NetworkManager.conf ]; then
    if ! grep -q "unmanaged-devices=interface-name:$ETH_INTERFACE" /etc/NetworkManager/NetworkManager.conf; then
        # Add keyfile section if it doesn't exist
        if ! grep -q "\[keyfile\]" /etc/NetworkManager/NetworkManager.conf; then
            echo "" >> /etc/NetworkManager/NetworkManager.conf
            echo "[keyfile]" >> /etc/NetworkManager/NetworkManager.conf
        fi
        sed -i "/\[keyfile\]/a unmanaged-devices=interface-name:$ETH_INTERFACE" /etc/NetworkManager/NetworkManager.conf
        echo -e "${GREEN}Configured NetworkManager to ignore $ETH_INTERFACE${NC}"
    else
        echo -e "${GREEN}NetworkManager already configured${NC}"
    fi
fi
echo ""

# Step 8: Wait for camera and discover
echo -e "${YELLOW}Step 8: Waiting for camera...${NC}"
echo "Please ensure camera is connected and powered on."
echo "Waiting 30 seconds for camera to boot..."
sleep 30

# Check for camera on network
echo -e "${YELLOW}Scanning for camera...${NC}"
CAMERA_FOUND=$(nmap -sn 169.254.0.0/16 2>/dev/null | grep -i "1C:0F:AF" || true)

if [ -n "$CAMERA_FOUND" ]; then
    echo -e "${GREEN}Camera found on network!${NC}"
    echo "$CAMERA_FOUND"
else
    echo -e "${YELLOW}Camera not found yet. This might be normal if:${NC}"
    echo "  - Camera is still booting"
    echo "  - Camera is not powered on"
    echo "  - Cable is not connected"
fi
echo ""

# Step 9: Try IpConfigUtility
echo -e "${YELLOW}Step 9: Testing camera discovery...${NC}"
IPCONFIG_PATH="$ARENA_SDK_PATH/precompiledExamples/IpConfigUtility"

if [ -f "$IPCONFIG_PATH" ]; then
    cd "$(dirname "$IPCONFIG_PATH")"
    echo "Running: ./IpConfigUtility /list"
    echo ""
    
    # Run and capture output
    if CAMERA_OUTPUT=$(timeout 10 ./IpConfigUtility /list 2>&1); then
        echo "$CAMERA_OUTPUT"
        
        # Check if camera was found
        if echo "$CAMERA_OUTPUT" | grep -q "1C0FAF"; then
            echo ""
            echo -e "${GREEN}=== Camera detected successfully! ===${NC}"
        else
            echo ""
            echo -e "${YELLOW}No cameras detected yet. This is normal if:${NC}"
            echo "  - Camera is still booting (wait 30+ seconds)"
            echo "  - Camera not powered on"
            echo "  - Cable not connected"
        fi
    else
        echo -e "${YELLOW}IpConfigUtility timed out or failed${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}IpConfigUtility not found at expected location${NC}"
    echo "Expected: $IPCONFIG_PATH"
    ((ERRORS++))
fi
echo ""

# Summary
echo "==================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}=== Setup Complete (no errors) ===${NC}"
else
    echo -e "${YELLOW}=== Setup Complete (with $ERRORS warnings/errors) ===${NC}"
fi
echo ""
echo "Configuration summary:"
echo "  - Interface: $ETH_INTERFACE"
echo "  - Pi IP: $PI_IP"
echo "  - MTU: $MTU"
echo "  - RX Buffer: ${MAX_RX:-unknown}"
echo "  - Expected camera IP: $CAMERA_IP"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo -e "${YELLOW}Warnings/errors occurred. Run diagnostics:${NC}"
    echo "  bash check_camera.sh"
    echo ""
fi

echo "Next steps:"
echo ""
echo "  1. If camera not detected, ensure it's powered and wait, then:"
echo "     cd $ARENA_SDK_PATH/precompiledExamples/"
echo "     sudo ./IpConfigUtility /list"
echo ""
echo "  2. Set persistent IP on camera (if needed):"
echo "     sudo ./IpConfigUtility /persist -i 0 -p true -a $CAMERA_IP -s $SUBNET -g 0.0.0.0"
echo "     sudo ./IpConfigUtility /config -i 0 -p true"
echo ""
echo "  3. Test camera access:"
echo "     python3 -c 'from arena_api.system import system; print(system.create_device())'"
echo ""
echo "  4. Reboot to verify persistence:"
echo "     sudo reboot"
echo ""
echo "  5. After reboot, verify camera still detected:"
echo "     sudo ./IpConfigUtility /list"
echo ""