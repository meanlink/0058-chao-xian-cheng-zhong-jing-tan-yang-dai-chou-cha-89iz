from fastapi import APIRouter,Depends
from core import db,require
from witness_input import Witness
from witness_review import accept

router=APIRouter(prefix="/coast-segments")

@router.post("/{code}/samples/{bag}/witness",status_code=201)
def sign(code:str,bag:int,body:Witness,user=Depends(require("reviewer"))):
    with db() as cx:
        return accept(cx,code,bag,body.source,body.note,user["email"])
