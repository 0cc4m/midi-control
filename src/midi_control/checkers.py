import dbus
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
    return subprocess.run(
        options["check"]["command"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.decode("UTF-8")


@checker("dbus")
def dbus_checker(options):
    check = options["check"]
    service = check["service"]
    path = check["path"]
    method = check["method"]
    try:
        proxy = SessionBus().get_object(service, path)
        method = proxy.get_dbus_method(method)
        res = method()
        if isinstance(res, dbus.types.Boolean):
            res = bool(res)
        return res

    except DBusException as e:
        log.info("Could not create dbus proxy in dbus action: %s"
                 % e.get_dbus_message())
        return None
