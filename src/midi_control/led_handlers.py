import mido

led_handlers = {}


def led_handler(name):
    def handler(led_handler_func):
        led_handlers[name] = led_handler_func
        return led_handler_func

    return handler


@led_handler("default")
def default_led(midi_id, value, midi_port, _, consts):
    msg = mido.Message(
        "note_on",
        note=midi_id,
        velocity=consts["note_on_values"].get(value, 0),
    )
    midi_port.send(msg)


@led_handler("steinberg_knob")
def steinberg_knob_led(midi_id, value, midi_port, options, _):
    minv = options.get("min", 0)
    maxv = options.get("max", 100)
    nibble_value = int(round((value - minv) / maxv * 0x0b, 0))
    msg = mido.Message(
        "control_change",
        control=midi_id,
        value=0x0f & nibble_value
        )
    midi_port.send(msg)


@led_handler("steinberg_fader")
def steinberg_fader_led(midi_id, value, midi_port, options, _):
    minv = options.get("min", 0)
    maxv = options.get("max", 100)
    final_value = int(round((value - minv) / maxv * 127, 0))
    msg = mido.Message.from_bytes([midi_id, 0, final_value])
    midi_port.send(msg)
