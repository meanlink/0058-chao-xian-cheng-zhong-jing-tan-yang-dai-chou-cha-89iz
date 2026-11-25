from decimal import Decimal

TOLERANCE = Decimal("0.50")

def weigh_status(first,second):
    return "disputed" if abs(first-second)>TOLERANCE else "awaiting"
