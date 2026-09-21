import sys

IS_WEB = sys.platform in ("emscripten", "wasi")


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
