from fastapi import HTTPException
from psycopg.types.json import Jsonb
from core import enqueue
from ratio import estimate,stratified_rows
from round_registry import round_state

def prepare(cx,code):
    cycle=round_state(cx,code,True)
    if cycle["status"]!="open":
        raise HTTPException(409,"这轮抽查已锁定")
    counts=stratified_rows(cx,code)
    if not counts or any(r["witness_count"]<min(r["bags"],2) for r in counts):
        raise HTTPException(409,"每段至少要两袋签过见证，单袋区须见证该袋")
    cx.execute("UPDATE coast_rounds SET status='locked' WHERE code=%s",(code,))
    return {"job_id":enqueue(cx,"issue_coast_haul",{"round":code})}

def issue(cx,code):
    points=stratified_rows(cx,code)
    net,parts=estimate(points)
    cx.execute("INSERT INTO coast_haul(round,estimated_kg,pieces) VALUES (%s,%s,%s)",(code,net,Jsonb(parts)))
    cx.execute("UPDATE coast_rounds SET status='issued' WHERE code=%s",(code,))
    return {"round":code,"estimated_kg":float(net),"pieces":parts}

def view(cx,code):
    cycle=round_state(cx,code)
    report=cx.execute("SELECT * FROM coast_haul WHERE round=%s",(code,)).fetchone()
    return {"status":cycle["status"],"report":report,"coverage":stratified_rows(cx,code)}
