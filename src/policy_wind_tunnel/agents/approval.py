from policy_wind_tunnel.contract.models import Contract

VALID_STATUSES = ("approved", "rejected", "proposed")


class ApprovalError(Exception):
    pass


def decide_ambiguity(contract: Contract, ambiguity_id: str, status: str, resolution: str | None = None) -> Contract:
    if status not in VALID_STATUSES:
        raise ApprovalError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    data = contract.model_dump()
    for item in data["ambiguities"]:
        if item["id"] == ambiguity_id:
            item["status"] = status
            if resolution is not None:
                item["resolution"] = resolution
            return Contract.model_validate(data)
    raise ApprovalError(f"no ambiguity with id {ambiguity_id!r}")
