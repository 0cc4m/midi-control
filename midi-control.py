import argparse
import mido
import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("device_file")
    args = parser.parse_args()

    with open(args.device_file, "r") as f:
        device = yaml.load(f.read(), Loader=yaml.SafeLoader)

    midi_device = device["midi_device"]
    types = device["types"]
    buttons = device["buttons"]
    encoders = device["encoders"]
    off = device["button_off"]
    on = device["button_on"]
    cw = device["cw"]
    ccw = device["ccw"]
    fader_min = device["fader_min"]
    fader_max = device["fader_max"]

    button_names = {v: k for k, v in buttons.items()}
    encoder_names = {v: k for k, v in encoders.items()}

    port = mido.open_input(midi_device)

    with mido.open_output(midi_device) as outport:
        for msg in port:
            if msg.bin()[0] == types["button"]:
                print(f"{button_names[msg.bin()[1]]} "
                      f"{'ON' if msg.bin()[2] == on else 'OFF'}")
                outport.send(msg)
            elif msg.bin()[0] == types["encoder"]:
                print(f"Encoder {encoder_names[msg.bin()[1]]} "
                      f"{'CW' if msg.bin()[2] == cw else 'CCW'}")
            elif msg.bin()[0] == types["slider"]:
                print(f"Fader {msg.bin()[2]}")


if __name__ == "__main__":
    main()
