from contextvars import ContextVar

# Interactive search may return no candidates on outage; the worker must
# distinguish an unavailable source from a successful empty response.
strict_scraping = ContextVar("strict_scraping", default=False)


class SourceUnavailable(RuntimeError):
    pass
