from fastapi import APIRouter,Depends
from core import db,require
from haul_dispatch import prepare,view

router=APIRouter(prefix="/coast-rounds/{code}/haul")

@router.get("")
def report(code:str,_=Depends(require())):
    with db() as cx:
        return view(cx,code)

@router.post("",status_code=202)
def dispatch(code:str,_=Depends(require("reviewer"))):
    with db() as cx:
        return prepare(cx,code)
