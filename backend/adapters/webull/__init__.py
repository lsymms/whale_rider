from .market import StockTickStream, StreamDisconnected, StreamRunReport

__all__ = ["CapabilityProbe", "ProbeReport", "WebullClient", "WebullCredentials", "StockTickStream", "StreamDisconnected", "StreamRunReport", "ContractListError", "OptionContract", "OptionContractCatalog"]


def __getattr__(name: str):
    if name in {"CapabilityProbe", "ProbeReport", "WebullClient", "WebullCredentials"}:
        from . import probe

        return getattr(probe, name)
    if name in {"ContractListError", "OptionContract", "OptionContractCatalog"}:
        from . import contracts

        return getattr(contracts, name)
    raise AttributeError(name)
