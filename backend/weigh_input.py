from decimal import Decimal
from pydantic import BaseModel,Field

class Weighing(BaseModel):
    bag: int=Field(ge=1,le=4000)
    first_kg: Decimal=Field(gt=0,le=80,decimal_places=2)
    second_kg: Decimal=Field(gt=0,le=80,decimal_places=2)
