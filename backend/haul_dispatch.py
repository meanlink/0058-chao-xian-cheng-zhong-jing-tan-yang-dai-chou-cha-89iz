from fastapi import HTTPException
from psycopg.types.json import Jsonb
from core import enqueue
from haul_correction import basis_rows, view
from ratio import estimate, stratified_rows
from round_registry import round_state

def prepare(cx, code):
    cycle = round_state(cx, code, True)
    if cycle["status"] != "open":
        raise HTTPException(409, "这轮抽查已锁定")
    counts = stratified_rows(cx, code)
    if not counts or any(r["witness_count"] < min(r["bags"], 2) for r in counts):
        raise HTTPException(409, "每段至少要两袋签过见证，单袋区须见证该袋")
    cx.execute("UPDATE coast_rounds SET status='locked' WHERE code=%s", (code,))
    return {"job_id": enqueue(cx, "issue_coast_haul", {"round": code})}

def issue(cx, code):
    points = stratified_rows(cx, code)
    net, parts = estimate(points)
    basis = [{**row, "accepted_kg": float(row["accepted_kg"])} for row in basis_rows(cx, code)]
    cx.execute("""
      INSERT INTO coast_haul(round,version,estimated_kg,pieces,basis)
      VALUES (%s,1,%s,%s,%s)
    """, (code, net, Jsonb(parts), Jsonb(basis)))
    cx.execute("UPDATE coast_rounds SET status='issued',current_version=1 WHERE code=%s", (code,))
    return {"round": code, "estimated_kg": float(net), "pieces": parts}
