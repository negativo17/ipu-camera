# Intel IPU cameras with libcamhal, icamerasrc and v4l2-relayd

This documents running Intel IPU MIPI cameras on Fedora with the proprietary userspace stack (the `libcamhal` HAL, firmware and proprietary imaging libraries) together with the IPU6, IPU7 and IPU8 kernel modules and the `icamerasrc` GStreamer plugin, with `v4l2-relayd` publishing the camera as a regular V4L2 webcam through v4l2loopback. It covers IPU6 (Tiger Lake through Meteor Lake) and IPU7 / IPU8 (Lunar Lake and newer).

## Test platform

Using the Intel IPU6 MIPI camera (e.g. OV02C10 sensor) via the `icamerasrc` GStreamer plugin and the IPU6 camera HAL.

Tested on a Raptor Lake platform (Core i7-13800H, IPU6 PCI `8086:a75d`, `ipu6ep` config set) with the `ov02c10` sensor and the out-of-tree IPU6 kernel modules (`intel_ipu6`, `intel_ipu6_isys`, `intel_ipu6_psys`).

On this particular laptop, these are the components required to get a full working setup:

- Platform: Raptor Lake i7‑13800H, IPU6 PCI 8086:a75d, uses the `ipu6ep` config set
- Sensor: ov02c10 19-0036 bound to CSI2 port 3 (`[ENABLED,IMMUTABLE]`)
- HAL config: `/usr/share/camera/ipu6ep/` present, incl. `OV02C10_*.aiqb` + `ov02c10-uf.xml`
- Firmware: `ipu6ep_fw.bin` present
- Plugin: `libgsticamerasrc.so`, camera device-name `ov02c10-uf`
- ISYS nodes: `/dev/video*`, `/dev/media2` with `uaccess` ACL for your session
- PSYS node: `/dev/ipu-psys0` with `uaccess` ACL for your session

## Prerequisites

Install the IPU camera stack. The easiest way is one of the two metapackages, which pull in the whole userspace-plus-kernel stack in the matching kernel-module flavour:

- `ipu-camera-dkms` — kernel modules built through DKMS.
- `ipu-camera-akmod` — kernel modules built through akmods.

Either metapackage pulls in the full stack for both IPU6 and IPU7/IPU8. The components, and the dependencies they drag in automatically, are:

- `ipu7-camera-hal` — the shared `libcamhal` adaptor plus the IPU7/IPU8 HAL plugins and per-platform configs. It automatically pulls in `ipu7-camera-bins` (firmware and proprietary binaries), which in turn pulls in `intel-ipu8-firmware`.
- `ipu6-camera-hal` — the IPU6 HAL plugins and per-platform configs (`/usr/share/camera/`). Note that this package no longer ships a camera HAL of its own: the `libcamhal` adaptor comes from `ipu7-camera-hal`. It automatically pulls in `ipu6-camera-bins` (firmware and proprietary binaries).
- `dkms-ipu7` / `akmod-ipu7` — the out-of-tree IPU7 kernel module (`intel-ipu7-psys`). The Intel CVS (`intel_cvs`) sensing-controller module they rely on is in the kernel since 7.2 and is no longer shipped here (see below).
- `dkms-ipu6` / `akmod-ipu6` — the IPU6 kernel modules, including the sensor drivers.

The `icamerasrc` GStreamer element and the V4L2 bridge are separate — they are not pulled in by the metapackages:

- `gstreamer1-plugin-icamerasrc` — the `icamerasrc` GStreamer element.
- `v4l2-relayd` — feeds `icamerasrc` into a v4l2loopback device, so V4L2 applications such as browsers see a regular webcam (see [Use as a standard webcam](#use-as-a-standard-webcam-v4l2loopback)). It pulls in the v4l2loopback module; install `dkms-v4l2loopback` or `akmod-v4l2loopback` explicitly to pick the same flavour as the IPU modules.

Confirm the sensor is bound in the media graph (should show `[ENABLED,IMMUTABLE]`). For example:

```bash
$ media-ctl -d /dev/media2 -p | grep -i ov02c10
		<- "ov02c10 19-0036":0 [ENABLED,IMMUTABLE]
- entity 248: ov02c10 19-0036 (1 pad, 1 link, 0 routes)
```

### PSYS device permissions

The processing side exposes `/dev/ipu-psys0`, which by default is `crw------- root root` — only root can open it, so pipelines fail with `Failed to open PSYS, error: Permission denied`.

Add a uaccess ACL (matching the ISYS `/dev/video*` nodes) with a udev rule. Each HAL package ships its own rule matching its PSYS subsystem — `72-ipu6-psys.rules` from `ipu6-camera-hal` and `72-ipu7-psys.rules` from `ipu7-camera-hal`. There is no separate IPU8 rule: IPU8 (Nova Lake) is driven by the same `intel-ipu7-psys` module and registers under the `intel-ipu7-psys` subsystem, so the IPU7 rule covers it too.

```bash
$ cat /usr/lib/udev/rules.d/72-ipu6-psys.rules
SUBSYSTEM=="intel-ipu6-psys", TAG+="uaccess"

$ cat /usr/lib/udev/rules.d/72-ipu7-psys.rules
SUBSYSTEM=="intel-ipu7-psys", TAG+="uaccess"
```

Verify that the device files have the proper ACL:

```bash
$ getfacl /dev/ipu-psys0
getfacl: Removing leading '/' from absolute path names
# file: dev/ipu-psys0
# owner: root
# group: root
user::rw-
user:slaanesh:rw-
group::---
mask::rw-
other::---
```

## IPU6 vs IPU7 HAL

The camera HAL is split into a thin **`libcamhal`** adaptor plus per-platform **plugins** in `/usr/lib64/libcamhal/plugins/`. At runtime the adaptor reads the IPU's PCI ID from `/sys/bus/pci/drivers/intel-ipu{6,7}` and `dlopen`s the matching plugin. The `ipu6-camera-hal` and `ipu7-camera-hal` packages ship the plugins, while the shared `libcamhal` / `libcamhal-devel` packages (built from `ipu7-camera-hal`) provide the adaptor and headers.

The IPU7 HAL is a **superset** of the IPU6 HAL: its adaptor recognises every platform the IPU6 adaptor does, plus IPU8 (Nova Lake). The two dispatch tables otherwise map the same PCI IDs to the same plugins, and the adaptor↔plugin ABI (the `camera_*` C API) is shared, so a single adaptor can drive either plugin set.

| Platform | PCI ID | Plugin | IPU | IPU6 HAL | IPU7 HAL |
|---|---|---|---|:-:|:-:|
| Tiger Lake (TGL)    | `0x9a19` | `ipu6`      | IPU6 | ✅ | ✅ |
| Jasper Lake (JSL)   | `0x4e19` | `ipu6sepla` | IPU6 | ✅ | ✅ |
| Alder Lake-N (ADLN) | `0x462e` | `ipu6ep`    | IPU6 | ✅ | ✅ |
| Alder Lake-P (ADLP) | `0x465d` | `ipu6ep`    | IPU6 | ✅ | ✅ |
| Raptor Lake (RPL)   | `0xa75d` | `ipu6ep`    | IPU6 | ✅ | ✅ |
| Meteor Lake (MTL)   | `0x7d19` | `ipu6epmtl` | IPU6 | ✅ | ✅ |
| Lunar Lake (LNL)    | `0x645d` | `ipu7x`     | IPU7 | ✅ | ✅ |
| Panther Lake (PTL)  | `0xb05d` | `ipu75xa`   | IPU7 | ✅ | ✅ |
| Nova Lake (NVL)     | `0xd719` | `ipu8`      | IPU8 | ❌ | ✅ |

The IPU6 adaptor already knows how to load the `ipu7x` / `ipu75xa` plugins (Lunar Lake / Panther Lake), but the `ipu6-camera-hal` package does not ship them — those plugins come from `ipu7-camera-hal`. Only the IPU7 adaptor adds the IPU8 / Nova Lake (`0xd719`) case, which is why `libcamhal` is built from `ipu7-camera-hal`.

### Headers

The two repositories ship slightly different HAL headers under `/usr/include/libcamhal/`, `ipu7-camera-hal` adds:

- `ParamDataType.h`
- `subway_autogen.h`
- `tnr7us_parameters_definition.h`
- `PerfettoTrace.h`
- `ICamera.h` (different from the IPU6 one)

Since the shared `libcamhal-devel` package (built from `ipu7-camera-hal`) is the one that provides these headers, the IPU7 header set is what gets installed for both.

## The CVS / vision sensing controller (IPU7 / Lunar Lake and newer)

On Lunar Lake and newer there is an extra layer below the IPU: [intel/vision-drivers](https://github.com/intel/vision-drivers) is the Intel **CVS** (Camera Vision Sensing) controller driver — the successor to the older **IVSC** (Intel Visual Sensing Controller). It provides `intel_cvs.ko` and rides on the LJCA USB bridge (GPIO ACPI ID `INTC10B5`). It was packaged here as `vision-kmod` (akmod) and `dkms-vision` until it reached mainline in Linux 7.2; on a current kernel it comes from `kernel-modules` instead.

What the module does, briefly: it drives the always-on vision sensing controller that sits between the MIPI sensor and the host IPU — handing sensor ownership from the controller to the host so the IPU can stream, driving the hardware privacy path (the privacy LED), and backing the low-power human-presence features (walk-away lock, adaptive dimming) that run without the host.

### Where it sits in the camera pipeline

```
                 ┌────────────────┐
   MIPI sensor ──┤ VSC / IVSC /   ├──► IPU (ISYS/PSYS) ──► libcamhal ──► your stack
   (ov02c10 …)   │  CVS controller│
                 └───────┬────────┘
                         └──► low-power presence/context sensing (walk-away lock,
                              adaptive dimming, "Studio Effects"), runs w/o the host
```

The controller can own the sensor independently of the OS for human-presence detection, and it provides the hardware privacy path. Crucially, **the sensor is shared** — the host IPU can only stream after the VSC/CVS hands ownership over. If that handoff driver isn't present or working, the IPU camera simply won't stream: the sensor stays owned by the controller (privacy LED can stay stuck on, sensor invisible to the host).

This is the same role as the `CONFIG_INTEL_VSC` path in the `ov02c10` sensor driver (the `cvfd_ids` `INTC1059` / `INTC1095` / `INTC100A` / `INTC10CF` and the `privacy_status` control). On kernels < 6.6 the sensor driver did the VSC acquire/release itself; on ≥ 6.6 that moved out to a separate driver set (`mei-vsc`, `ivsc-csi` / `mei_csi`, `ljca`), most of which is now mainline.

### Generation lineage

| Platform | IPU | Sensing controller | Driver |
|---|---|---|---|
| Tiger Lake / Alder Lake / Raptor Lake / Meteor Lake | IPU6 | IVSC | `mei-vsc` / `ivsc-csi` (mostly mainline now) |
| Lunar Lake and newer | IPU7 / IPU8 | CVS | `intel_cvs.ko`, mainline since 7.2 |

So for the IPU7/IPU8 packages, camera enablement is not just IPU driver + sensor + HAL — on CVS-equipped machines you also need this CVS/vision driver + LJCA, or the camera never releases to the host. It is orthogonal to the libcamhal / PipeWire-plugin layer (that is all above libcamhal); it is a hard dependency lower in the stack. This is why `dkms-ipu7` and `ipu7-kmod` require a kernel new enough to carry `intel_cvs`, that is 7.2 or later.

### Mainline status

Don't conflate two separate things:

- The **IPU7 driver itself is mainline** as of Linux 6.17 (merged for Lunar Lake / Panther Lake webcams) — which is why `dkms-ipu7` / `ipu7-kmod` only build the out-of-tree `intel-ipu7-psys` module on ≥ 6.17 kernels.
- The **CVS sensing-controller driver (`intel_cvs`) is mainline since Linux 7.2**, as `drivers/media/i2c/cvs/intel_cvs.ko` in the `kernel-modules` package. Intel issue [#36](https://github.com/intel/vision-drivers/issues/36) had asked for exactly that, flagging it as "critical for IPU7 camera". Up to 7.1 it lived only in `intel/vision-drivers` and was shipped here as `dkms-vision` / `akmod-vision`; those packages are gone, and on a 7.2 kernel the in-tree module is used instead.

Note that the out-of-tree module was installed under `/updates`, which takes precedence over the in-tree one, so on a 7.2 kernel DKMS would report `installed (Original modules exist)` and the kernel's own `intel_cvs` would be shadowed. That is the other reason for dropping the packages rather than just leaving them installed.

So on CVS-equipped Lunar Lake / Panther Lake machines the whole chain is now in the kernel: IPU7 (6.17), `intel_cvs` (7.2) and LJCA/USBIO. Without the sensing controller the camera stays owned by it and never reaches the host (LED stuck on, sensor invisible), so a kernel older than 7.2 still needs an out-of-tree build.

One thing worth confirming per target machine: whether the IPU7/IPU8 laptop actually has CVS at all, since some wire the sensor straight to the IPU.

## The IVSC sensing controller (IPU6)

On the IPU6 generation the counterpart of CVS is the older **IVSC** (Intel Visual Sensing Controller). It is provided by [intel/ivsc-driver](https://github.com/intel/ivsc-driver): `mei-vsc` (the MEI transport to the controller), `ivsc-csi` (CSI-2 routing and the sensor-ownership handoff) and `ivsc-ace` (the Algorithm Context Engine that arbitrates ownership). The same repo also bundles the older **LJCA** USB-bridge drivers (`usb-ljca` and its `gpio` / `i2c` / `spi` cells).

Its role is exactly the CVS role one generation earlier: it mediates sensor ownership between the always-on sensing controller and the host IPU and provides the hardware privacy path — the IPU can only stream once IVSC hands the sensor over.

These are **mainline now**: the IVSC media drivers (`mei-vsc`, `ivsc-csi`, `ivsc-ace`) landed in Linux 6.8 and the LJCA bridge in 6.7, so on a current Fedora kernel there is no out-of-tree ivsc-driver / DKMS / akmod package in this stack — a recent kernel is enough. The IPU7-era successor, CVS / `intel_cvs`, followed in 7.2 (see above).

The IVSC/CVS split is no longer strictly generational, though. As of the `20260819` snapshots the IPU6 stack has started to speak CVS as well: `ipu6-camera-hal` now looks for a media entity named `Intel CVS` and only falls back to the legacy `Intel IVSC CSI` name, and the Meteor Lake (`ipu6epmtl`) `ov08x40-uf` configuration routes the sensor through it (`ov08x40` → `Intel CVS` → `Intel IPU6 CSI-2` instead of straight to the CSI-2 receiver). On the driver side the out-of-tree `ov05c10` stream-on and soft-standby register sequences were reworked to match the CVS firmware control flow. So an IPU6-generation machine can present a CVS-named sensing controller too, and the HAL now handles both entity names.

## The USB bridge: LJCA and USBIO

On some IPU laptops the camera sensor's control interface (I2C) and its GPIO lines (power, reset, privacy) are not on the SoC's own I2C/GPIO controllers but sit behind a small USB-attached bridge, so the host (and the sensing controller) reaches the sensor over USB. There are two generations of that bridge, each with its own driver set:

- **LJCA** (La Jolla Cove Adapter) — the older bridge. Its drivers (`usb-ljca` plus the `gpio-ljca` / `i2c-ljca` / `spi-ljca` cells) are bundled in [intel/ivsc-driver](https://github.com/intel/ivsc-driver) and have been mainline since Linux 6.7.
- **USBIO** — the newer USB IO-expander used on Meteor Lake and newer (Arrow Lake, Lunar Lake, Panther Lake). [intel/usbio-drivers](https://github.com/intel/usbio-drivers) provides `usbio` (bridge) plus `gpio-usbio` / `i2c-usbio`; these are mainline as of Linux 6.18.

Because both are upstream, there is no `ljca` / `usbio` DKMS / akmod package in this stack — a recent kernel is enough: the bridge binds automatically and its GPIO/I2C controllers appear for the sensor and `ipu-bridge` to use. It only matters on machines whose sensor or sensing controller is wired through the USB bridge; where the sensor sits directly on a native SoC I2C/GPIO controller, the bridge drivers are not involved at all.

## Kernel modules and mainline status

Where every module involved lives, and — if it has been merged upstream — since which mainline kernel version. The rows marked *out-of-tree* are the only ones this stack still ships as DKMS / akmod; everything else comes from a recent kernel.

| Project | Kernel module | In mainline since | Pacakge |
|---|---|---|---|
| [intel/vision-drivers](https://github.com/intel/vision-drivers) | `intel_cvs` | 7.2 | in `kernel-modules` |
| [intel/usbio-drivers](https://github.com/intel/usbio-drivers) | `usbio` | 6.18 | Not needed |
| | `gpio-usbio` | 6.18 |
| | `i2c-usbio` | 6.18 |
| [intel/ipu6-drivers](https://github.com/intel/ipu6-drivers) | `intel-ipu6` | 6.10 | `dkms-ipu6`/`akmod-ipu6` |
| | `intel-ipu6-isys` | 6.10 |
| | `intel-ipu6-psys` | *out-of-tree* |
| | `ipu-bridge` (shared helper) | 6.6 |
| | `ov01a10` | 6.8 |
| | `ov2740` | 6.8 |
| | `hi556` | 6.10 |
| | `ov02c10` | 6.16 |
| | `ov02e10` | 6.16 |
| | `imx471` | 7.1 |
| | `hm11b1` | *out-of-tree* |
| | `ov01a1s` | *out-of-tree* |
| | `hm2170` | *out-of-tree* |
| | `hm2172` | *out-of-tree* |
| | `gc5035` | *out-of-tree* |
| | `ov05c10` | *out-of-tree* |
| | `s5k3j1` | *out-of-tree* |
| [intel/ipu7-drivers](https://github.com/intel/ipu7-drivers) | `intel-ipu7` | 6.17 | `dkms-ipu7`/`akmod-ipu7` |
| | `intel-ipu7-isys` | 6.17 |
| | `intel-ipu7-psys` | *out-of-tree* |
| [intel/ivsc-driver](https://github.com/intel/ivsc-driver) | `mei-vsc` | 6.8 | Not needed |
| | `ivsc-csi` (old `mei_csi`) | 6.8 |
| | `ivsc-ace` (old `mei_ace`) | 6.8 |
| | `usb-ljca` (old `ljca`) | 6.7 |
| | `gpio-ljca` | 6.7 |
| | `i2c-ljca` | 6.7 |
| | `spi-ljca` | 6.7 |

So on a current Fedora kernel most of the stack is upstream — IPU6/IPU7 ISYS, `ipu-bridge`, IVSC, LJCA, USBIO and the mainlined sensors. What this stack still builds out-of-tree is: the two `*-psys` modules (`dkms-ipu6` / `dkms-ipu7` or their akmods) and the camera sensors that are not upstreamed — `hm11b1`, `ov01a1s`, `hm2170`, `hm2172`, `gc5035`, `ov05c10`, `s5k3j1` (`ov05c10` builds only on kernels ≥ 6.8, `s5k3j1` only on ≥ 6.10). `imx471` is a special case: it reached mainline in 7.1, so `dkms-ipu6` / `akmod-ipu6` build the out-of-tree copy only in the 6.10–7.0 window and drop it from kernel 7.1 on. The sensor versions above are taken from the `ipu6-drivers` `dkms.conf` gating (there are no sensors in `ipu7-drivers`).

The `ivsc-driver` repo also carries a few legacy/debug modules (`intel_vsc`, `mei_pse`, `mei_ace_debug`) that were never upstreamed and are not used here.

## Caps note

This `icamerasrc` build emits **only** DMABuf with a DRM format: `video/x-raw(memory:DMABuf), format=DMA_DRM, drm-format=NV12` (linear).

- Caps filters must use `format=DMA_DRM`; a plain `format=NV12` will not negotiate.
- The buffers are **linear** NV12. `vapostproc` only imports **tiled** NV12 DMABuf, so it will not link directly — route conversions through `glupload` / `gldownload` (GL) instead of VA, as shown below.

## Commands

Some sample commands using only the proprietary stack components.

### Headless sanity check (no display)

```bash
gst-launch-1.0 icamerasrc num-buffers=30 printfps=true ! \
  "video/x-raw(memory:DMABuf),format=DMA_DRM,width=1280,height=720" ! fakesink
```

### Live preview (Wayland/GL, keeps it as DMABuf)

```bash
gst-launch-1.0 icamerasrc ! \
  "video/x-raw(memory:DMABuf),format=DMA_DRM,width=1920,height=1080" ! \
  glimagesink
```

The window opens small; drag to resize or maximize it.

### DMABuf → system-memory NV12

```bash
gst-launch-1.0 icamerasrc ! \
  "video/x-raw(memory:DMABuf),format=DMA_DRM,width=1920,height=1080" ! \
  glupload ! glcolorconvert ! gldownload ! "video/x-raw,format=NV12" ! \
  videoconvert ! autovideosink
```

### Record to H.264 MP4 (encode on the GPU via `vah264enc`, which takes system NV12)

```bash
gst-launch-1.0 -e icamerasrc ! \
  "video/x-raw(memory:DMABuf),format=DMA_DRM,width=1920,height=1080" ! \
  glupload ! glcolorconvert ! gldownload ! "video/x-raw,format=NV12" ! \
  vah264enc ! h264parse ! mp4mux ! filesink location=cam.mp4
```

### Selecting a sensor

There is usually a single camera (the default). To pick one explicitly:

```bash
gst-launch-1.0 icamerasrc device-name=ov02c10-uf ! ...
```

## Use as a standard webcam (v4l2loopback)

`icamerasrc` is a native GStreamer source and does **not** create a `/dev/videoN` node, so apps expecting a plain webcam (browsers, conferencing apps, `v4l2src`) cannot use it directly. Bridge it through `v4l2loopback`: a GStreamer pipeline pumps the camera into a loopback device that appears as an ordinary V4L2 webcam.

This is what Chrome expects without turning on Pipewire support.

A bridge that held the sensor open all the time would keep the camera (and its privacy LED) on, so it has to switch the sensor on only while an application is actually reading from the loopback device.

### Automatic bridge (v4l2-relayd)

`v4l2-relayd` does exactly that, and is the recommended way to get a webcam out of this stack. Once installed it needs no configuration:

- `v4l2loopback` is loaded at boot with `exclusive_caps=1` and the card label `Virtual Camera`.
- `v4l2-relayd.service` is enabled by a preset. A systemd generator starts one `v4l2-relayd@<name>.service` instance per file in `/etc/v4l2-relayd.d/`, and the package ships `icamera.conf`, so the running instance is `v4l2-relayd@icamera.service`.
- While no application has the loopback device open, the relay feeds it a static black frame from `videotestsrc` and the sensor stays off. When an application opens the device it switches to `icamerasrc` and the sensor turns on; when the application closes it, the relay goes back to the static frame and the sensor turns off again.
- The loopback device is looked up by its card label, not by a fixed `/dev/videoN` number.

Settings are read from `/etc/default/v4l2-relayd` and then from `/etc/v4l2-relayd.d/icamera.conf`, which overrides them. The pipeline description, output format, resolution and frame rate are all in `icamera.conf`; restart the instance after changing it.

**The camera resolution has to be declared in `icamera.conf`.** Nothing is negotiated between the camera and the applications reading the loopback device: the relay opens it with fixed caps built from `FORMAT`, `WIDTH`, `HEIGHT` and `FRAMERATE`, and every frame coming out of `VIDEOSRC` and `SPLASHSRC` has to match them. Set the same size and frame rate in the `icamerasrc` caps and the final `capsfilter` of `VIDEOSRC`, in the `capsfilter` of `SPLASHSRC`, and in `WIDTH`, `HEIGHT` and `FRAMERATE`. `videoconvert` only converts the pixel format, so to request one size from the camera and publish another, add `videoscale` to `VIDEOSRC`. For example, for 1280x720:

```bash
VIDEOSRC="icamerasrc ! video/x-raw,format=NV12,width=1280,height=720,framerate=30/1 ! videoconvert ! capsfilter caps=video/x-raw,format=YUY2,width=1280,height=720,framerate=30/1"
SPLASHSRC="videotestsrc is-live=true pattern=black ! videoconvert ! capsfilter caps=video/x-raw,format=YUY2,width=1280,height=720,framerate=30/1"
FORMAT=YUY2
WIDTH=1280
HEIGHT=720
FRAMERATE=30/1
```

```bash
sudo systemctl restart v4l2-relayd@icamera.service
```

Check that the bridge is running and find the device:

```bash
systemctl status v4l2-relayd@icamera.service
v4l2-ctl --list-devices
```

Point any application at **"Virtual Camera"**.

### Manual bridge

Useful for testing a pipeline by hand. Stop the relay first, since it holds the loopback device and would compete for the camera; if `v4l2-relayd` is installed, `v4l2loopback` is also already loaded with its own options, so remove it before loading it with the ones below:

```bash
sudo systemctl stop v4l2-relayd.service
sudo modprobe -r v4l2loopback
```

Create a loopback device and feed it:

```bash
sudo modprobe v4l2loopback devices=1 video_nr=42 card_label="IPU6 Camera" exclusive_caps=1

gst-launch-1.0 -e icamerasrc ! \
  "video/x-raw(memory:DMABuf),format=DMA_DRM,width=1280,height=720" ! \
  glupload ! glcolorconvert ! gldownload ! "video/x-raw,format=NV12" ! \
  videoconvert ! "video/x-raw,format=YUY2" ! \
  v4l2sink device=/dev/video42
```

`exclusive_caps=1` is required for most apps (Chrome, Firefox, Zoom) to list the node as a capture device. `YUY2` is the format most apps expect. Point any app at **"IPU6 Camera"** (`/dev/video42`); verify with:

```bash
gst-launch-1.0 v4l2src device=/dev/video42 ! videoconvert ! autovideosink
```


## Notes

- `icamerasrc` is a native GStreamer source and does **not** create a `/dev/videoN` V4L2 node. Apps expecting a plain webcam (browsers, conferencing apps, `v4l2src`) will not see it directly; `v4l2-relayd` bridges it through `v4l2loopback`.
- The warning `CamHAL[WAR] Failed to open file /run/camera/ov02c10-uf_VIDEO.aiqd` is harmless. `.aiqd` is the AIQ auto-tuning cache the HAL loads at startup and writes at stream stop; on the first run after boot it does not exist yet. Capture proceeds using the shipped `.aiqb` tuning.
