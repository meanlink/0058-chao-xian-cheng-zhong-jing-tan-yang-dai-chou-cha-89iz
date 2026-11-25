from haul_dispatch import issue

def run(cx,kind,data):
    if kind!="issue_coast_haul": raise ValueError(kind)
    return issue(cx,data["round"])
