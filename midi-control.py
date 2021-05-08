import argparse
import logging
import mido
import os
import subprocess
import time
import yaml
from dbus import SessionBus
from dbus.exceptions import DBusException

log = logging.getLogger("midi-controller")

handlers = {}
states = {}

control_by_name = {}
note_on_values = {
    False: 0,
    True: 127,
}
control_change_values = {
    "cw": 1,
    "ccw": 64,
}


def action_handler(name):
    def handler(func):
        handlers[name] = func
        return func
    return handler


def handle_actions(name, value, actions, midi_out, msg):
    if name not in states:
        states[name] = {}
    for action, options in actions.items():
        action_type = options["type"]
        if ((action == "press" and value == note_on_values[True]) or
                (action == "release" and value == note_on_values[False]) or
                (action == "cw" and value == control_change_values["cw"]) or
                (action == "ccw" and value == control_change_values["ccw"]) or
                action == "set"):
            handlers[action_type](options, states[name], midi_out, msg)


def set_led(port, name, value):
    msg = mido.Message(
        "note_on", note=control_by_name[name]["id"],
        velocity=note_on_values[value],
    )
    port.send(msg)


@action_handler("command")
def command_action(options, state, midi_out, msg):
    subprocess.run(options["command"])
    for led, value in options.get("states", {}).items():
        set_led(midi_out, led, value)


@action_handler("toggle")
def toggle_action(options, state, midi_out, msg):
    if "toggle_state" not in state or not state["toggle_state"]:
        subprocess.run(options["command_on"])
        for led, value in options.get("states_on", {}).items():
            set_led(midi_out, led, value)
        state["toggle_state"] = True
    else:
        subprocess.run(options["command_off"])
        for led, value in options.get("states_off", {}).items():
            set_led(midi_out, led, value)
        state["toggle_state"] = False


@action_handler("fader_command")
def fader_command_action(options, state, midi_out, msg):
    minv = options["min"]
    maxv = options["max"]
    val = msg.bin()[2]

    final = int(round(minv + val / 127 * maxv, 0))

    command = options["command"].copy()

    for i in range(0, len(command)):
        command[i] = command[i].replace("$VALUE", str(final))

    subprocess.run(command)


@action_handler("dbus")
def dbus_action(options, state, midi_out, msg):
    method_name = options["method"]
    service = options["service"]
    path = options["path"]
    if "dbus" not in state:
        try:
            proxy = SessionBus().get_object(service, path)
            method = proxy.get_dbus_method(method_name)
            state["dbus"] = method
        except DBusException as e:
            log.error("Could not create dbus proxy in dbus action: %s"
                      % e.get_dbus_message())
            return

    args = options.get("args", [])

    state["dbus"](*args)

    for led, value in options.get("states", {}).items():
        set_led(midi_out, led, value)


@action_handler("dbus_toggle")
def dbus_toggle_action(options, state, midi_out, msg):
    method_name = options["method"]
    service = options["service"]
    path = options["path"]
    if "dbus_toggle" not in state:
        try:
            proxy = SessionBus().get_object(service, path)
            method = proxy.get_dbus_method(method_name)
            state["dbus_toggle"] = {"method": method,
                                    "state": False}
        except DBusException as e:
            log.error("Could not create dbus proxy in dbus_toggle action: %s"
                      % e.get_dbus_message())
            return

    if state["dbus_toggle"]["state"]:
        args = options.get("args_on", [])
        state["dbus_toggle"]["state"] = False
        for led, value in options.get("states_on", {}).items():
            set_led(midi_out, led, value)
    else:
        args = options.get("args_off", [])
        state["dbus_toggle"]["state"] = True
        for led, value in options.get("states_off", {}).items():
            set_led(midi_out, led, value)

    state["dbus_toggle"]["method"](*args)


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
                        {b_name: {
                            "id": b_id,
                            "type": type_name,
                            "device": device_name}}
                        )
            control_by_name.update(by_name)


def handle_messages(inport, outport, device, actions):
    for msg in inport.iter_pending():
        if msg.type == "note_on":
            name = device.get("note_on", {}).get(msg.note, "unknown")
            value = msg.velocity
            log.info(f"{name}: {value}")
        elif msg.type == "control_change":
            name = device.get("control_change", {}).get(msg.control,
                                                        "unknown")
            value = msg.value
            log.info(f"{name}: {value}")
        elif msg.type == "pitchwheel":
            name = device.get("pitchwheel", {})\
                .get(msg.bin()[0], "unknown")
            channel = msg.channel
            value = msg.pitch
            log.info(f"{name} {channel}: {value}")
        else:
            continue

        handle_actions(
            name, value, actions.get(name, {}), outport, msg,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--device-file",
                        default="~/.config/midi-control/device.yml")
    parser.add_argument("-a", "--actions-file",
                        default="~/.config/midi-control/actions.yml")
    parser.add_argument("--log", "-l",
                        default="WARNING",
                        help="Set loglevel")
    args = parser.parse_args()

    logging.basicConfig(format="[%(levelname)s]: %(message)s",
                        level=args.log.upper())

    with open(os.path.expanduser(args.device_file), "r") as f:
        devices = yaml.load(f.read(), Loader=yaml.SafeLoader)

    with open(os.path.expanduser(args.actions_file), "r") as f:
        actions = yaml.load(f.read(), Loader=yaml.SafeLoader)

    map_controls(devices)

    if "consts" in devices:
        consts = devices["consts"]
        if "button_off" in consts:
            note_on_values[False] = consts["button_off"]
        if "button_on" in consts:
            note_on_values[True] = consts["button_on"]
        if "cw" in consts:
            control_change_values["cw"] = consts["cw"]
        if "ccw" in consts:
            control_change_values["ccw"] = consts["ccw"]
        devices.pop("consts")

    device_ports = {}
    for device in devices:
        inport = mido.open_input(device)
        outport = mido.open_output(device)
        device_ports[device] = {"in": inport, "out": outport}

    while True:
        for device, ports in device_ports.items():
            handle_messages(ports["in"],
                            ports["out"],
                            devices[device],
                            actions[device])
            time.sleep(0.01)


if __name__ == "__main__":
    main()
