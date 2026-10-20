class BrowserError(Exception):
    pass


class BlockedUrlError(BrowserError):
    pass


class SearchBlockedError(BrowserError):
    pass
