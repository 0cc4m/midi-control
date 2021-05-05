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


def handle_actions(event, actions):
    for action, options in actions.items():
        action_type = options["type"]
        if action == event:
            handlers[action_type](options)


@action_handler("command")
def command_action(options):
    subprocess.run(options["command"])


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
                handle_actions(value, actions.get(name, {}))
                print(f"{name}: {value}")
                outport.send(msg)
            elif msg.type == "control_change":
                name = device.get("control_change", {}).get(msg.control, "unknown")
                value = "cw" if msg.value == cw else "ccw"
                handle_actions(value, actions.get(name, {}))
                print(f"{name}: {value}")
            elif msg.type == "pitchwheel":
                name = "Pitch"
                value = msg.pitch
                print(f"{name}: {value}")


if __name__ == "__main__":
    main()
