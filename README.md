# Intel IPU cameras

Documentation for Intel IPU6, IPU7 and IPU8 MIPI cameras on Fedora, covering Tiger Lake through Meteor Lake (IPU6) and Lunar Lake and newer (IPU7 / IPU8).

The whole stack is installed with one of the two metapackages, which differ only in how the kernel modules are built:

- `ipu-camera-dkms` — kernel modules built through DKMS.
- `ipu-camera-akmod` — kernel modules built through akmods.

## Documents

- [libcamhal-icamerasrc-v4l2.md](libcamhal-icamerasrc-v4l2.md) — the `libcamhal` HAL used directly through the `icamerasrc` GStreamer element, and published as a regular V4L2 webcam through `v4l2-relayd` and v4l2loopback. Also the reference for prerequisites, device permissions, the CVS/IVSC sensing controllers, the USB bridges and the mainline status of every kernel module.
- [libcamera.md](libcamera.md) — libcamera's software ISP, used when `libcamhal` is not installed, and the problems it has on hybrid-GPU laptops.
- [libcamhal-libcamera.md](libcamhal-libcamera.md) — libcamera driving the camera through the proprietary `libcamhal` HAL, with full Intel imaging for libcamera and PipeWire applications. Describes the components, the libcamera pipeline handler and how it coexists with the software ISP.

## Comparison

| Concern                   | libcamhal + icamerasrc + v4l2-loopback + v4l2-relayd | libcamera (software ISP)                          | libcamera + libcamhal               |
|---------------------------|------------------------------------------------------|---------------------------------------------------|-------------------------------------|
| Hybrid-GPU EGL crash      | not affected (no software ISP)                       | `LIBCAMERA_SOFTISP_MODE=cpu` or Mesa EGL override | not affected (no software ISP)      |
| Image quality (3A/tuning) | full Intel imaging                                   | minimal                                           | full Intel imaging                  |
| libcamera-native apps     | not used, GStreamer and V4L2 only                    | works                                             | works                               |
| Resolution                | requires manual configuration                        | native                                            | native                              |
| Firefox                   | works (V4L2 only)                                    | works (PipeWire)                                  | works (PipeWire)                    |
| Chrome / Chromium         | works (V4L2 only)                                    | works with the PipeWire camera flag               | works with the PipeWire camera flag |
| V4L2-only applications    | works (V4L2 only)                                    | not usable                                        | not usable                          |
