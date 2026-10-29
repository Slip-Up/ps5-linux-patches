# ps5-linux-patches — HDMI test build

Temporary notes for testing the HDMI and USB-C changes before submitting the PR.
This candidate is based on main `730b80e` and Linux 7.2.3.

## Check your HDMI converter first

Run on the console:

```bash
sudo dmesg | grep -F 'HDMI IC Type'
```

Look for `HDMI IC Type [FLAVA3]` or `HDMI IC Type [VERDE]`. If the boot log has
rolled over, try:

```bash
sudo journalctl -k -b --no-pager | grep -F 'HDMI IC Type'
```

No result means the type has not been identified from the available log; do not
guess from the console model.

- **FLAVA3:** the new HDMI modes, colour handling, native FRL, 4:2:0, recovery
  and ALLM work targets this converter on the physical HDMI output.
- **VERDE:** no new converter features are added. Reports of regressions in
  existing output are useful, but the FLAVA3 options do not enable them on VERDE.
- **USB-C:** the default-off DP policy is a separate change, not a FLAVA3 feature.
  The HDMI options do not configure native USB-C DisplayPort output.
- **PS5 Pro:** upstream support is retained; these HDMI changes have not been
  tested on Pro. Check the converter rather than assuming compatibility.

## What is new

- Extended FLAVA3 modes and improved SDR/HDR, colour depth and RGB range handling.
- A shared GPU/bridge output plan for native FRL, keeping timing, format, depth,
  range and HDR settings consistent.
- Native FRL output, including supported 4K100/120 modes and native 4:2:0.
- Bounded recovery after FRL setup failures, with stale recovery work discarded
  after a disconnect or display change.
- ALLM on displays that advertise it, including live changes without stalling
  the display commit.
- USB-C DP policy disabled by default so it does not reset an attached boot drive.

## Defaults

No extra boot arguments are needed for these changes:

| Setting | Default | Effect |
|---|---|---|
| `hdmi.extended_modes` | `1` | Allow additional supported FLAVA3 modes without forcing them to be preferred. `0` disables this extension; `2` also prefers extended modes. |
| Colour/HDR handling | Automatic | Apply the requested supported colour, depth and range settings. HDR still needs to be enabled by the desktop or application. |
| `hdmi.hdcp_mode` | `3` | HDCP off, with the HDCP 2.2 bit set, to avoid authentication failures leaving video muted. Native FRL fixes its HDCP mode to `3` independently of this parameter. |
| `hdmi.allm_avi` | `1` | Clear the TMDS AVI IT/content-type hints when ALLM policy is enabled on a capable display. This does not enable ALLM itself. |
| `usbc_dp.enable` | `0` | Leave USB-C DP policy programming disabled. |

Mode availability still depends on the display, cable, reported capabilities and
link bandwidth. This build does not add VRR or DSC, and does not promise every
format/depth at 4K120. In particular, do not expect uncompressed 4K120 RGB 10-bit.

## Features that are off by default

Add these to the **test kernel's command line** using your existing PS5 Linux
launcher/boot method. These are boot arguments, not shell commands. Keep your
working kernel and its command line available for returning to the baseline.

| Argument | What it enables |
|---|---|
| `hdmi.frl_4k120=1` | Native FRL, including supported 4K100/120 modes. |
| `hdmi.frl_yuv420=1` | Allow native FRL 4:2:0 as a fallback. Requires native FRL enabled. |
| `hdmi.frl_yuv420=2` | Prefer native FRL 4:2:0 when the display and mode allow it. Requires native FRL enabled. |
| `hdmi.frl_recovery=1` | Retry legal format/depth combinations after a native FRL failure, then fall back to an available mode. |
| `hdmi.allm=1` | Follow the DRM Game content type. Requires an ALLM-capable display and an application/compositor that sets the property. |
| `hdmi.allm=2` | Request ALLM whenever the display supports it. Works with supported TMDS and FRL output; does not require 4K120. |

The default for each feature above is `0`. Start with native FRL alone, then add
one option at a time. For a combined FRL/4:2:0/recovery/ALLM test:

```text
hdmi.frl_4k120=1 hdmi.frl_yuv420=2 hdmi.frl_recovery=1 hdmi.allm=2
```

Enabling an option does not select a resolution or turn HDR on. Select those in
the desktop/application afterward. ALLM is automatic low-latency mode, not VRR.

`usbc_dp.enable=1` opts back into USB-C DP policy programming. Enabling it can
reset a device on the front USB-C port; do not use it with the running OS drive
on that port. USB-C DP/PSVR2 output has not been tested in this candidate.

## Check the running settings

```bash
uname -r
cat /proc/cmdline
for p in extended_modes hdcp_mode frl_4k120 frl_yuv420 frl_recovery allm allm_avi frl_rate frl_failed allm_sink allm_active allm_valid; do
    f="/sys/module/hdmi/parameters/$p"
    [ ! -r "$f" ] || printf '%s=%s\n' "$p" "$(cat "$f")"
done
cat /sys/module/usbc_dp/parameters/enable
```

Boolean parameters may show `Y`/`N`. Missing parameters can indicate that the
expected candidate is not running. `allm_sink=Y` means the display advertises
ALLM; `allm_active` is meaningful only with `allm_valid=Y`. `frl_rate` is the
converter's last EDID notification report, not proof of the current output mode.
Check the display's information screen and the kernel's mode/setup messages too.

## Suggested test order

1. **Defaults:** boot without optional HDMI arguments. Check normal desktop
   output, 1080p/1440p/4K60 where offered, SDR/HDR switching, audio and RGB range.
   Check for washed-out blacks, crushed shadows, wrong colours or blank output.
2. **Native FRL:** enable `hdmi.frl_4k120=1`. Try 4K60 and 4K120 where offered,
   including SDR/HDR and returning to a lower resolution/refresh rate. Check
   stable picture, motion, audio and the refresh rate reported by the display.
3. **4:2:0:** add `hdmi.frl_yuv420=2` and repeat supported 4K60/120 modes.
   Confirm the selected format in the logs. Reduced colour detail around text
   is expected with 4:2:0; flickering, corruption and signal loss are not.
4. **ALLM:** on a compatible TV, add `hdmi.allm=2` and check its game/low-latency
   indication. Compare with `hdmi.allm=0`. Test policy `1` only when the software
   can set Game content type; launching a game alone may not do so. ALLM should
   stay inactive on a display without support.
5. **Recovery and reconnects:** add `hdmi.frl_recovery=1`. Check any naturally
   failing mode, unplug/replug HDMI, and swap displays if available. Record
   whether output and audio return and which mode was selected. Do not force
   failures with diagnostic hooks; they are not part of this build.
6. **Regressions:** check CEC if used, display sleep/wake and booting with the
   usual USB storage connection. Return to the previous kernel if something
   breaks, and note whether the same issue occurs there.

## Reporting results

Capture the kernel log after reproducing an issue:

```bash
sudo journalctl -k -b --no-pager > hdmi-test-kernel.log
```

If journald is unavailable, use `sudo dmesg > hdmi-test-kernel.log`. Review logs
before sharing them. Do not infer a pass solely from driver status; report what
you actually saw and heard.

The final source-review fixes have local compile/patch checks only; existing older kernel packages do
not contain those fixes. Use a package built from the supplied candidate source.

Screen-saving and display-specific audio/video compatibility remain test areas.

## Building from source

Clone this test branch and the matching kernel source:

```bash
git clone --branch hdmi-usbc-test https://github.com/Slip-Up/ps5-linux-patches
git clone https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git
```

Then apply the candidate patch and build:

```bash
cd linux
git checkout "tags/v$(grep -m1 "^# Linux/" ../ps5-linux-patches/.config | awk '{print $3}')"
git apply ../ps5-linux-patches/linux.patch
cp ../ps5-linux-patches/.config .config
make -j$(nproc)
```

Install the kernel and matching modules using your existing PS5 Linux test-boot
procedure, preserving the working boot files. On a PS5 Pro, also follow the
[Viola firmware instructions](firmware/README.md#viola-firmware-ps5-pro).
