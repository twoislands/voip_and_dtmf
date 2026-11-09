# Portenta X8 VoIP and DTMF

A standalone SIP endpoint built on the **Arduino Portenta X8**. It answers incoming calls, carries two-way audio, and sends and receives RFC 4733 keypad events. Ethernet is the primary connection. When the network route switches to LTE, the unit registers again using the same SIP account. The Max Carrier provides battery backup for the unit.

**Prototype status** — The Python event parser has been checked. The Arduino sketch, LTE failover, and battery switchover still need testing on the assembled hardware.

## How it works

| Component | Role |
| --- | --- |
| [Baresip](https://github.com/baresip/baresip) on the X8's Linux processor | SIP registration, auto-answer, G.711 audio, and RTP DTMF |
| [Linux companion](gateway.py) | Monitors the route to the SIP server, restarts Baresip after a route change, and passes received digits to the sketch |
| [Arduino sketch](VoipDtmf/VoipDtmf.ino) on the X8's microcontroller | Receives digits over RPC and selects a reply. In the demo, pressing `*` during a call sends `5` back. |

## Hardware and budget

| Item | Part or specification | Estimated cost |
| --- | --- | ---: |
| Arduino Portenta X8 | ABX00049 | €118.16 |
| Portenta Max Carrier | ABX00043, with RJ45, DC input, and battery charging | €204.23 |
| Arduino Pro 4G GNSS Global | TPX00200, Quectel EG25-G | €72.00 |
| Arduino antenna kit | TPX00219 | €7.50 |
| Mains adapter | 12 V DC, 3 A budgeted. Match plug and polarity to the carrier. | €17–€25 |
| Backup cell | Compatible 3.7 V 18650 Li-ion. Confirm fit, discharge rating, and charging compatibility. | €8–€15 |
| USB-A headset or audio adapter | Linux-compatible microphone and speaker | €15–€25 |
| Ethernet cable | Short Cat 6 patch cable | €3–€6 |
| Enclosure and mounting hardware | Indoor enclosure and standoffs | €18–€35 |

**Patras, Greece budget as of 9 November 2026** — €463–€508 in parts at the displayed sale prices, or about €465–€535 with a delivery allowance. At the displayed regular board prices, allow about €660–€735 including delivery. Labor, the LTE data SIM and plan, and SIP service fees are separate. Check the checkout price and delivery before ordering. [X8 price](https://store.arduino.cc/products/portenta-x8) · [Carrier price](https://store.arduino.cc/products/portenta-max-carrier) · [Modem price](https://store.arduino.cc/products/4g-module-global) · [Antenna price](https://store.arduino.cc/products/4g-module-antenna)

## Setup

### 1. Assemble and flash

Fit the X8, modem, antennas, and data SIM according to Arduino's instructions for the Max Carrier and add-in modem. Connect Ethernet, USB audio, and the DC adapter. Fit a compatible battery for the backup test. [Max Carrier manual](https://docs.arduino.cc/tutorials/portenta-max-carrier/user-manual) · [Portenta X8 manual](https://docs.arduino.cc/tutorials/portenta-x8/user-manual) · [Pro 4G module](https://docs.arduino.cc/hardware/pro-4g-module/)

Open [VoipDtmf.ino](VoipDtmf/VoipDtmf.ino) in Arduino IDE, select **Portenta X8**, and upload it. The Linux image needs the `m4-proxy` service for the sketch's RPC connection. [Arduino RPC example](https://docs.arduino.cc/tutorials/portenta-x8/edge-ai-docker-container/)

### 2. Set up Ethernet and LTE

Activate the modem with the SIM provider's APN. Keep both connections active and give Ethernet a lower route metric so it is preferred. Use the actual profile names shown by `nmcli connection show`.

```sh
nmcli connection show
sudo nmcli connection modify "WIRED PROFILE" ipv4.route-metric 100
sudo nmcli connection modify "CELLULAR PROFILE" ipv4.route-metric 600 connection.autoconnect yes
```

Reconnect both profiles to apply the settings. Disconnect Wi-Fi during the test so the two intended paths are easy to verify. For an upstream outage while the Ethernet link stays up, enable and test NetworkManager's connectivity checking. A SIP server outage requires its own reachability policy. [NetworkManager connectivity settings](https://www.networkmanager.dev/docs/api/latest/NetworkManager.conf.html)

### 3. Configure SIP and run the container

Run the commands below on the X8 from the project root. Copy the example settings to a directory outside the repository and keep SIP credentials in that copy.

```sh
config_dir="$HOME/.config/portenta-voip"
install -d -m 700 "$config_dir"
install -m 600 config/accounts "$config_dir/accounts"
install -m 600 config/config "$config_dir/config"
```

Edit `"$config_dir/accounts"` with your SIP extension, registrar, and credentials. Use a test extension and restrict auto-answer to calls authorized by your PBX. The registrar must be reachable from both Ethernet and LTE. The included configuration assumes a stable IPv4 address and a test network that permits SIP and RTP without TLS or SRTP. [Baresip account settings](https://github.com/baresip/baresip/wiki/Accounts)

Replace `192.0.2.10` with the real IPv4 address of your registrar or outbound proxy.

```sh
sudo docker build -t portenta-voip .
sudo docker run -d --name portenta-voip --init --restart unless-stopped --network host \
  --device /dev/snd --mount "type=bind,source=$config_dir,target=/config" \
  -e PBX_IPV4=192.0.2.10 portenta-voip
sudo docker logs -f portenta-voip
```

If your USB audio device is missing from calls, set `audio_source`, `audio_player`, and `audio_alert` in the copied `config` file to the appropriate ALSA device and restart the container. If the image exposes the Arduino RPC proxy at a different address, add `-e M4_PROXY=ADDRESS` to the Docker command.

## Bench tests

| Test | Expected result |
| --- | --- |
| Call the SIP extension from a softphone set to RTP Events. | The unit answers and passes audio in both directions. |
| Press `5` twice with a pause, then press `*`. | The log shows two received `5` digits and one `*`. The PBX or an RTP capture shows the unit sending one `5` in reply. |
| Unplug Ethernet, then reconnect it after a successful LTE call. | The same account registers over LTE, then returns to Ethernet. Place a new call and repeat the DTMF test after each switch. |
| Unplug the mains adapter during an LTE call. | The unit stays powered on battery. Measure runtime under load and check charging after restoring mains. |
| Reboot the unit. | The container starts and the extension registers without a PC attached. |

An active call can drop when the SIP client restarts during a network change. The internal battery powers the unit itself. A local router or PBX needs its own backup power if it must stay reachable during an outage.
