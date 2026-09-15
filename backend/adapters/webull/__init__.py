from .market import StockTickStream, StreamDisconnected, StreamRunReport

__all__ = ["CapabilityProbe", "ProbeReport", "WebullClient", "WebullCredentials", "StockTickStream", "StreamDisconnected", "StreamRunReport"]


def __getattr__(name: str):
    if name in {"CapabilityProbe", "ProbeReport", "WebullClient", "WebullCredentials"}:
        from . import probe

        return getattr(probe, name)
    raise AttributeError(name)
