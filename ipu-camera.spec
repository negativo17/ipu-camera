%global debug_package %{nil}

Name:           ipu-camera
Version:        1
Release:        2%{?dist}
Summary:        Metapackages for the Intel IPU MIPI camera stack
License:        MIT
URL:            https://github.com/negativo17/ipu-camera
ExclusiveArch:  x86_64
BuildArch:      noarch

Source0:        README.md

%description
This package provides metapackages that pull in the complete Intel IPU MIPI
camera stack (userspace HAL, firmware and kernel modules) for the IPU6, IPU7
and IPU8 platforms, in either a DKMS or an akmod flavour.

%package dkms
Summary:        Intel IPU MIPI camera stack (DKMS kernel modules)
Requires:       ipu6-camera-hal
Requires:       ipu7-camera-hal
Requires:       dkms-ipu6
Requires:       dkms-ipu7

%description dkms
Metapackage that pulls in the complete Intel IPU MIPI camera stack using the
DKMS kernel modules. It brings in the IPU6 and IPU7 userspace HAL (and their
firmware and proprietary binaries) together with the IPU6, IPU7 and CVS (vision)
kernel modules built through DKMS.

%package akmod
Summary:        Intel IPU MIPI camera stack (akmod kernel modules)
Requires:       ipu6-camera-hal
Requires:       ipu7-camera-hal
Requires:       akmod-ipu6
Requires:       akmod-ipu7

%description akmod
Metapackage that pulls in the complete Intel IPU MIPI camera stack using the
akmod kernel modules. It brings in the IPU6 and IPU7 userspace HAL (and their
firmware and proprietary binaries) together with the IPU6, IPU7 and CVS (vision)
kernel modules built through akmods.

%prep
%setup -q -c -T
install -p -m 0644 %{SOURCE0} README.md

%build

%install

%files dkms
%doc README.md libcamera.md

%files akmod
%doc README.md libcamera.md

%changelog
* Fri Jul 10 2026 Simone Caronni <negativo17@gmail.com> - 1-2
- Add libcamera.md.

* Wed Jul 08 2026 Simone Caronni <negativo17@gmail.com> - 1-1
- First build.
