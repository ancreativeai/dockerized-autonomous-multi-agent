# Networking Guide — How Tailscale Works

## The Problem: IP Addresses Change

When you move between WiFi networks, your **public IP address changes**:

```
McDonald's WiFi    → Public IP: 1.2.3.4
Starbucks WiFi     → Public IP: 5.6.7.8
Home Broadband     → Public IP: 9.10.11.12
wireless@sgx       → Public IP: 11.12.13.14
```

Each network (each ISP, each WiFi hotspot) assigns your device a different public IP. If you tried to reach your server by public IP, **the address would be wrong within hours**.

## Solution: Stable Device Identity

Tailscale solves this by **giving each device a stable identity that doesn't depend on public IP**.

Instead of tracking devices by IP address, Tailscale tracks devices by **cryptographic keys** — digital fingerprints that prove "this is your device."

### How It Works

**Setup (one-time):**
1. You install Tailscale on your laptop
2. Log in with your Tailscale account
3. Tailscale generates a **cryptographic key pair** (public/private) for your laptop
4. Assigns you a stable **Tailscale IP** (e.g., `100.104.71.39`)
5. This IP **never changes**, no matter where you go

**Daily use (from anywhere):**

```
Your laptop (public IP changes)
    ↓
Tailscale (checks your device key)
    ↓
Tailscale Central Coordination Server
    ↓
Updates: "Your device = Tailscale IP 100.104.71.39, now at public IP 1.2.3.4"
    ↓
Other devices can now reach you at 100.104.71.39 (which internally routes through public IP 1.2.3.4)
```

When you move to a new WiFi:

```
New WiFi assigns you public IP 5.6.7.8
    ↓
Your laptop tells Tailscale: "I'm still device-xyz, now at public IP 5.6.7.8"
    ↓
Tailscale updates: 100.104.71.39 → now at 5.6.7.8
    ↓
ssh root@100.107.239.95 still works! ✅
```

## What Changes, What Doesn't

### Public IP (assigned by ISP/WiFi provider)

**CHANGES when you:**
- Connect to McDonald's WiFi
- Connect to Starbucks WiFi  
- Go home and connect to your home WiFi
- Connect to any new network

**Why:** Each network is a different ISP or router. They assign IPs from their own pools.

### Private IP (assigned by your local router)

**CHANGES when you:**
- Connect to any new WiFi router (gets a new 192.168.x.x or 10.x.x.x)

**Why:** Each router manages its own local network.

```
McDonald's router    → 192.168.1.5   (McDonald's assigns this)
Starbucks router     → 192.168.0.10  (Starbucks assigns this)
Home router          → 192.168.1.x   (Your home router assigns this)
```

### Tailscale IP (assigned by Tailscale account)

**NEVER CHANGES** — tied to your device account, not the network

```
McDonald's WiFi  → Tailscale IP: 100.104.71.39
Starbucks WiFi   → Tailscale IP: 100.104.71.39
Home WiFi        → Tailscale IP: 100.104.71.39
Airplane WiFi    → Tailscale IP: 100.104.71.39 ✅
```

## Visual Summary

```
┌─────────────────────────────────────────────────────────┐
│  Your Device (Laptop)                                   │
├─────────────────────────────────────────────────────────┤
│  Device Key: (cryptographic identity - NEVER CHANGES)   │
│  Tailscale IP: 100.104.71.39 (ALWAYS THE SAME)          │
└─────────────────────────────────────────────────────────┘
                        ↓
            Tailscale Central Server
            (keeps track of your key)
                        ↓
            Updates: 100.104.71.39 → public IP X.X.X.X
                        ↓
        (Public IP changes as you move, but server knows!)
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Other Devices (Server, etc.)                           │
├─────────────────────────────────────────────────────────┤
│  Can always reach YOU via: 100.104.71.39                │
│  (Server maps that to your current public IP internally)│
└─────────────────────────────────────────────────────────┘
```

## Real Example: Traveling

**At home on WiFi:**
```
Your public IP: 9.10.11.12
Your Tailscale IP: 100.104.71.39
ssh root@100.107.239.95 ✅ Works!
```

**Go to McDonald's WiFi:**
```
Your public IP: 1.2.3.4 (new ISP/network)
Your Tailscale IP: 100.104.71.39 (unchanged - still YOU)
ssh root@100.107.239.95 ✅ Still works!
```

**Go to Starbucks WiFi:**
```
Your public IP: 5.6.7.8 (different ISP/network)
Your Tailscale IP: 100.104.71.39 (still the same)
ssh root@100.107.239.95 ✅ Still works!
```

The server at `100.107.239.95` doesn't care about your public IP. It reaches you via your Tailscale IP, which is stable.

## Why This Matters for Security

Traditional approach (IP-based):
- You give someone your IP address
- If it changes, connection breaks
- Firewalls have to allow that IP
- Anyone on the internet can try to reach you (if you're not firewalled)

Tailscale approach (key-based):
- Your Tailscale IP is tied to your cryptographic key (proves it's really you)
- IP can change freely, connection stays up
- No firewall rules needed (Tailscale handles it)
- **Only people in your tailnet can see your Tailscale IP** (private, encrypted network)

## Summary Table

| Property | Depends On | Changes | Example |
|---|---|---|---|
| **Public IP** | ISP / WiFi network | Yes | 1.2.3.4, 5.6.7.8 |
| **Private IP** | Local router | Yes | 192.168.1.5 |
| **Tailscale IP** | Your device account | **No** ✅ | 100.104.71.39 (always) |

**Bottom line:** Tailscale gives you a stable IP tied to your device identity, not your location. That's why you can `ssh root@100.107.239.95` from anywhere. 🌍

---

**Next:** [Agent Stack Guide](agent-stack-guide.md) for the actual URLs and commands.
