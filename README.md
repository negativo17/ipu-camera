# IPU6 Camera with icamerasrc (GStreamer)

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

Install the IPU6 stack:

- `ipu6-camera-bins` — firmware plus proprietary binaries.
- `ipu6-camera-hal` — camera HAL and per-platform configs (`/usr/share/camera/`).
- `gstreamer1-plugin-icamerasrc` — the `icamerasrc` GStreamer element.
- `dkms-ipu6` or `akmod-ipu6` — kernel modules including the sensor drivers.

Confirm the sensor is bound in the media graph (should show `[ENABLED,IMMUTABLE]`). For example:

```bash
$ media-ctl -d /dev/media2 -p | grep -i ov02c10
		<- "ov02c10 19-0036":0 [ENABLED,IMMUTABLE]
- entity 248: ov02c10 19-0036 (1 pad, 1 link, 0 routes)
```

### PSYS device permissions

The processing side exposes `/dev/ipu-psys0`, which by default is `crw------- root root` — only root can open it, so pipelines fail with `Failed to open PSYS, error: Permission denied`. Grant the `video` group and a uaccess ACL (matching the ISYS `/dev/video*` nodes) with a udev rule:

```bash
$ cat /usr/lib/udev/rules.d/72-ipu6-psys.rules
SUBSYSTEM=="intel-ipu6-psys", TAG+="uaccess"
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

The two repositories ship slightly different HAL headers under `/usr/include/libcamhal/`: `ipu7-camera-hal` adds `ParamDataType.h`, `subway_autogen.h`, `tnr7us_parameters_definition.h` and `PerfettoTrace.h`, and its `ICamera.h` differs from the IPU6 one. Since the shared `libcamhal-devel` package (built from `ipu7-camera-hal`) is the one that provides these headers, the IPU7 header set is what gets installed for both.

## Caps note

This `icamerasrc` build emits **only** DMABuf with a DRM format: `video/x-raw(memory:DMABuf), format=DMA_DRM, drm-format=NV12` (linear).

- Caps filters must use `format=DMA_DRM`; a plain `format=NV12` will not negotiate.
- The buffers are **linear** NV12. `vapostproc` only imports **tiled** NV12 DMABuf, so it will not link directly — route conversions through `glupload` / `gldownload` (GL) instead of VA, as shown below.

## Commands

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

Because the bridge holds the sensor open while it runs, it must be started **on-demand** when you need the webcam,

### Manual bridge

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

- `icamerasrc` is a native GStreamer source and does **not** create a `/dev/videoN` V4L2 node. Apps expecting a plain webcam (browsers, conferencing apps, `v4l2src`) will not see it directly; bridge it through `v4l2loopback` if needed.
- The warning `CamHAL[WAR] Failed to open file /run/camera/ov02c10-uf_VIDEO.aiqd` is harmless. `.aiqd` is the AIQ auto-tuning cache the HAL loads at startup and writes at stream stop; on the first run after boot it does not exist yet. Capture proceeds using the shipped `.aiqb` tuning.
