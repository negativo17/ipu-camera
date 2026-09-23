%global debug_package %{nil}

Name:           ipu-camera
Version:        1
Release:        6%{?dist}
Summary:        Metapackages for the Intel IPU MIPI camera stack
License:        MIT
URL:            https://github.com/negativo17/ipu-camera
ExclusiveArch:  x86_64
BuildArch:      noarch

Source0:        README.md
Source1:        libcamera.md
Source2:        libcamhal-icamerasrc-v4l2.md
Source3:        libcamhal-libcamera.md

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
firmware and proprietary binaries) together with the IPU6 and IPU7 kernel
modules built through DKMS. The Intel CVS sensing controller is in the kernel
since 7.2 and is no longer built out of tree.

%package akmod
Summary:        Intel IPU MIPI camera stack (akmod kernel modules)
Requires:       ipu6-camera-hal
Requires:       ipu7-camera-hal
Requires:       akmod-ipu6
Requires:       akmod-ipu7

%description akmod
Metapackage that pulls in the complete Intel IPU MIPI camera stack using the
akmod kernel modules. It brings in the IPU6 and IPU7 userspace HAL (and their
firmware and proprietary binaries) together with the IPU6 and IPU7 kernel
modules built through akmods. The Intel CVS sensing controller is in the kernel
since 7.2 and is no longer built out of tree.

%prep
%setup -q -c -T
install -p -m 0644 %{SOURCE0} %{SOURCE1} %{SOURCE2} %{SOURCE3} .

%build

%install

%files dkms
%doc *.md

%files akmod
%doc *.md

%changelog
* Wed Sep 23 2026 Simone Caronni <negativo17@gmail.com> - 1-6
- Update documentation.

* Wed Sep 16 2026 Simone Caronni <negativo17@gmail.com> - 1-5
- Document that intel_cvs is in the kernel since 7.2.

* Sun Sep 06 2026 Simone Caronni <negativo17@gmail.com> - 1-4
- Update README.

* Thu Jul 23 2026 Simone Caronni <negativo17@gmail.com> - 1-3
- Update README.

* Fri Jul 10 2026 Simone Caronni <negativo17@gmail.com> - 1-2
- Add libcamera.md.

* Wed Jul 08 2026 Simone Caronni <negativo17@gmail.com> - 1-1
- First build.
