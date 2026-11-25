from haul_correction import CORRECTION_KIND, apply_correction
from haul_dispatch import issue

def run(cx, kind, data):
    if kind == "issue_coast_haul":
        return issue(cx, data["round"])
    if kind == CORRECTION_KIND:
        return apply_correction(cx, data["round"], data["correction_id"])
    raise ValueError(kind)
