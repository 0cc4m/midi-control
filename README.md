# midi-control

Trigger actions on MIDI input.

This script was developed for midi controlers from the Steinberg CMC series, but it is probably adaptable to other controllers by adding a new device definition file.

## Installation

Use setuptools:
``` bash
git pull https://github.com/0cc4m/midi-control.git
cd midi-control
python setup.py install --user
```

Or on Arch Linux you can use the supplied PKGBUILD.

## Configuration

`midi-control` reads its configuration from `~/.config/midi-control/`.
It expects two files in that directory:
* device.yml
* actions.yml

### device.yml

This file defines all the buttons and controls which are present on the used controller as well as some constansts.
Your device may already have a definition file, check the `devices` directory of this repository.

The top level entries of this file are the MIDI ports the device provides. This can be more than one, for example in the case of the Steinberg Quick Controller (`devices/steinberg_qc.yml`).
(With the exception of the `consts`entry)
The port entries define names for controls by key and type.

Let's imagine a midi controller that has one control knob and one button.
The knob might send 'control_change' for controller 0x10 and the button 'note_on' for the key 0x40.
A definiton for this device could look like this:

``` yaml
Simple Controller MIDI 1:
  note_on:
    0x40: button_1
  control_change:
    0x10: knob_1
```

### actions.yml

This file maps actions to the controls defined in device.yml.
Currently the following actions are available:
* command
* toggle
* fader_command
* dbus
* dbus_toggle

Actions can be triggered by different events:
* press
* release
* cw (clockwise rotation)
* ccw (counter clockwise rotation)
* set (value change)

The `set` event always fires when the associated control sends a message. This is useful for processing raw midi messages.

(What constitutes a press, release, etc. event is defined in the device constants)

Top level entries in this file define for which port the actions are defined.
An `actions.yml` for the simple controller might look like this:
``` yaml
Simple Controller MIDI 1:
  button_1:
    press:
      type: command
      command: ["notify-send", "Button 1 was pressed"]
    release:
      type: command
      command: ["notify-send", "Button 1 was release"]

```

## Actions

Configure action:
``` yaml
<device>:
  <control>:
    <event>:
      type: <action_type>
      <option>: <value>
      ...
      ...
```

Most actions also accept a `states` options (or `states_on` and `states_off` for toggle commands)
This is used to define MIDI messages that should be sent back to the controller when the actions gets executed.
Some controllers accept midi messages to set the state of an associated LEDs, so this con for example be used to display the state of a toggle command.

### command
``` yaml
<event>:
  type: command
  command: ["notify-send", "pressed"] # Command to be executed
  states: 
    button_1: on # Turn led of button_1 on
```

### toggle_command
``` yaml
<event>:
  type: command
  command_on: ["notify-send", "toggle on"]
  command_on: ["notify-send", "toggle off"]
  states_on: 
    button_1: on # Turn led of button_1 on
  states_off: 
    button_1: off # Turn led of button_1 on
```

### fader_command
This actions takes the third byte of whatever mesage triggered it and maps to the interval specified by the min and max options.
It the replaces any occurence of `$VALUE` in the command with this value.

Example for controlling volume:
``` yaml
set:
  type: fader_command
  command: ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "$VALUE%"]
  min: 0
  max: 100
```

### dbus
Calls a dbus method.
Arguments kan be supllied as list in `args`.
``` yaml
<event>:
  type: dbus
  service: net.sourceforge.mumble.mumble
  path: /
  method: setSelfMuted
  args:
    - true
  states: 
    button_1: on # Turn led of button_1 on

```

### dbus_toggle
Like command_toggle, but with dbus methods.
Arguments can be supplied as a list in `args_on` and `args_off`

``` yaml
<event>:
  type: dbus_toggle
  service: net.sourceforge.mumble.mumble
  path: /
  method: setSelfMuted
  args_on:
    - true
  args_off:
    - false
  states_on:
    write: on
    states_off:
    write: off
```
