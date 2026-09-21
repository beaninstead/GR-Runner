import sys

IS_WEB = sys.platform in ("emscripten", "wasi")

_NICK_INPUT_ID = "fr-nick-input"


def debug_hotkeys_allowed():
    """Desktop always; web only on localhost / 127.0.0.1 / empty hostname."""
    if not IS_WEB:
        return True
    try:
        from platform import window

        host = str(getattr(window.location, "hostname", "") or "").strip().lower()
        return host in ("", "localhost", "127.0.0.1")
    except Exception:
        return False


def open_url(url):
    if IS_WEB:
        try:
            from platform import window

            window.open(url, "_blank")
            return
        except Exception:
            pass
    import webbrowser

    webbrowser.open(url)


def show_nickname_html_input(initial: str = "") -> None:
    """Show/focus an HTML <input> so mobile browsers open the soft keyboard.

    pygame.key.start_text_input() alone does not raise the OSK on Safari/Chrome
    for canvas games; a real focused DOM input is required.
    """
    if not IS_WEB:
        return
    try:
        from platform import window

        doc = window.document
        el = doc.getElementById(_NICK_INPUT_ID)
        if el is None:
            el = doc.createElement("input")
            el.id = _NICK_INPUT_ID
            el.type = "text"
            el.setAttribute("autocomplete", "nickname")
            el.setAttribute("autocapitalize", "off")
            el.setAttribute("autocorrect", "off")
            el.setAttribute("spellcheck", "false")
            el.setAttribute("enterkeyhint", "done")
            el.setAttribute("maxlength", "16")
            el.setAttribute("inputmode", "text")
            el.setAttribute("placeholder", "Nickname (3–16)")
            # Visible overlay: opacity:0 / display:none often blocks the OSK on iOS.
            # font-size >= 16px avoids Safari auto-zoom on focus.
            el.style.cssText = (
                "position:fixed;left:50%;top:38%;transform:translate(-50%,-50%);"
                "width:min(86vw,420px);height:48px;z-index:10000;"
                "font-size:16px;line-height:20px;font-family:system-ui,sans-serif;"
                "border:3px solid #6b3fa0;border-radius:12px;"
                "padding:8px 14px;box-sizing:border-box;"
                "background:#ffffff;color:#1a1028;outline:none;"
                "-webkit-appearance:none;appearance:none;"
            )
            doc.body.appendChild(el)
            # Enter / Escape flags polled from Python (JS→Python callbacks are flaky).
            window.eval(
                """
(function () {
  var el = document.getElementById('fr-nick-input');
  if (!el || el._frNickBound) return;
  el._frNickBound = true;
  window.__frNickEnter = false;
  window.__frNickEscape = false;
  el.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      window.__frNickEnter = true;
    } else if (e.key === 'Escape') {
      e.preventDefault();
      window.__frNickEscape = true;
    }
  });
  // Re-focus on canvas taps while nickname mode is active (iOS often
  // drops focus after the programmatic focus from SUBMIT SCORE).
  var refocus = function () {
    if (!window.__frNeedNickInput) return;
    var n = document.getElementById('fr-nick-input');
    if (n && n.style.display !== 'none') {
      try { n.focus(); } catch (err) {}
    }
  };
  var canvas = document.getElementById('canvas');
  if (canvas && !canvas._frNickFocusBound) {
    canvas._frNickFocusBound = true;
    canvas.addEventListener('touchend', refocus, {passive: true});
    canvas.addEventListener('mouseup', refocus);
  }
})();
"""
            )

        el.value = str(initial or "")[:16]
        el.style.display = "block"
        window.__frNeedNickInput = True
        window.__frNickEnter = False
        window.__frNickEscape = False
        try:
            el.focus()
            # Place caret at end.
            length = len(str(el.value))
            if hasattr(el, "setSelectionRange"):
                el.setSelectionRange(length, length)
        except Exception:
            pass
    except Exception:
        pass


def hide_nickname_html_input() -> None:
    if not IS_WEB:
        return
    try:
        from platform import window

        window.__frNeedNickInput = False
        window.__frNickEnter = False
        window.__frNickEscape = False
        el = window.document.getElementById(_NICK_INPUT_ID)
        if el is not None:
            try:
                el.blur()
            except Exception:
                pass
            el.style.display = "none"
    except Exception:
        pass


def focus_nickname_html_input() -> None:
    if not IS_WEB:
        return
    try:
        from platform import window

        el = window.document.getElementById(_NICK_INPUT_ID)
        if el is None:
            return
        window.__frNeedNickInput = True
        el.style.display = "block"
        el.focus()
    except Exception:
        pass


def poll_nickname_html_input():
    """Return current input value, or None if the bridge is inactive/unavailable."""
    if not IS_WEB:
        return None
    try:
        from platform import window

        el = window.document.getElementById(_NICK_INPUT_ID)
        if el is None:
            return None
        display = str(getattr(el.style, "display", "") or "")
        if display == "none":
            return None
        return str(el.value)[:16]
    except Exception:
        return None


def consume_nickname_html_enter() -> bool:
    if not IS_WEB:
        return False
    try:
        from platform import window

        if bool(getattr(window, "__frNickEnter", False)):
            window.__frNickEnter = False
            return True
    except Exception:
        pass
    return False


def consume_nickname_html_escape() -> bool:
    if not IS_WEB:
        return False
    try:
        from platform import window

        if bool(getattr(window, "__frNickEscape", False)):
            window.__frNickEscape = False
            return True
    except Exception:
        pass
    return False
