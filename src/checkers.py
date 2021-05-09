import subprocess
import logging
from dbus import SessionBus
from dbus.exceptions import DBusException

log = logging.getLogger("midi-control")

checkers = {}


def checker(name):
    def check(checker):
        checkers[name] = checker
        return checker

    return check


@checker("command")
def command_checker(options):
    return subprocess.check_output(options["check"]["command"])


@checker("dbus")
def dbus_checker(options):
    check = options["check"]
    service = check["service"]
    path = check["path"]
    method = check["method"]
    try:
        proxy = SessionBus().get_object(service, path)
        method = proxy.get_dbus_method(method)
        return method()

    except DBusException as e:
        log.error("Could not create dbus proxy in dbus action: %s"
                  % e.get_dbus_message())
        return None
