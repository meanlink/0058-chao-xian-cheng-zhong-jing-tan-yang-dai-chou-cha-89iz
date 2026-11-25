from typing import Literal,Annotated
from pydantic import BaseModel,StringConstraints

class Witness(BaseModel):
    source: Literal['first','second']
    note: Annotated[str,StringConstraints(strip_whitespace=True,max_length=160)] = ""
