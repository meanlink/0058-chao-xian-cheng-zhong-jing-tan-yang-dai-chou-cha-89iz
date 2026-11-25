from fastapi import APIRouter,Depends
from core import db,require
from weigh_input import Weighing
from weigh_log import record,sample_rows

router=APIRouter()

@router.get("/coast-rounds/{code}/samples")
def samples(code:str,_=Depends(require())):
    with db() as cx:
        return sample_rows(cx,code)

@router.post("/coast-segments/{code}/samples",status_code=201)
def add(code:str,body:Weighing,_=Depends(require("operator"))):
    with db() as cx:
        return record(cx,code,body)
