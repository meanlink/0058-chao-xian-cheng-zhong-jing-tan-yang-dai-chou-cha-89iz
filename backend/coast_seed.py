from discrepancy import weigh_status
from decimal import Decimal
from haul_dispatch import issue
from witness_review import accept

def seed(cx):
    for key,name in [('S-02','南湾二号净滩轮次'),('S-01','南湾十月清运回执')]:
        if not cx.execute("INSERT INTO coast_rounds(code,shore) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING code",(key,name)).fetchone():
            continue
        for segment, label, bags, weights in [
          ('E','东口',20,[(1,'4.10','4.20'),(4,'4.00','4.90')]),
          ('M','中心',40,[(3,'2.10','2.10'),(6,'2.80','2.90')]),
          ('W','西口',10,[(2,'1.40','1.40'),(8,'1.55','1.60')]),
        ]:
            code=key+'-'+segment
            cx.execute("INSERT INTO coast_segments VALUES (%s,%s,%s,%s)",(code,key,label,bags))
            for bag,first,second in weights:
                status=weigh_status(Decimal(first),Decimal(second))
                cx.execute("INSERT INTO coast_samples VALUES (%s,%s,%s,%s,%s)",(code,bag,first,second,status))
                if status!="disputed" or key=='S-01':
                    accept(cx,code,bag,'second','复核秤纸编号一致','reviewer@demo.local')
        if key=='S-01':
            issue(cx,key)
