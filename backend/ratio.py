from decimal import Decimal,ROUND_HALF_UP

def half_up(value):
    return value.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)

def estimate(rows):
    total=Decimal(0)
    pieces=[]
    for row in rows:
        net=row["sample_kg"]*row["bags"]/row["witness_count"]
        total+=net
        pieces.append({"segment":row["name"],"bags":row["bags"],"witness_count":row["witness_count"],
                      "sample_kg":float(row["sample_kg"]),"estimated_kg":float(half_up(net))})
    return half_up(total),pieces

def stratified_rows(cx,code):
    return cx.execute("""
      SELECT p.name,p.bags,count(w.bag) AS witness_count,coalesce(sum(w.accepted_kg),0) AS sample_kg
      FROM coast_segments p LEFT JOIN coast_witness w ON w.segment=p.code
      WHERE p.round=%s GROUP BY p.code,p.name,p.bags ORDER BY p.code
    """,(code,)).fetchall()
