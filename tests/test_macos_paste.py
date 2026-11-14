"""Native paste routing avoids WebKit image promises and retains normal text paste."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ytmp3.macos_paste import install_paste_shortcut, paste_into_focused_field


class MacPasteTests(unittest.TestCase):
    def test_command_v_dispatches_to_frontend_without_native_webkit_paste(self):
        event_api = Mock()
        helper = Mock()
        helper.callAfter.side_effect = lambda task: task()
        modules = {
            "AppKit": SimpleNamespace(
                NSEvent=event_api, NSEventMaskKeyDown=1, NSEventModifierFlagCommand=2
            ),
            "PyObjCTools": SimpleNamespace(AppHelper=helper),
        }
        window = Mock()
        window.native.isKeyWindow.return_value = True
        event = Mock()
        event.keyCode.return_value = 9
        event.modifierFlags.return_value = 2
        with (
            patch.dict("sys.modules", modules),
            patch("ytmp3.macos_paste.threading.Thread") as thread,
        ):
            stop = install_paste_shortcut(window)
            handler = event_api.addLocalMonitorForEventsMatchingMask_handler_.call_args.args[1]
            self.assertIsNone(handler(event))
            window.run_js.assert_not_called()
            self.assertEqual(thread.call_args.kwargs["target"], window.run_js)
            self.assertEqual(
                thread.call_args.kwargs["args"], ("window.dispatchEvent(new Event('nativepaste'))",)
            )
            thread.return_value.start.assert_called_once()
            window.native.firstResponder.assert_not_called()
            event.keyCode.return_value = 8
            self.assertIs(handler(event), event)
            event.keyCode.return_value = 9
            window.native.isKeyWindow.return_value = False
            self.assertIs(handler(event), event)
            stop()
            event_api.removeMonitor_.assert_called_once()

    def test_text_fallback_uses_standard_responder_paste_on_main_thread(self):
        helper = Mock()
        helper.callAfter.side_effect = lambda task: task()
        window = Mock()
        responder = window.native.firstResponder.return_value
        with patch.dict("sys.modules", {"PyObjCTools": SimpleNamespace(AppHelper=helper)}):
            paste_into_focused_field(window)
        responder.paste_.assert_called_once_with(None)
