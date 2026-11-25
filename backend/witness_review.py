from fastapi import HTTPException
from round_registry import segment

def accept(cx,code,bag,source,note,operator):
    segment(cx,code)
    sample=cx.execute("SELECT * FROM coast_samples WHERE segment=%s AND bag=%s FOR UPDATE",(code,bag)).fetchone()
    if sample is None:
        raise HTTPException(404,"样袋缺双称记录")
    if sample["status"]=="accepted":
        raise HTTPException(409,"此样袋已有见证记录")
    if sample["status"]=="disputed" and len(note)<5:
        raise HTTPException(409,"差异超过 0.50 公斤，需要说明取舍证据")
    net=sample["first_kg"] if source=="first" else sample["second_kg"]
    cx.execute("UPDATE coast_samples SET status='accepted' WHERE segment=%s AND bag=%s",(code,bag))
    return cx.execute("INSERT INTO coast_witness VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
                    (code,bag,net,source,operator,note)).fetchone()
