from fastapi import APIRouter, Depends
from core import db, require
from correction_input import CorrectionRequest
from haul_correction import open_correction, retry_correction, view
from haul_dispatch import prepare

router = APIRouter(prefix="/coast-rounds/{code}/haul")

@router.get("")
def report(code: str, _=Depends(require())):
    with db() as cx:
        return view(cx, code)

@router.post("", status_code=202)
def dispatch(code: str, _=Depends(require("reviewer"))):
    with db() as cx:
        return prepare(cx, code)

@router.post("/corrections", status_code=202)
def correct(code: str, body: CorrectionRequest, user=Depends(require("reviewer"))):
    with db() as cx:
        return open_correction(cx, code, body, user["email"])

@router.post("/corrections/{correction_id}/retry", status_code=202)
def retry(code: str, correction_id: int, _=Depends(require("reviewer"))):
    with db() as cx:
        return retry_correction(cx, code, correction_id)
