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
        "ccw": 65,
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


def map_controls(devices, ports):
    # Create dict to enable input lookup by name
    for device_name, controls in devices.items():
        if type(controls) != dict:
            continue
        for type_name, control_type in controls.items():
            if type(control_type) != dict:
                continue
            by_name = {}
            for b_id, b in control_type.items():
                b_name = b["name"]
                led_type = b["led_type"]
                by_name.update(
                    {b_name: {"id": b_id,
                              "type": type_name,
                              "device": device_name,
                              "device_out_port": ports[device_name]["out"],
                              "led_type": led_type}}
                )
            control_by_name.update(by_name)


def process_device_definition(devices):
    p_devices = {}
    # Iterate all devices
    for device_name, control_types in devices.items():
        p_devices[device_name] = {}
        # Iterate all types of controls
        for control_type, led_types in control_types.items():
            p_devices[device_name][control_type] = {}
            # Iterate all led types
            print(led_types)
            for led_type, controls in led_types.items():
                p_controls = {}
                # Led type of control not defined -> default led handler
                if type(controls) == str:
                    c_id = led_type
                    c_name = controls
                    p_controls[c_id] = {"name": c_name, "led_type": "default"}
                    p_devices[device_name][control_type].update(p_controls)
                    continue

                for c_id, c_name in controls.items():
                    p_controls[c_id] = {"name": c_name, "led_type": led_type}
                p_devices[device_name][control_type].update(p_controls)

    return p_devices


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

    processed_devices = process_device_definition(devices)
    map_controls(processed_devices, device_ports)

    # Initialize handlers to set initial control value
    for dname, device in actions.items():
        for name, button in device.items():
            handlers[name] = {}
            for action, event in button.items():
                handlers[name][action] = handler_classes[event["type"]](
                    event, control_by_name, consts
                )

    while True:
        for device, ports in device_ports.items():
            handle_messages(ports["in"], ports["out"], devices[device],
                            actions[device])
            time.sleep(0.01)
