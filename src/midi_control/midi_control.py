#!/usr/bin/env python3
"""
Copyright (C) 2021  0cc4m, Ripsnapper

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import time
import argparse
import logging
import mido
import signal
import yaml
from .action_handlers import handler_classes, terminate_threads

log = logging.getLogger("midi-control")

handlers = {}

control_by_name = {}

consts = {
    "note_on_values": {
        False: 0,
        True: 127,
    },
    "control_change_values": {
        "cw": 1,
        "ccw": 64,
    },
}


def handle_actions(name, value, actions, midi_out, msg):
    if name not in handlers:
        handlers[name] = {}
    for action, options in actions.items():
        if (
            (action == "press" and value == consts["note_on_values"][True])
            or (action == "release" and value == consts["note_on_values"][False])
            or (action == "cw" and value == consts["control_change_values"]["cw"])
            or (action == "ccw" and value == consts["control_change_values"]["ccw"])
            or action == "set"
        ):
            handlers[name][action](msg)


def map_controls(devices):
    # Create dict to enable input lookup by name
    for device_name, controls in devices.items():
        if type(controls) != dict:
            continue
        for type_name, control_type in controls.items():
            if type(control_type) != dict:
                continue
            by_name = {}
            for b_id, b_name in control_type.items():
                by_name.update(
                    {b_name: {"id": b_id, "type": type_name, "device": device_name}}
                )
            control_by_name.update(by_name)


def handle_messages(inport, outport, device, actions):
    for msg in inport.iter_pending():
        if msg.type == "note_on":
            name = device.get("note_on", {}).get(msg.note, "unknown")
            value = msg.velocity
            log.info(f"{name}: {value}")
        elif msg.type == "control_change":
            name = device.get("control_change", {}).get(msg.control, "unknown")
            value = msg.value
            log.info(f"{name}: {value}")
        elif msg.type == "pitchwheel":
            name = device.get("pitchwheel", {}).get(msg.bin()[0], "unknown")
            channel = msg.channel
            value = msg.pitch
            log.info(f"{name} {channel}: {value}")
        else:
            continue

        handle_actions(
            name,
            value,
            actions.get(name, {}),
            outport,
            msg,
        )


def main():
    signal.signal(signal.SIGTERM, terminate_threads)
    signal.signal(signal.SIGINT, terminate_threads)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d", "--device-file", default="~/.config/midi-control/device.yml"
    )
    parser.add_argument(
        "-a", "--actions-file", default="~/.config/midi-control/actions.yml"
    )
    parser.add_argument("--log", "-l", default="WARNING", help="Set loglevel")
    args = parser.parse_args()

    formatter = logging.Formatter(fmt="[%(levelname)s]: %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(args.log.upper())

    with open(os.path.expanduser(args.device_file), "r") as f:
        devices = yaml.load(f.read(), Loader=yaml.SafeLoader)

    with open(os.path.expanduser(args.actions_file), "r") as f:
        actions = yaml.load(f.read(), Loader=yaml.SafeLoader)

    map_controls(devices)

    if "consts" in devices:
        device_consts = devices["consts"]
        if "button_off" in consts:
            consts["note_on_values"][False] = device_consts["button_off"]
        if "button_on" in consts:
            consts["note_on_values"][True] = device_consts["button_on"]
        if "cw" in consts:
            consts["control_change_values"]["cw"] = device_consts["cw"]
        if "ccw" in consts:
            consts["control_change_values"]["ccw"] = device_consts["ccw"]
        devices.pop("consts")

    device_ports = {}
    for device in devices:
        inport = mido.open_input(device)
        outport = mido.open_output(device)
        device_ports[device] = {"in": inport, "out": outport}

        # Empty device buffers
        time.sleep(0.1)
        for _ in inport.iter_pending():
            pass

    # Initialize handlers to set initial control value
    for dname, device in actions.items():
        for name, button in device.items():
            handlers[name] = {}
            for action, event in button.items():
                handlers[name][action] = handler_classes[event["type"]](
                    event, control_by_name, consts, device_ports[dname]["out"]
                )

    while True:
        for device, ports in device_ports.items():
            handle_messages(ports["in"], ports["out"], devices[device],
                            actions[device])
            time.sleep(0.01)
