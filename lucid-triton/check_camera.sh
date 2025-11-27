#!/bin/bash

# Lucid Triton Camera Diagnostic Script
# Checks all network and camera configuration
# Run with: bash check_camera.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== Lucid Triton Camera Diagnostics ==="
echo ""

# Detect ethernet interface
ETH_INTERFACE=$(ip link show | grep -E '^[0-9]+: (eth|enp)' | head -1 | cut -d: -f2 | tr -d ' ')

if [ -z "$ETH_INTERFACE" ]; then
    echo -e "${RED}Error: No ethernet interface found${NC}"
    exit 1
fi

echo "Ethernet Interface: $ETH_INTERFACE"
echo ""

# Check 1: Physical connection
echo -e "${YELLOW}[1] Physical Connection${NC}"
LINK_STATE=$(ip link show "$ETH_INTERFACE" | grep -o "state [A-Z]*" | cut -d' ' -f2)
if [ "$LINK_STATE" = "UP" ]; then
    echo -e "${GREEN}✓ Link is UP${NC}"
else
    echo -e "${RED}✗ Link is DOWN - check cable${NC}"
fi
echo ""

# Check 2: IP address
echo -e "${YELLOW}[2] IP Address Configuration${NC}"
IP_ADDR=$(ip addr show "$ETH_INTERFACE" | grep "inet 169.254" | awk '{print $2}')
if [ -n "$IP_ADDR" ]; then
    echo -e "${GREEN}✓ IP configured: $IP_ADDR${NC}"
else
    echo -e "${RED}✗ No Link-Local IP configured${NC}"
    echo "  Fix: sudo ip addr add 169.254.0.1/16 dev $ETH_INTERFACE"
fi
echo ""

# Check 3: MTU
echo -e "${YELLOW}[3] MTU (Jumbo Frames)${NC}"
MTU=$(ip link show "$ETH_INTERFACE" | grep -o "mtu [0-9]*" | cut -d' ' -f2)
if [ "$MTU" = "9000" ]; then
    echo -e "${GREEN}✓ MTU is 9000 (jumbo frames enabled)${NC}"
else
    echo -e "${YELLOW}⚠ MTU is $MTU (recommended: 9000)${NC}"
    echo "  Fix: sudo ip link set $ETH_INTERFACE mtu 9000"
fi
echo ""

# Check 4: Reverse path filtering
echo -e "${YELLOW}[4] Reverse Path Filtering${NC}"
RP_FILTER_ALL=$(sysctl -n net.ipv4.conf.all.rp_filter)
RP_FILTER_IF=$(sysctl -n net.ipv4.conf."$ETH_INTERFACE".rp_filter)
if [ "$RP_FILTER_ALL" = "0" ] && [ "$RP_FILTER_IF" = "0" ]; then
    echo -e "${GREEN}✓ Reverse path filtering disabled${NC}"
else
    echo -e "${RED}✗ Reverse path filtering enabled (blocks Link-Local)${NC}"
    echo "  Fix: sudo sysctl -w net.ipv4.conf.all.rp_filter=0"
    echo "       sudo sysctl -w net.ipv4.conf.$ETH_INTERFACE.rp_filter=0"
fi
echo ""

# Check 5: RX buffer
echo -e "${YELLOW}[5] RX Buffer Size${NC}"
if command -v ethtool &> /dev/null; then
    CURRENT_RX=$(sudo ethtool -g "$ETH_INTERFACE" 2>/dev/null | grep -A4 "Current hardware" | grep "RX:" | head -1 | awk '{print $2}')
    MAX_RX=$(sudo ethtool -g "$ETH_INTERFACE" 2>/dev/null | grep -A4 "Pre-set maximums" | grep "RX:" | head -1 | awk '{print $2}')
    if [ -n "$CURRENT_RX" ] && [ -n "$MAX_RX" ]; then
        if [ "$CURRENT_RX" -eq "$MAX_RX" ]; then
            echo -e "${GREEN}✓ RX buffer at maximum: $CURRENT_RX${NC}"
        else
            echo -e "${YELLOW}⚠ RX buffer: $CURRENT_RX (max: $MAX_RX)${NC}"
            echo "  Fix: sudo ethtool -G $ETH_INTERFACE rx $MAX_RX"
        fi
    fi
else
    echo -e "${YELLOW}⚠ ethtool not installed${NC}"
fi
echo ""

# Check 6: Socket buffers
echo -e "${YELLOW}[6] Socket Buffers${NC}"
RMEM_DEFAULT=$(sysctl -n net.core.rmem_default)
RMEM_MAX=$(sysctl -n net.core.rmem_max)
if [ "$RMEM_DEFAULT" -ge "1048576" ] && [ "$RMEM_MAX" -ge "1048576" ]; then
    echo -e "${GREEN}✓ Socket buffers configured (1MB+)${NC}"
else
    echo -e "${YELLOW}⚠ Socket buffers: default=$RMEM_DEFAULT, max=$RMEM_MAX${NC}"
    echo "  Recommended: 1048576"
fi
echo ""

# Check 7: Firewall
echo -e "${YELLOW}[7] Firewall Rules${NC}"
if command -v ufw &> /dev/null; then
    UFW_STATUS=$(sudo ufw status 2>/dev/null | grep -c "169.254" || echo "0")
    if [ "$UFW_STATUS" -gt "0" ]; then
        echo -e "${GREEN}✓ UFW rules configured for Link-Local${NC}"
    else
        echo -e "${RED}✗ UFW rules missing for Link-Local network${NC}"
        echo "  Fix: sudo ufw allow from 169.254.0.0/16"
    fi
    
    # Check iptables
    IPTABLES_POLICY=$(sudo iptables -L INPUT -n | head -1 | grep -o "policy [A-Z]*" | cut -d' ' -f2)
    if [ "$IPTABLES_POLICY" = "DROP" ]; then
        echo -e "${YELLOW}⚠ Default INPUT policy is DROP (need explicit allow rules)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ UFW not installed${NC}"
fi
echo ""

# Check 8: NetworkManager
echo -e "${YELLOW}[8] NetworkManager Status${NC}"
if systemctl is-active NetworkManager &> /dev/null; then
    if [ -f /etc/NetworkManager/NetworkManager.conf ]; then
        if grep -q "unmanaged-devices=interface-name:$ETH_INTERFACE" /etc/NetworkManager/NetworkManager.conf; then
            echo -e "${GREEN}✓ NetworkManager configured to ignore $ETH_INTERFACE${NC}"
        else
            echo -e "${YELLOW}⚠ NetworkManager active and managing $ETH_INTERFACE${NC}"
            echo "  May cause DHCP conflicts with Link-Local"
        fi
    fi
else
    echo -e "${GREEN}✓ NetworkManager not running${NC}"
fi
echo ""

# Check 9: Network scan
echo -e "${YELLOW}[9] Network Scan for Camera${NC}"
if command -v nmap &> /dev/null; then
    echo "Scanning 169.254.0.0/16 for Lucid cameras..."
    CAMERA_SCAN=$(sudo nmap -sn 169.254.0.0/16 2>/dev/null | grep -B2 "1C:0F:AF" || echo "")
    if [ -n "$CAMERA_SCAN" ]; then
        echo -e "${GREEN}✓ Camera found on network:${NC}"
        echo "$CAMERA_SCAN"
    else
        echo -e "${RED}✗ No Lucid camera found on network${NC}"
        echo "  Check: camera power, LED status, cable connection"
    fi
else
    echo -e "${YELLOW}⚠ nmap not installed${NC}"
    echo "  Install: sudo apt install nmap"
fi
echo ""

# Check 10: ARP/Neighbor table
echo -e "${YELLOW}[10] ARP/Neighbor Table${NC}"
NEIGHBOR=$(ip neigh show | grep "169.254" || echo "")
if [ -n "$NEIGHBOR" ]; then
    echo -e "${GREEN}✓ Link-Local devices in neighbor table:${NC}"
    echo "$NEIGHBOR"
else
    echo -e "${YELLOW}⚠ No Link-Local devices in neighbor table${NC}"
fi
echo ""

# Check 11: Persistent configuration
echo -e "${YELLOW}[11] Persistent Configuration${NC}"
if [ -f "/etc/network/interfaces.d/$ETH_INTERFACE" ]; then
    echo -e "${GREEN}✓ Persistent network config exists${NC}"
else
    echo -e "${YELLOW}⚠ No persistent network config - settings will be lost on reboot${NC}"
fi

if grep -q "net.core.rmem" /etc/sysctl.conf 2>/dev/null; then
    echo -e "${GREEN}✓ Socket buffers persistent in sysctl.conf${NC}"
else
    echo -e "${YELLOW}⚠ Socket buffers not persistent${NC}"
fi

if [ -f /etc/sysctl.d/10-network-security.conf ]; then
    if grep -q "^#.*rp_filter=1" /etc/sysctl.d/10-network-security.conf; then
        echo -e "${GREEN}✓ Reverse path filtering permanently disabled${NC}"
    else
        echo -e "${YELLOW}⚠ Reverse path filtering may re-enable on reboot${NC}"
    fi
fi
echo ""

# Check 12: Arena SDK
echo -e "${YELLOW}[12] Arena SDK${NC}"
if [ -f "/usr/lib/libArena.so" ] || [ -f "/usr/local/lib/libArena.so" ]; then
    echo -e "${GREEN}✓ Arena SDK library found${NC}"
else
    echo -e "${RED}✗ Arena SDK not installed${NC}"
fi

if python3 -c "import arena_api" 2>/dev/null; then
    echo -e "${GREEN}✓ Python bindings installed${NC}"
else
    echo -e "${YELLOW}⚠ Python bindings not installed${NC}"
fi
echo ""

# Summary
echo "==================================="
echo -e "${GREEN}Diagnostics Complete${NC}"
echo ""
echo "If camera not detected:"
echo "  1. Check all items marked with ✗ or ⚠"
echo "  2. Verify camera LED (flashing green = waiting for communication)"
echo "  3. Try: sudo ./IpConfigUtility /list"
echo "  4. Check logs: dmesg | grep -i eth"