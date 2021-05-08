pkgname=midi-control-git
pkgver=r23.7f8e11f
pkgrel=1
_gitname=midi-control
pkgdesc="Trigger actions on MIDI input"
arch=(any)
url="https://github.com/0cc4m/midi-control"
license=("GPL3")
makedepends=("git" "python-setuptools")
depends=("python" "dbus-python" "python-mido" "python-pyaml")
source=("${_gitname}::git+https://github.com/0cc4m/${_gitname}.git")
sha256sums=("SKIP")

pkgver() {
  cd "$srcdir/${_gitname}"
  printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

package() {
  cd "${srcdir}/${_gitname}"
  python setup.py install --root="${pkgdir}/"
}
