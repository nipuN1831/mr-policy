import importlib
import pkgutil

from policy_wind_tunnel.civic import data
from policy_wind_tunnel.civic.models import CountryPack

_CACHE: dict[str, CountryPack] = {}


def _discover() -> dict[str, CountryPack]:
    if not _CACHE:
        for module_info in pkgutil.iter_modules(data.__path__):
            module = importlib.import_module(f"{data.__name__}.{module_info.name}")
            pack = CountryPack.model_validate(module.PACK)
            _CACHE[pack.code] = pack
    return _CACHE


def available_countries() -> list[dict[str, str]]:
    return [
        {"code": p.code, "name": p.name, "status": p.status}
        for p in sorted(_discover().values(), key=lambda pack: pack.name)
    ]


def load_pack(code: str) -> CountryPack:
    packs = _discover()
    if code not in packs:
        raise KeyError(code)
    return packs[code]
