from fastapi import HTTPException
from discrepancy import weigh_status
from round_registry import segment

def record(cx,code,body):
    row=segment(cx,code)
    if body.bag>row["bags"]:
        raise HTTPException(409,"袋号超过该段登记的总袋数")
    state=weigh_status(body.first_kg,body.second_kg)
    return cx.execute("INSERT INTO coast_samples VALUES (%s,%s,%s,%s,%s) RETURNING *",
                     (code,body.bag,body.first_kg,body.second_kg,state)).fetchone()

def sample_rows(cx,code):
    return cx.execute("""
      SELECT s.*,w.witness,w.accepted_kg,w.source,w.note,p.name FROM coast_samples s
      JOIN coast_segments p ON p.code=s.segment
      LEFT JOIN coast_witness w ON w.segment=s.segment AND w.bag=s.bag
      WHERE p.round=%s ORDER BY s.segment,s.bag
    """,(code,)).fetchall()
