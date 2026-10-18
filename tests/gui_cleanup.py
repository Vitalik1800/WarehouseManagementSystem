"""Test-only cleanup for scheduled Tk/CustomTkinter callbacks."""


def cleanup_gui(root):
    """Cancel pending Tcl after jobs before destroying a test root.

    The root may already be destroyed by application shutdown.
    Do not call update() here: it would execute callbacks during teardown.
    """
    try:
        exists = bool(root.winfo_exists())
    except (AttributeError, RuntimeError, ValueError):
        return
    except Exception as exc:
        if exc.__class__.__name__ == "TclError":
            return
        raise

    if not exists:
        return

    try:
        pending = root.tk.call("after", "info")
        if isinstance(pending, str):
            pending = root.tk.splitlist(pending)
        for job in pending:
            try:
                root.after_cancel(job)
            except Exception as exc:
                if exc.__class__.__name__ != "TclError":
                    raise
    finally:
        if root.winfo_exists():
            root.destroy()
