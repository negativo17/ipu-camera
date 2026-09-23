# Intel IPU cameras with libcamhal and libcamera

The libcamera package shipped with this stack drives Intel IPU6, IPU7 and IPU8 MIPI cameras through the proprietary `libcamhal` HAL, the same HAL `icamerasrc` uses. libcamera applications, and everything that reaches the camera through libcamera (PipeWire, GNOME Snapshot, `cam`, `qcam`, the `libcamerasrc` GStreamer element), get the full Intel imaging pipeline — 3A, lens shading and the per-sensor tuning — instead of libcamera's software ISP.

This is the default path once the stack is installed. The [icamerasrc / v4l2-relayd path](libcamhal-icamerasrc-v4l2.md) keeps working alongside it, and the [software ISP path](libcamera.md) is what libcamera falls back to when `libcamhal` is not installed.

## Components

From the bottom up:

- **Kernel modules.** The ISYS driver (capture) is in the kernel for both IPU6 and IPU7, as are `ipu-bridge`, the IVSC and CVS sensing controllers, the LJCA/USBIO bridges and most sensors. What is still built out of tree is the PSYS driver (`intel-ipu6-psys` / `intel-ipu7-psys`, needed by `libcamhal`) and a few sensors, through `dkms-ipu6` / `dkms-ipu7` or `akmod-ipu6` / `akmod-ipu7`. The HAL packages load the PSYS module at boot through `modules-load.d`, since nothing else loads it on demand. See [Kernel modules and mainline status](libcamhal-icamerasrc-v4l2.md#kernel-modules-and-mainline-status) for the full table.
- **Firmware and proprietary libraries.** `ipu6-camera-bins`, `ipu7-camera-bins` and `intel-ipu8-firmware` provide the imaging libraries (3A, tuning, graph configuration) and the IPU8 firmware; the IPU6 and IPU7 firmware comes from `intel-vsc-firmware`.
- **libcamhal.** The `libcamhal` package (built from `ipu7-camera-hal`) provides the adaptor, `libcamhal.so.0`. At runtime it detects which IPU is present and loads the matching platform plugin from `%{_libdir}/libcamhal/`: the IPU6 plugins come from `ipu6-camera-hal`, the IPU7 and IPU8 ones from `ipu7-camera-hal`. The per-platform sensor and tuning configuration lives in `/usr/share/camera/`.
- **libcamera.** The Fedora libcamera package for the release, rebuilt with one extra patch that adds a `libcamhal` pipeline handler. It carries `Epoch: 1` so it replaces the Fedora build, and on x86_64 it requires `libcamhal`.

## The libcamhal pipeline handler

The handler lives in `src/libcamera/pipeline/libcamhal/` and is added by `0003-add-libcamhal-pipeline-handler.patch` in the libcamera package. It is built on x86_64 only, as that is the only architecture `libcamhal` exists for.

- **The HAL is loaded with `dlopen()` and `RTLD_LOCAL`, not linked.** Linking it into libcamera's global symbol namespace lets the platform plugin's logging globals be interposed, and the first HAL log message then crashes. `icamerasrc` loads the HAL locally too, which is why it never hits this.
- **Enumeration.** The handler asks the HAL for its cameras. The HAL reports every sensor slot of the platform configuration whether or not a sensor is fitted, so only camera 0 (the primary bound sensor) is registered by default. `LIBCAMERA_CAMHAL_CAMERAS=all`, or a camera id, overrides that.
- **Location.** Front or back is taken from the facing the HAL reports for the sensor, so applications label the camera correctly.
- **Stream.** A single NV12 output stream, with six buffers allocated by libcamera as DMABufs. The sensor timestamp is passed back in the request metadata.
- **Buffer recycling.** Buffers are re-queued to the HAL with their sequence number and timestamp reset, as `icamerasrc` does. Without this the HAL's bookkeeping gets corrupted and ISYS stalls after all buffers have gone round once.

Messages from the handler itself are printed on stderr with a `camhal:` prefix; the HAL's own logging is separate.

## Coexistence with the software ISP

libcamera's `simple` pipeline handler also claims the Intel IPU media devices, through the software ISP, so both handlers are built and the patch keeps them from both exposing the same camera. At startup `simple` checks whether `libcamhal` can be loaded; if it can, it leaves the `intel-ipu6` and `intel-ipu7` media devices to the `libcamhal` handler. If `libcamhal` is not installed, nothing changes and the camera is handled by the software ISP as described in [libcamera.md](libcamera.md).

The i686 build has no `libcamhal` handler, so there only the software ISP is available.

The HAL packages also ship a WirePlumber rule that disables the raw ISYS `/dev/video*` nodes as V4L2 cameras. They are not usable directly (they carry unprocessed sensor data and are driven by the HAL), and without the rule PipeWire lists a few dozen broken "cameras" next to the real one.

## Permissions

`libcamhal` opens `/dev/ipu-psys0` as well as the ISYS nodes, so the session user needs access to both. This is the same requirement as for `icamerasrc`, see [PSYS device permissions](libcamhal-icamerasrc-v4l2.md#psys-device-permissions).

## Usage

List the cameras and check which pipeline handler picked up the IPU:

```sh
cam -l
LIBCAMERA_LOG_LEVELS=Camera:INFO cam -l
```

Capture a few frames, or open a preview:

```sh
cam -c 1 --capture=10
qcam
```

Through GStreamer:

```sh
gst-launch-1.0 libcamerasrc ! videoconvert ! autovideosink
```

Applications using PipeWire cameras, such as GNOME Snapshot and Firefox, pick up the camera through PipeWire's libcamera plugin with no configuration. Chrome and Chromium enumerate V4L2 devices by default; enable `chrome://flags/#enable-webrtc-pipewire-camera` to use PipeWire cameras instead. Applications that only speak V4L2 need the [`v4l2-relayd` bridge](libcamhal-icamerasrc-v4l2.md#use-as-a-standard-webcam-v4l2loopback).

## Troubleshooting

- **No camera, or only a software ISP one.** Check that `libcamhal` is installed, since without it `simple` takes the device, and that the PSYS module is loaded (`lsmod | grep psys`).
- **The camera shows up but never delivers frames.** Check the permissions on `/dev/ipu-psys0` and the ISYS nodes, and look for `camhal:` errors on stderr.
- **More than one camera listed for a single sensor.** This happens with `LIBCAMERA_CAMHAL_CAMERAS=all` on platform configurations that describe more sensor slots than are fitted; leave the variable unset.
