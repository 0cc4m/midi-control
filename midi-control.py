import argparse
import mido
import yaml
import subprocess

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


def handle_actions(name, event, actions, midi_out):
    for action, options in actions.items():
        action_type = options["type"]
        # event is press, release, cw, ccw
        if action == event:
            if name not in states:
                states[name] = {}
            handlers[action_type](options, states[name], midi_out)


def set_led(port, name, value):
    msg = mido.Message(
        "note_on", note=control_by_name[name]["id"],
        velocity=note_on_values[value],
    )
    port.send(msg)


@action_handler("command")
def command_action(options, state, midi_out):
    subprocess.run(options["command"])
    for led, value in options.get("states", {}).items():
        set_led(midi_out, led, value)


@action_handler("toggle")
def toggle_action(options, state, midi_out):
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


def process_actions(actions, device):
    # Create dict to enable input lookup by name
    for type_name, control_type in device.items():
        if type(control_type) != dict:
            continue
        by_name = {}
        for b_id, b_name in control_type.items():
            by_name.update({b_name: {"id": b_id, "type": type_name}})
        control_by_name.update(by_name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("device_file")
    parser.add_argument("actions_file")
    args = parser.parse_args()

    with open(args.device_file, "r") as f:
        device = yaml.load(f.read(), Loader=yaml.SafeLoader)

    midi_device = device["midi_device"]

    with open(args.actions_file, "r") as f:
        all_actions = yaml.load(f.read(), Loader=yaml.SafeLoader)
        actions = all_actions.get(midi_device, {})

    process_actions(actions, device)

    if "button_off" in device:
        note_on_values[False] = device["button_off"]
    if "button_on" in device:
        note_on_values[True] = device["button_on"]
    if "cw" in device:
        control_change_values["cw"] = device["cw"]
    if "ccw" in device:
        control_change_values["ccw"] = device["ccw"]

    port = mido.open_input(midi_device)

    with mido.open_output(midi_device) as outport:
        for msg in port:
            if msg.type == "note_on":
                name = device.get("note_on", {}).get(msg.note, "unknown")
                value = "press" if msg.velocity == note_on_values[True]\
                        else "release"
                handle_actions(name, value, actions.get(name, {}), outport)
                print(f"{name}: {value}")
            elif msg.type == "control_change":
                name = device.get("control_change", {}).get(msg.control,
                                                            "unknown")
                value = "cw" if msg.value == control_change_values["cw"]\
                        else "ccw"
                handle_actions(name, value, actions.get(name, {}), outport)
                print(f"{name}: {value}")
            elif msg.type == "pitchwheel":
                name = "Pitch"
                channel = msg.channel
                value = msg.pitch
                print(f"{name} {channel}: {value}")


if __name__ == "__main__":
    main()
