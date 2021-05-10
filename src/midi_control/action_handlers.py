import subprocess
import mido
import logging
import sys
import threading
import time
from dbus import SessionBus
from dbus.exceptions import DBusException

from .checkers import checkers

log = logging.getLogger("midi-control")

handler_classes = {}

terminate = False


def terminate_threads(*_):
    global terminate
    terminate = True
    sys.exit(0)


def action_handler(name):
    def handler(handler_class):
        handler_classes[name] = handler_class
        return handler_class

    return handler


class ActionHandler:
    def __init__(self, options, controls, consts, midi_out):
        self.options = options
        self.controls = controls
        self.consts = consts
        self.midi_out = midi_out

        check = self.options.get("check", None)

        if check:
            self.check_state()

            freq = check.get("frequency", None)
            if freq:
                self.check_thread = threading.Thread(
                    target=self.regular_check,
                    args=(freq,),
                )
                self.check_thread.start()

    def __call__(self, msg):
        pass

    def set_led(self, name, value):
        msg = mido.Message(
            "note_on",
            note=self.controls[name]["id"],
            velocity=self.consts["note_on_values"][value],
        )
        self.midi_out.send(msg)

    def check_state(self):
        pass

    def regular_check(self, frequency):
        while not terminate:
            time.sleep(1 / frequency)
            self.check_state()


@action_handler("command")
class CommandAction(ActionHandler):
    def __call__(self, msg):
        subprocess.run(self.options["command"])
        for led, value in self.options.get("states", {}).items():
            self.set_led(led, value)

    def check_state(self):
        if "check" in self.options:
            check_type = self.options["check"]["type"]
            invert = self.options["check"].get("invert", False)
            result = checkers[check_type](self.options)
            if isinstance(result, bool) and result ^ invert:
                for led, value in self.options.get("states", {}).items():
                    self.set_led(led, value)


@action_handler("toggle")
class ToggleAction(ActionHandler):
    def __init__(self, options, controls, consts, midi_out):
        super().__init__(options, controls, consts, midi_out)
        self.state = False

    def __call__(self, msg):
        if self.state:
            subprocess.run(self.options["command_on"])
            for led, value in self.options.get("states_on", {}).items():
                self.set_led(led, value)
            self.state = False
        else:
            subprocess.run(self.options["command_off"])
            for led, value in self.options.get("states_off", {}).items():
                self.set_led(led, value)
            self.state = True

    def check_state(self):
        if "check" in self.options:
            check_type = self.options["check"]["type"]
            result = checkers[check_type](self.options)
            if result:
                self.state = True
                for led, value in self.options.get("states_on", {}).items():
                    self.set_led(led, value)
            else:
                self.state = False
                for led, value in self.options.get("states_off", {}).items():
                    self.set_led(led, value)


@action_handler("fader_command")
class FaderCommandAction(ActionHandler):
    def __call__(self, msg):
        minv = self.options["min"]
        maxv = self.options["max"]
        val = msg.bin()[2]

        final = int(round(minv + val / 127 * maxv, 0))

        command = self.options["command"].copy()
        command = [s.replace("$VALUE", str(final)) for s in command]

        subprocess.run(command)

    def check_state(self):
        if "check" in self.options:
            check_type = self.options["check"]["type"]
            minv = self.options["min"]
            maxv = self.options["max"]
            result = max(min(int(checkers[check_type](self.options)), maxv),
                         minv)
            final = int(round((result - minv) / maxv * 127, 0))
            for fader in self.options.get("states", []):
                address = self.controls[fader]["id"]
                msg = mido.Message.from_bytes([address, 0, final])
                self.midi_out.send(msg)


@action_handler("dbus")
class DBusAction(ActionHandler):
    def __init__(self, options, controls, consts, midi_out):
        super().__init__(options, controls, consts, midi_out)
        self.dbus_method = False

    def __call__(self, msg):
        method_name = self.options["method"]
        service = self.options["service"]
        path = self.options["path"]
        if not self.dbus_method:
            try:
                proxy = SessionBus().get_object(service, path)
                method = proxy.get_dbus_method(method_name)
                self.dbus_method = method
            except DBusException as e:
                log.error(
                    "Could not create dbus proxy in dbus action: %s"
                    % e.get_dbus_message()
                )
                return

        args = self.options.get("args", [])

        self.dbus_method(*args)

        for led, value in self.options.get("states", {}).items():
            self.set_led(led, value)

    def check_state(self):
        if "check" in self.options:
            check_type = self.options["check"]["type"]
            invert = self.options["check"].get("invert", False)
            result = checkers[check_type](self.options)
            if result ^ invert:
                for led, value in self.options.get("states", {}).items():
                    self.set_led(led, value)


@action_handler("dbus_toggle")
class DBusToggleAction(ActionHandler):
    def __init__(self, options, controls, consts, midi_out):
        super().__init__(options, controls, consts, midi_out)
        self.dbus_method = False
        self.state = False

    def __call__(self, msg):
        method_name = self.options["method"]
        service = self.options["service"]
        path = self.options["path"]
        if not self.dbus_method:
            try:
                proxy = SessionBus().get_object(service, path)
                method = proxy.get_dbus_method(method_name)
                self.dbus_method = method
            except DBusException as e:
                log.error(
                    "Could not create dbus proxy in dbus action: %s"
                    % e.get_dbus_message()
                )
                return

        if self.state:
            args = self.options.get("args_on", [])
            self.state = False
            for led, value in self.options.get("states_on", {}).items():
                self.set_led(led, value)
        else:
            args = self.options.get("args_off", [])
            self.state = True
            for led, value in self.options.get("states_off", {}).items():
                self.set_led(led, value)

        self.dbus_method(*args)

    def check_state(self):
        if "check" in self.options:
            check_type = self.options["check"]["type"]
            result = checkers[check_type](self.options)
            if result:
                self.state = True
                for led, value in self.options.get("states_on", {}).items():
                    self.set_led(led, value)
            else:
                self.state = False
                for led, value in self.options.get("states_off", {}).items():
                    self.set_led(led, value)
