"""Export HA's schema library; legacy/test hosts can use voluptuous."""

try:
    import probatio as vol
except (ImportError, RuntimeError):
    import voluptuous as vol

__all__ = ["vol"]
