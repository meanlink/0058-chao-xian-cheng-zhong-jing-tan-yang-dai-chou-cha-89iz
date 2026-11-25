"""已签发清运单的更正流程。

更正发起时即把每个样袋本次采用的称重与原因快照固定下来，
后台重算只依据该快照；旧版清运单原样保留，重算失败不影响在用版本。
"""
from fastapi import HTTPException
from psycopg.types.json import Jsonb

from core import enqueue
from ratio import estimate, stratified_rows
from round_registry import round_state

CORRECTION_KIND = "correct_coast_haul"

def current_haul(cx, code, lock=False):
    row = cx.execute(
        "SELECT * FROM coast_haul WHERE round=%s AND version="
        "(SELECT current_version FROM coast_rounds WHERE code=%s)"
        + (" FOR UPDATE" if lock else ""),
        (code, code),
    ).fetchone()
    if row is None:
        raise HTTPException(409, "清运交接尚未签发，不能发起更正")
    return row

def basis_rows(cx, code):
    """出单时采用的样袋证据：只取见证通过的样袋，按段、袋号固定。"""
    return cx.execute("""
      SELECT w.segment, w.bag, w.accepted_kg, w.source, w.witness, w.note
      FROM coast_witness w
      JOIN coast_segments p ON p.code = w.segment
      WHERE p.round = %s
      ORDER BY w.segment, w.bag
    """, (code,)).fetchall()

def _evidence(cx, code, choices):
    """把复核员的选择与双称记录核对，固定本次取证快照。"""
    seen = set()
    evidence = []
    for choice in choices:
        key = (choice.segment, choice.bag)
        if key in seen:
            raise HTTPException(409, "同一样袋只能登记一条更正证据")
        seen.add(key)
        sample = cx.execute("""
          SELECT s.*, p.round, w.accepted_kg AS witnessed_kg
          FROM coast_samples s
          JOIN coast_segments p ON p.code = s.segment
          LEFT JOIN coast_witness w ON w.segment = s.segment AND w.bag = s.bag
          WHERE s.segment=%s AND s.bag=%s
        """, key).fetchone()
        if sample is None:
            raise HTTPException(404, f"样袋 {choice.segment}/{choice.bag} 没有双称记录")
        if sample["round"] != code:
            raise HTTPException(409, f"样袋 {choice.segment}/{choice.bag} 不属于本轮抽查")
        if sample["witnessed_kg"] is None:
            raise HTTPException(409, f"样袋 {choice.segment}/{choice.bag} 未参与本次出单，不能更正")
        accepted = sample["first_kg"] if choice.source == "first" else sample["second_kg"]
        evidence.append({
            "segment": choice.segment,
            "bag": choice.bag,
            "source": choice.source,
            "accepted_kg": float(accepted),
            "note": choice.note,
        })
    return evidence

def open_correction(cx, code, body, operator):
    round_state(cx, code, True)
    current_haul(cx, code)
    evidence = _evidence(cx, code, body.choices)
    correction = cx.execute("""
      INSERT INTO coast_haul_correction(round,base_version,reason,evidence,created_by)
      VALUES (%s,(SELECT current_version FROM coast_rounds WHERE code=%s),%s,%s,%s)
      RETURNING *
    """, (code, code, body.reason, Jsonb(evidence), operator)).fetchone()
    job_id = enqueue(cx, CORRECTION_KIND,
                     {"round": code, "correction_id": correction["id"]})
    return {"correction_id": correction["id"], "job_id": job_id,
            "base_version": correction["base_version"]}

def retry_correction(cx, code, correction_id):
    round_state(cx, code, True)
    correction = cx.execute(
        "SELECT * FROM coast_haul_correction WHERE round=%s AND id=%s FOR UPDATE",
        (code, correction_id),
    ).fetchone()
    if correction is None:
        raise HTTPException(404, "没有这条更正申请")
    if correction["status"] == "succeeded":
        raise HTTPException(409, "该更正已生成新版清运单，无需重试")
    if correction["status"] == "stale":
        raise HTTPException(409, "期间已有其他更正接替旧单，请重新核对后发起更正")
    job = cx.execute("""
      SELECT id,status FROM app_jobs
      WHERE kind=%s AND payload->>'round'=%s
        AND (payload->>'correction_id')::bigint=%s
      ORDER BY id DESC LIMIT 1
    """, (CORRECTION_KIND, code, correction_id)).fetchone()
    if job and job["status"] in ("queued", "running"):
        raise HTTPException(409, "该更正仍在处理中，不能重复出单")
    if job is None:
        raise HTTPException(409, "更正任务记录缺失，无法重试")
    # 复用同一条更正申请，仅重新入队，不会产生第二张单子。
    job_id = enqueue(cx, CORRECTION_KIND,
                     {"round": code, "correction_id": correction["id"]})
    return {"correction_id": correction["id"], "job_id": job_id}

def _corrected_basis(cx, code, correction):
    """以更正快照替换对应样袋的采用重量，其余样袋沿用出单依据。"""
    overrides = {(item["segment"], item["bag"]): item for item in correction["evidence"]}
    basis = []
    for row in basis_rows(cx, code):
        pick = overrides.pop((row["segment"], row["bag"]), None)
        if pick is None:
            basis.append({**dict(row), "accepted_kg": float(row["accepted_kg"])})
        else:
            basis.append({
                "segment": row["segment"], "bag": row["bag"],
                "accepted_kg": float(pick["accepted_kg"]), "source": pick["source"],
                "witness": correction["created_by"],
                "note": pick["note"] or correction["reason"],
            })
    basis.sort(key=lambda item: (item["segment"], item["bag"]))
    return basis

def _recalc_rows(cx, code, correction):
    """按固定证据替换样袋采用重量后，重新做分层放大推算。"""
    return cx.execute("""
      WITH override AS (
        SELECT segment, bag, accepted_kg
        FROM jsonb_to_recordset(%s::jsonb)
          AS e(segment text, bag int, source text,
               accepted_kg numeric, note text)
      )
      SELECT p.name, p.bags,
             count(s.bag) AS witness_count,
             COALESCE(sum(COALESCE(o.accepted_kg, w.accepted_kg)), 0) AS sample_kg
      FROM coast_segments p
      JOIN coast_samples s ON s.segment = p.code
      JOIN coast_witness w ON w.segment = s.segment AND w.bag = s.bag
      LEFT JOIN override o ON o.segment = s.segment AND o.bag = s.bag
      WHERE p.round = %s
      GROUP BY p.code, p.name, p.bags
      ORDER BY p.code
    """, (Jsonb(correction["evidence"]), code)).fetchall()

def apply_correction(cx, code, correction_id):
    round_state(cx, code, True)
    correction = cx.execute(
        "SELECT * FROM coast_haul_correction WHERE round=%s AND id=%s FOR UPDATE",
        (code, correction_id),
    ).fetchone()
    if correction is None:
        raise HTTPException(404, "没有这条更正申请")
    if correction["status"] == "succeeded":
        return {"round": code, "stale": False, "message": "该更正已出单"}
    # 串行化同一轮次的重算：两个更正任务并发时，后者在此等待，
    # 拿到锁后版本检查即会判定为 stale，配合 (round,version) 唯一索引兜底。
    cx.execute("LOCK TABLE coast_rounds IN SHARE ROW EXCLUSIVE MODE")
    round_row = cx.execute(
        "SELECT current_version FROM coast_rounds WHERE code=%s FOR UPDATE",
        (code,),
    ).fetchone()
    # 乐观并发：两人同时更正同一版，先完成的接替旧单，其余要求重新核对。
    if round_row["current_version"] != correction["base_version"]:
        cx.execute(
            "UPDATE coast_haul_correction SET status='stale' WHERE id=%s",
            (correction_id,),
        )
        return {"round": code, "stale": True,
                "message": "期间已有其他更正接替旧单，请重新核对后再发起更正"}

    basis = _corrected_basis(cx, code, correction)
    rows = _recalc_rows(cx, code, correction)
    net, parts = estimate(rows)
    new_version = correction["base_version"] + 1
    cx.execute("""
      INSERT INTO coast_haul(round,version,estimated_kg,pieces,basis,correction_id)
      VALUES (%s,%s,%s,%s,%s,%s)
    """, (code, new_version, net, Jsonb(parts), Jsonb(basis), correction_id))
    cx.execute(
        "UPDATE coast_rounds SET current_version=%s WHERE code=%s",
        (new_version, code),
    )
    cx.execute(
        "UPDATE coast_haul_correction SET status='succeeded' WHERE id=%s",
        (correction_id,),
    )
    return {"round": code, "version": new_version, "estimated_kg": float(net),
            "pieces": parts, "stale": False}

def _correction_history(cx, code):
    corrections = cx.execute(
        "SELECT * FROM coast_haul_correction WHERE round=%s ORDER BY id",
        (code,),
    ).fetchall()
    for correction in corrections:
        correction["job"] = cx.execute("""
          SELECT id,status,error FROM app_jobs
          WHERE kind=%s AND (payload->>'correction_id')::bigint=%s
          ORDER BY id DESC LIMIT 1
        """, (CORRECTION_KIND, correction["id"])).fetchone()
    return corrections

def view(cx, code):
    cycle = round_state(cx, code)
    current = cx.execute("""
      SELECT * FROM coast_haul
      WHERE round=%s AND version=(SELECT current_version FROM coast_rounds WHERE code=%s)
    """, (code, code)).fetchone()
    versions = cx.execute(
        "SELECT round,version,estimated_kg,issued_at,correction_id,basis "
        "FROM coast_haul WHERE round=%s ORDER BY version",
        (code,),
    ).fetchall()
    return {
        "status": cycle["status"],
        "current_version": cycle["current_version"],
        "report": current,
        "coverage": stratified_rows(cx, code),
        "versions": versions,
        "corrections": _correction_history(cx, code),
    }
