# Intel IPU cameras with libcamera

Instead of the proprietary `libcamhal` stack documented in [libcamhal-icamerasrc-v4l2.md](libcamhal-icamerasrc-v4l2.md), the same IPU6/IPU7 MIPI sensor can be driven by upstream **libcamera** through its *software ISP* (SoftISP): the kernel ISYS captures raw Bayer frames and libcamera debayers and applies a minimal 3A in userspace. No proprietary HAL, firmware imaging libraries or `icamerasrc` are involved.

The libcamera package shipped with this stack carries a pipeline handler for `libcamhal`, and when `libcamhal` is installed the software ISP steps aside for the Intel IPU (see [libcamhal-libcamera.md](libcamhal-libcamera.md)). What follows applies when libcamera drives the camera through the software ISP instead: without `libcamhal`, on i686, or with upstream libcamera.

This works for libcamera-native apps (e.g. GNOME Snapshot, `qcam`, `cam`), but on this hardware it has a number of issues. This file documents the limitations we hit so that users can decide between the two paths — and, if they stay on libcamera, apply the workarounds below.

## Test platform

Same laptop as in [libcamhal-icamerasrc-v4l2.md](libcamhal-icamerasrc-v4l2.md): Raptor Lake i7-13800H, IPU6 `8086:a75d`, `ov02c10` sensor — but **hybrid graphics**: Intel iGPU (Mesa) + NVIDIA dGPU (proprietary driver), switchable via `switcherooctl`. The hybrid-GPU angle is what triggers most of the problems below.

## 1. Software-ISP EGL failure on the NVIDIA GPU

libcamera's SoftISP can debayer on the GPU via an EGL/GLES offscreen render (`debayer_egl`, rendering into an FBO). On this hybrid-GPU laptop that path **crashes the pipeline**:

```
glFramebufferTexture2D ... GL error 0x8CD6 (36054, GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT)
debayerGPU failed
pipeline_handler ... assertion -> abort
```

### Why NVIDIA is picked (and why it fails)

EGL vendor selection goes through **glvnd**, which loads the ICD JSON files in `/usr/share/glvnd/egl_vendor.d/` in lexical order and uses the first vendor as the default EGL display:

```
/usr/share/glvnd/egl_vendor.d/10_nvidia.json
/usr/share/glvnd/egl_vendor.d/50_mesa.json
```

So `libEGL` hands libcamera the **NVIDIA** vendor by default. NVIDIA's EGL does not complete the SoftISP offscreen FBO the way libcamera expects (the FBO comes back `INCOMPLETE_ATTACHMENT`), the GPU debayer fails, and the SoftISP pipeline handler asserts and aborts. The camera never delivers a frame.

### Workaround A — keep GPU debayer, force the Mesa/Intel EGL vendor

Point glvnd at the Mesa ICD only, so the offscreen FBO runs on the Intel iGPU (which handles it correctly):

```sh
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
```

GPU debayer still runs, just on the iGPU. Downside: `__EGL_VENDOR_LIBRARY_*` is a process-wide EGL override, so it affects *every* EGL user in that process/session, not only libcamera — awkward to scope to a single camera app, and undesirable if you actually want NVIDIA EGL for something else in the same environment.

### Workaround B — disable the GPU debayer (recommended)

Tell libcamera to debayer on the **CPU**, so no EGL/GPU is touched at all:

```sh
LIBCAMERA_SOFTISP_MODE=cpu
```

This is the cleaner fix: `LIBCAMERA_SOFTISP_MODE` is honoured only by libcamera, so it has no effect on other EGL/GPU applications (unlike the glvnd override). The cost is higher CPU usage for the debayer. We ship it as a user environment drop-in:

```sh
# ~/.config/environment.d/50-libcamera-softisp.conf
LIBCAMERA_SOFTISP_MODE=cpu
```

`environment.d` is read by the systemd user session, so GUI apps launched from the session inherit it. Apps started outside the session (some launchers, or Chrome started from a non-session context) may need it exported another way (e.g. `/etc/profile.d`).

## 2. Browsers

Browsers see libcamera cameras through PipeWire:

- **Firefox** uses PipeWire cameras out of the box, so the libcamera camera is listed with no configuration.
- **Chrome and Chromium** enumerate the V4L2 `/dev/video*` devices by default, and libcamera does not provide one. Enable `chrome://flags/#enable-webrtc-pipewire-camera` to switch to PipeWire cameras; the libcamera camera is then listed.

Applications that only speak V4L2 cannot use a libcamera camera. For those, the [`v4l2-relayd` bridge](libcamhal-icamerasrc-v4l2.md#use-as-a-standard-webcam-v4l2loopback) provides a real V4L2 device.

### `pw-v4l2` is not a replacement for the Chrome flag

`pw-v4l2` is an `LD_PRELOAD` shim that intercepts V4L2 syscalls and makes a PipeWire node appear as a `/dev/videoN` device to a V4L2-only app:

```sh
pw-v4l2 google-chrome
```

It does create a `/dev/videoN` node, but **Chrome rejects/ignores it**:

- the shim does not implement all the ioctls Chrome's V4L2 capture requires (notably `VIDIOC_CREATE_BUFS` comes back unsupported), and
- the emulated device's card metadata/capabilities don't match what Chrome expects from a real capture device,

so Chrome drops it from the usable camera list. Use the PipeWire camera flag instead.

## 3. Other limitations of the libcamera path

- **No vendor 3A / tuning.** The proprietary HAL applies Intel's imaging (AEC/AGC, AWB, lens shading, the per-sensor `.aiqb` tuning). libcamera's SoftISP is a minimal debayer + basic 3A, so image quality is noticeably lower.
- **CPU cost.** With Workaround B (CPU debayer) the debayer runs on the CPU for every frame; at higher resolutions/framerates this is significant.
- **App coverage.** libcamera-native and PipeWire applications (GNOME Snapshot, `qcam`, `cam`, Firefox, Chrome with PipeWire cameras enabled) work once the EGL issue above is handled; applications that only speak V4L2 do not.
