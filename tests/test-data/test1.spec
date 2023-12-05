# Just a run-of-the-mill spec file using some macros and corner cases
%bcond_without subpackage
%bcond_with dependency

Name: test
Version: 1
Release: 1
Summary: Test spec file
Group: Old RPM versions require group, so we test it

License: CC-0
URL: https://github.com/some/example/repo
Source0: %{url}/archive/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Patch: %{url}/commit/0123456789abcdef0123456789abcdef01234567.patch
Patch3: boop.patch
Patch: %{url}/commit/abcdef0123456789abcdef0123456789abcdef01.patch
%if %{with dependency}
BuildRequires: some-dependency
%endif
BuildArch: noarch

%if %{with subpackage}
%package subpackage
%endif

%description
%{summary}.

%if %{with subpackage}
%description subpackage
%{summary} subpackage.
%endif

%prep
%autosetup

%build
%make_build

%install
%make_install

%files
%license LICENSE
%doc AUTHORS README.md

%changelog
