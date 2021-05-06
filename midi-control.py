import argparse
import mido
import yaml
import subprocess

handlers = {}


def action_handler(name):
    def handler(func):
        handlers[name] = func
        return func
    return handler


def handle_actions(midi_port, event, actions):
    for action, options in actions.items():
        action_type = options["type"]
        # event is press, release, cw, ccw
        if action == event:
            handlers[action_type](options)

        for msg in options.get("state_messages", []):
            print("Sending message: ", msg)
            midi_port.send(msg)


@action_handler("command")
def command_action(options):
    subprocess.run(options["command"])


def process_actions(actions, device):
    # Create dict to enable input lookup by name
    control_by_name = {}
    for type_name, control_type in device.items():
        if type(control_type) != dict:
            continue
        by_name = {}
        for b_id, b_name in control_type.items():
            by_name.update({b_name: {"id": b_id, "type": type_name}})
        control_by_name.update(by_name)

    # Prepare messages for state updates
    # Iterate all controls
    for action_control, action_mapping in actions.items():
        # Iteare all actions mapped to this control
        for action, options in action_mapping.items():
            actions[action_control][action]["state_messages"] = []
            # Iterate all controls which states should be update when
            # this actions occurs
            for state_control, state in options.get("states", {}).items():
                control_info = control_by_name[state_control]
                # Check which type of control is updated
                # in order to prepare the correct midi message
                if control_info["type"] == "note_on":
                    msg = mido.Message("note_on", note=control_info["id"])
                    if state:
                        msg.velocity = device["button_on"]
                    else:
                        msg.velocity = device["button_off"]
                    actions[action_control][action]["state_messages"].append(msg)


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


    off = device.get("button_off", 0)
    on = device.get("button_on", 127)
    cw = device.get("cw", 1)
    ccw = device.get("ccw", 64)

    port = mido.open_input(midi_device)

    with mido.open_output(midi_device) as outport:
        for msg in port:
            if msg.type == "note_on":
                name = device.get("note_on", {}).get(msg.note, "unknown")
                value = "press" if msg.velocity == on else "release"
                handle_actions(outport, value, actions.get(name, {}))
                print(f"{name}: {value}")
            elif msg.type == "control_change":
                name = device.get("control_change", {}).get(msg.control, "unknown")
                value = "cw" if msg.value == cw else "ccw"
                handle_actions(outport, value, actions.get(name, {}))
                print(f"{name}: {value}")
            elif msg.type == "pitchwheel":
                name = "Pitch"
                value = msg.pitch
                print(f"{name}: {value}")


if __name__ == "__main__":
    main()
