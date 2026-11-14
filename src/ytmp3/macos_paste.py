"""Route Cmd-V through React before WebKit reads Photos file promises."""

import threading
from collections.abc import Callable
from typing import Any


def install_paste_shortcut(window: Any) -> Callable[[], None]:
    from AppKit import NSEvent, NSEventMaskKeyDown, NSEventModifierFlagCommand
    from PyObjCTools import AppHelper

    holder = {"token": None, "closed": False}

    def key_down(event):
        if (
            window.native.isKeyWindow()
            and event.keyCode() == 9
            and event.modifierFlags() & NSEventModifierFlagCommand
        ):
            # pywebview waits for JavaScript completion; keep that wait off AppKit's
            # main thread so WebKit can process the request and paint the result.
            threading.Thread(
                target=window.run_js,
                args=("window.dispatchEvent(new Event('nativepaste'))",),
                daemon=True,
            ).start()
            return None
        return event

    def install():
        if not holder["closed"]:
            holder["token"] = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown, key_down
            )

    def remove():
        holder["closed"] = True
        if holder["token"] is not None:
            NSEvent.removeMonitor_(holder["token"])
            holder["token"] = None

    AppHelper.callAfter(install)
    return lambda: AppHelper.callAfter(remove)


def paste_into_focused_field(window: Any) -> None:
    from PyObjCTools import AppHelper

    def paste():
        responder = window.native.firstResponder()
        if responder is not None and responder.respondsToSelector_("paste:"):
            responder.paste_(None)

    AppHelper.callAfter(paste)
