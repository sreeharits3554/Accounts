"""Market-data sources. Each returns a list of `Bar` with naive IST bar-start timestamps."""


class SourceError(RuntimeError):
    """A data source failed (network, auth, or unexpected response). Never contains secrets."""
