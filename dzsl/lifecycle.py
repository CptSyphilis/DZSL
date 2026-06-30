def cancel_active_downloads(app):
    progress = getattr(app, "_active_progress", None)
    if progress is not None:
        progress.request_cancel()
