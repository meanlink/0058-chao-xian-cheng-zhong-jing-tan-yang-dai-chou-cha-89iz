from fastapi import HTTPException

def round_state(cx,key,lock=False):
    row=cx.execute("SELECT * FROM coast_rounds WHERE code=%s"+(" FOR UPDATE" if lock else ""),(key,)).fetchone()
    if not row: raise HTTPException(404,"抽查批次不存在")
    return row

def segment(cx,key):
    row=cx.execute("SELECT * FROM coast_segments WHERE code=%s",(key,)).fetchone()
    if not row: raise HTTPException(404,"没有对应净滩区段")
    if round_state(cx,row["round"],True)["status"]!="open":
        raise HTTPException(409,"该区段已进入清运交接，样袋证据冻结")
    return row
