import sys

IS_WEB = sys.platform in ("emscripten", "wasi")


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
