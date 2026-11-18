"""Company sources. Each takes a raw-data directory and returns list[Company]."""
from . import boem, oklahoma, texas_rrc


def _boem(raw):
    return boem.fetch(raw, states=boem.ALL_STATES)


REGISTRY = {
    "boem": _boem,
    "tx_rrc": texas_rrc.fetch,
    "ok_occ": oklahoma.fetch,
}
