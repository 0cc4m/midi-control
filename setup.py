import setuptools

setuptools.setup(
    name="midi-control",
    version="0.0.1",
    packages=["midi_control"],
    package_dir={"midi_control": "src"},
    python_requires=">=3.6",
    install_requires=[
        "dbus-python",
        "mido",
        "pyyaml"
    ],
    entry_points={
        "console_scripts": [
            "midi-control=midi_control:main"
            ],
    }
)
