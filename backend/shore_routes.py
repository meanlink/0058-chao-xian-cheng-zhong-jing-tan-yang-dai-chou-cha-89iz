from fastapi import APIRouter,Depends
from core import db,require
from round_registry import round_state

router=APIRouter()

@router.get("/coast-rounds")
def rounds(_=Depends(require())):
    with db() as cx:
        return cx.execute("SELECT * FROM coast_rounds ORDER BY code").fetchall()

@router.get("/coast-rounds/{code}/segments")
def segments(code:str,_=Depends(require())):
    with db() as cx:
        round_state(cx,code)
        return cx.execute("SELECT * FROM coast_segments WHERE round=%s ORDER BY code",(code,)).fetchall()
