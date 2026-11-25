from typing import Literal, Annotated
from pydantic import BaseModel, Field, StringConstraints

class CorrectionChoice(BaseModel):
    segment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    bag: int = Field(ge=1, le=4000)
    source: Literal['first', 'second']
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] = ""

class CorrectionRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=200)]
    choices: list[CorrectionChoice] = Field(min_length=1, max_length=50)
