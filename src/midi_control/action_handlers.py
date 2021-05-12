import subprocess
import mido
import logging
import sys
import threading
import time
from dbus import SessionBus
from dbus.exceptions import DBusException

from .checkers import checkers
from .led_handlers import led_handlers

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
    def __init__(self, options, controls, consts):
        self.options = options
        self.controls = controls
        self.consts = consts

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
        led_info = self.controls[name]
        handler = led_handlers[led_info["led_type"]]
        handler(led_info["id"],
                value,
                led_info["device_out_port"],
                self.options,
                self.consts)

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
            if isinstance(result, str):
                result = result.strip() in self.options["check"]\
                    .get("eval_true", ["true", "True"])
            if isinstance(result, bool) and result ^ invert:
                for led, value in self.options.get("states", {}).items():
                    self.set_led(led, value)


@action_handler("toggle")
class ToggleAction(ActionHandler):
    def __init__(self, options, controls, consts):
        super().__init__(options, controls, consts)
        self.state = False

    def __call__(self, msg):
        if self.state:
            subprocess.run(self.options["command_on"])
            for led, value in self.options.get("states_off", {}).items():
                self.set_led(led, value)
            self.state = False
        else:
            subprocess.run(self.options["command_off"])
            for led, value in self.options.get("states_on", {}).items():
                self.set_led(led, value)
            self.state = True

    def check_state(self):
        if "check" in self.options:
            check_type = self.options["check"]["type"]
            invert = self.options["check"].get("invert", False)
            result = checkers[check_type](self.options)
            if isinstance(result, str):
                result = result.strip() in self.options["check"]\
                    .get("eval_true", ["true", "True"])
            if isinstance(result, bool) and result ^ invert:
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
            try:
                result = max(min(
                    int(checkers[check_type](self.options)), maxv), minv)
            except ValueError as err:
                log.info("Check returned invalid value %s, ", err)
                return
            for fader in self.options.get("states", []):
                self.set_led(fader, result)
                

@action_handler("knob_command")
class KnobCommandAction(ActionHandler):
    def __init__(self, options, controls, consts):
        super().__init__(options, controls, consts)
        self.value = 0

    def __call__(self, msg):
        minv = self.options.get("min", 0)
        maxv = self.options.get("max", 100)
        inc = self.options["inc"]

        if msg.value == self.consts["control_change_values"]["ccw"]:
            inc *= -1

        self.value += inc

        final = int(max(min(self.value, maxv), minv))

        command = self.options["command"].copy()
        command = [s.replace("$VALUE", str(final)) for s in command]

        subprocess.run(command, check=False)

    def check_state(self):
        if "check" in self.options:
            check_type = self.options["check"]["type"]
            minv = self.options.get("min", 0)
            maxv = self.options.get("max", 100)
            try:
                result = max(min(
                    int(checkers[check_type](self.options)), maxv), minv)
                self.value = result
            except ValueError as err:
                log.info("Check returned invalid value %s, ", err)
                return
            for knob in self.options.get("states", []):
                self.set_led(knob, result)


@action_handler("dbus")
class DBusAction(ActionHandler):
    def __init__(self, options, controls, consts):
        super().__init__(options, controls, consts)
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
                log.info(
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
            if isinstance(result, str):
                result = result in self.options["check"].get("eval_true",
                                                             ["true", "True"])
            if isinstance(result, bool) and result ^ invert:
                for led, value in self.options.get("states", {}).items():
                    self.set_led(led, value)


@action_handler("dbus_toggle")
class DBusToggleAction(ActionHandler):
    def __init__(self, options, controls, consts):
        super().__init__(options, controls, consts)
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
                log.info(
                    "Could not create dbus proxy in dbus action: %s"
                    % e.get_dbus_message()
                )
                return

        if self.state:
            args = self.options.get("args_on", [])
            self.state = False
            for led, value in self.options.get("states_off", {}).items():
                self.set_led(led, value)
        else:
            args = self.options.get("args_off", [])
            self.state = True
            for led, value in self.options.get("states_on", {}).items():
                self.set_led(led, value)

        self.dbus_method(*args)

    def check_state(self):
        if "check" in self.options:
            check_type = self.options["check"]["type"]
            invert = self.options["check"].get("invert", False)
            result = checkers[check_type](self.options)
            if isinstance(result, str):
                result = result in self.options["check"].get("eval_true",
                                                             ["true", "True"])
            if isinstance(result, bool) and result ^ invert:
                self.state = True
                for led, value in self.options.get("states_on", {}).items():
                    self.set_led(led, value)
            else:
                self.state = False
                for led, value in self.options.get("states_off", {}).items():
                    self.set_led(led, value)
