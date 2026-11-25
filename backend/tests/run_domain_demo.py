"""纯标准库集成演练：用内存假库跑真实领域模块，验证清运单更正全流程。

运行：python3 tests/run_domain_demo.py
不依赖 fastapi/psycopg/redis/pydantic，只验证 backend 下的业务逻辑与 SQL 调用契约。
"""
import importlib
import sys
import types
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ---- 外部依赖桩件 -------------------------------------------------------
def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class _HttpException(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _Jsonb:
    def __init__(self, obj, dumps=None):
        self.obj = obj


fastapi = _stub("fastapi", HTTPException=_HttpException,
                APIRouter=lambda **kw: types.SimpleNamespace(
    include_router=lambda *a, **k: None, get=lambda *a, **k: (lambda f: f),
    post=lambda *a, **k: (lambda f: f)))
_stub("fastapi.security", HTTPAuthorizationCredentials=object, HTTPBearer=lambda **kw: None)
_stub("fastapi.encoders", jsonable_encoder=lambda x: x)
psycopg = _stub("psycopg", IntegrityError=type("IntegrityError", (Exception,), {}))
_stub("psycopg.rows", dict_row=None)
_stub("psycopg.types", )
_stub("psycopg.types.json", Jsonb=_Jsonb)
_stub("redis", Redis=types.SimpleNamespace(from_url=lambda *a, **k: None))
jwt = _stub("jwt")
jwt.encode = lambda *a, **k: "token"
jwt.decode = lambda *a, **k: {}
jwt.InvalidTokenError = type("InvalidTokenError", (Exception,), {})
pydantic = _stub("pydantic")


class _BaseModel:
    def __init__(self, **kwargs):
        annotations = getattr(type(self), "__annotations__", {})
        for key in annotations:
            setattr(self, key, kwargs.get(key))
        for key, value in kwargs.items():
            if key not in annotations:
                setattr(self, key, value)


pydantic.BaseModel = _BaseModel
pydantic.Field = lambda *a, **k: None
pydantic.StringConstraints = lambda **k: str

# core 的真实模块只用到 enqueue / db / require，这里换成轻量实现。
core = _stub("core", db=None, require=lambda *roles: (lambda *a, **k: {"email": "reviewer@demo.local", "role": "reviewer"}),
             enqueue=None)


def _enqueue(cx, kind, payload, available_at=None):
    job = {"id": cx.next_id("job"), "kind": kind, "payload": payload,
           "status": "queued", "error": None, "result": None}
    cx.tables["jobs"].append(job)
    return job["id"]


core.enqueue = _enqueue


# ---- 内存数据库 ---------------------------------------------------------
class FakeCx:
    def __init__(self):
        self.tables = {
            "rounds": [], "segments": [], "samples": [], "witness": [],
            "hauls": [], "corrections": [], "jobs": [],
        }
        self._seq = {}

    def next_id(self, kind):
        self._seq[kind] = self._seq.get(kind, 0) + 1
        return self._seq[kind]

    def transaction(self):
        outer = self

        class _Tx:
            def __enter__(self):
                return outer

            def __exit__(self, *exc):
                return False

        return _Tx()

    def execute(self, sql, params=()):
        cursor = Cursor(self, _squash(sql), params)
        # 真实 psycopg 的 execute 立即生效；写操作/锁不取结果，这里同步执行。
        if cursor.sql.startswith(("insert", "update", "delete", "lock")):
            cursor._run()
        return cursor


def _squash(sql):
    return " ".join(sql.replace("(%s::jsonb)", "%s").split()).lower()


class Cursor:
    def __init__(self, cx, sql, params):
        self.cx = cx
        self.sql = sql
        self.params = list(params)
        self._rows = None

    def fetchone(self):
        rows = self._run()
        return rows[0] if rows else None

    def fetchall(self):
        return self._run()

    def _run(self):
        if self._rows is not None:
            return self._rows
        self._rows = dispatch(self.cx, self.sql, self.params)
        return self._rows


def dispatch(cx, sql, p):
    t = cx.tables

    if sql.startswith("lock table"):
        return []

    if "insert into coast_rounds" in sql:
        if any(r["code"] == p[0] for r in t["rounds"]):
            return []
        t["rounds"].append({"code": p[0], "shore": p[1],
                            "status": "open", "current_version": 1})
        return [{"code": p[0]}]

    if sql.startswith("select * from coast_rounds where code="):
        rows = [r for r in t["rounds"] if r["code"] == p[0]]
        return rows

    if sql.startswith("select * from coast_segments where code="):
        return [dict(s) for s in t["segments"] if s["code"] == p[0]]

    if "insert into coast_segments values" in sql:
        t["segments"].append({"code": p[0], "round": p[1], "name": p[2], "bags": p[3]})
        return []

    if "insert into coast_samples values" in sql:
        t["samples"].append({"segment": p[0], "bag": p[1],
                             "first_kg": Decimal(str(p[2])),
                             "second_kg": Decimal(str(p[3])), "status": p[4]})
        return []

    if "insert into coast_witness values" in sql:
        row = {"segment": p[0], "bag": p[1], "accepted_kg": p[2],
               "source": p[3], "witness": p[4], "note": p[5]}
        t["witness"].append(row)
        return [row]

    if "update coast_samples set status='accepted'" in sql:
        return []

    if sql.startswith("select s.*, p.round, w.accepted_kg as witnessed_kg"):
        seg, bag = p
        sample = next((s for s in t["samples"] if s["segment"] == seg and s["bag"] == bag), None)
        if not sample:
            return []
        segment = next(x for x in t["segments"] if x["code"] == seg)
        wit = next((w for w in t["witness"] if w["segment"] == seg and w["bag"] == bag), None)
        return [{"segment": seg, "bag": bag, "first_kg": sample["first_kg"],
                 "second_kg": sample["second_kg"], "status": sample["status"],
                 "round": segment["round"], "witnessed_kg": wit["accepted_kg"] if wit else None}]

    if "select * from coast_samples where segment=" in sql and "for update" in sql:
        seg, bag = p
        return [s for s in t["samples"] if s["segment"] == seg and s["bag"] == bag]

    if "from coast_witness w join coast_segments p on p.code = w.segment" in sql:
        seg_codes = {s["code"] for s in t["segments"] if s["round"] == p[0]}
        return [dict(w) for w in t["witness"] if w["segment"] in seg_codes]

    if "from coast_segments p left join coast_witness w" in sql:
        return _stratified(cx, p[0])

    if sql.startswith("with override as"):
        return _recalc(cx, p[1], p[0].obj)

    if sql.startswith("update coast_rounds set status='locked'"):
        _round(cx, p[0])["status"] = "locked"
        return []

    if sql.startswith("update coast_rounds set status='issued'"):
        r = _round(cx, p[0]); r["status"] = "issued"; r["current_version"] = 1
        return []

    if sql.startswith("update coast_rounds set current_version="):
        _round(cx, p[1])["current_version"] = p[0]
        return []

    if "insert into coast_haul" in sql and len(p) == 6:
        t["hauls"].append({"round": p[0], "version": p[1], "estimated_kg": p[2],
                           "pieces": p[3].obj, "basis": p[4].obj,
                           "correction_id": p[5], "issued_at": "now"})
        return []

    if "insert into coast_haul" in sql and len(p) == 4:
        t["hauls"].append({"round": p[0], "version": 1, "estimated_kg": p[1],
                           "pieces": p[2].obj, "basis": p[3].obj,
                           "correction_id": None, "issued_at": "now"})
        return []

    if sql.startswith("select * from coast_haul where round=") and "for update" in sql:
        code = p[0]
        current = _round(cx, code)["current_version"]
        return [h for h in t["hauls"] if h["round"] == code and h["version"] == current]

    if sql.startswith("select * from coast_haul where round="):
        code = p[0]
        current = _round(cx, code)["current_version"]
        return [h for h in t["hauls"] if h["round"] == code and h["version"] == current]

    if "from coast_haul where round=" in sql and "order by version" in sql:
        return [dict(h) for h in t["hauls"] if h["round"] == p[0]]

    if "insert into coast_haul_correction" in sql:
        code = p[0]
        reason, evidence, who = p[2], p[3], p[4]
        base = _round(cx, code)["current_version"]
        row = {"id": cx.next_id("correction"), "round": code, "base_version": base,
               "reason": reason, "evidence": evidence.obj, "created_by": who,
               "created_at": "now", "status": "queued"}
        t["corrections"].append(row)
        return [dict(row)]

    if "select * from coast_haul_correction where round=" in sql and len(p) == 2:
        code, cid = p
        return [dict(c) for c in t["corrections"] if c["round"] == code and c["id"] == cid]

    if "from coast_haul_correction where round=" in sql:
        return [dict(c) for c in t["corrections"] if c["round"] == p[0]]

    if "from coast_haul_correction" in sql and len(p) == 1:
        cid = p[0]
        return [dict(c) for c in t["corrections"] if c["id"] == cid]

    if "from coast_haul_correction where round=" in sql:
        return [dict(c) for c in t["corrections"] if c["round"] == p[0]]

    if "update coast_haul_correction set status='stale'" in sql:
        c = next(c for c in t["corrections"] if c["id"] == p[0]); c["status"] = "stale"
        return []

    if "update coast_haul_correction set status='succeeded'" in sql:
        c = next(c for c in t["corrections"] if c["id"] == p[0]); c["status"] = "succeeded"
        return []

    if "select current_version from coast_rounds where code=" in sql:
        return [{"current_version": _round(cx, p[0])["current_version"]}]

    if "from app_jobs where kind=" in sql and "order by id desc limit 1" in sql:
        kind = p[0]
        if len(p) == 3:
            code, cid = p[1], p[2]
            rows = [j for j in t["jobs"] if j["kind"] == kind
                    and j["payload"]["round"] == code
                    and j["payload"]["correction_id"] == cid]
        else:
            cid = p[1]
            rows = [j for j in t["jobs"] if j["kind"] == kind
                    and j["payload"]["correction_id"] == cid]
        rows.sort(key=lambda j: j["id"], reverse=True)
        return [{"id": rows[0]["id"], "status": rows[0]["status"],
                 "error": rows[0]["error"]}] if rows else []

    if "insert into app_jobs" in sql:
        job = {"id": cx.next_id("job"), "kind": p[0], "payload": p[1].obj,
               "status": "queued", "error": None, "result": None}
        t["jobs"].append(job)
        return [{"id": job["id"]}]

    raise AssertionError(f"未实现的 SQL: {sql}")


def _round(cx, code):
    return next(r for r in cx.tables["rounds"] if r["code"] == code)


def _stratified(cx, code):
    out = []
    for seg in [s for s in cx.tables["segments"] if s["round"] == code]:
        ws = [w for w in cx.tables["witness"] if w["segment"] == seg["code"]]
        out.append({"name": seg["name"], "bags": seg["bags"],
                    "witness_count": len(ws),
                    "sample_kg": sum((w["accepted_kg"] for w in ws), Decimal("0"))})
    return out


def _recalc(cx, code, evidence):
    override = {(e["segment"], e["bag"]): Decimal(str(e["accepted_kg"])) for e in evidence}
    out = []
    for seg in [s for s in cx.tables["segments"] if s["round"] == code]:
        total = Decimal("0"); count = 0
        for w in [w for w in cx.tables["witness"] if w["segment"] == seg["code"]]:
            total += override.get((w["segment"], w["bag"]), w["accepted_kg"]); count += 1
        out.append({"name": seg["name"], "bags": seg["bags"],
                    "witness_count": count, "sample_kg": total})
    return out


# ---- 真实领域模块 -------------------------------------------------------
rr = importlib.import_module("round_registry")
discrepancy = importlib.import_module("discrepancy")
witness_review = importlib.import_module("witness_review")
ratio = importlib.import_module("ratio")
haul_correction = importlib.import_module("haul_correction")
haul_dispatch = importlib.import_module("haul_dispatch")
haul_worker = importlib.import_module("haul_worker")
correction_input = importlib.import_module("correction_input")

Choice = correction_input.CorrectionChoice
Request = correction_input.CorrectionRequest


def build_round(cx, code="S-99"):
    cx.tables["rounds"].append({"code": code, "shore": "演练岸段",
                                "status": "open", "current_version": 1})
    data = [("E", "东口", 20, [(1, "4.10", "4.20"), (4, "4.00", "4.90")]),
            ("M", "中心", 40, [(3, "2.10", "2.10"), (6, "2.80", "2.90")]),
            ("W", "西口", 10, [(2, "1.40", "1.40"), (8, "1.55", "1.60")])]
    for seg, name, bags, weights in data:
        sc = f"{code}-{seg}"
        cx.tables["segments"].append({"code": sc, "round": code, "name": name, "bags": bags})
        for bag, first, second in weights:
            f, s = Decimal(first), Decimal(second)
            status = discrepancy.weigh_status(f, s)
            cx.tables["samples"].append({"segment": sc, "bag": bag, "first_kg": f,
                                         "second_kg": s, "status": status})
            witness_review.accept(cx, sc, bag, "second", "复核秤纸编号一致", "reviewer@demo.local")


def run_job(cx, job_id):
    job = next(j for j in cx.tables["jobs"] if j["id"] == job_id)
    job["status"] = "running"
    result = haul_worker.run(cx, job["kind"], job["payload"])
    job["status"] = "done"; job["result"] = result
    return result


PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ✓ {name}")
    else:
        FAIL += 1; print(f"  ✗ {name} {detail}")


def expect_conflict(name, fn):
    try:
        fn(); check(name, False, "(未拒绝)")
    except _HttpException as exc:
        check(name, exc.status_code in (409, 404), f"status={exc.status_code} {exc.detail}")


def main():
    print("场景一：正常更正，旧单保留、新版接替、取证固定")
    cx = FakeCx(); build_round(cx)
    haul_dispatch.prepare(cx, "S-99")
    run_job(cx, cx.tables["jobs"][-1]["id"])
    v1 = next(h for h in cx.tables["hauls"] if h["version"] == 1)
    check("首版总重 206.00kg", v1["estimated_kg"] == Decimal("206.00"), str(v1["estimated_kg"]))
    check("首版固定 6 条取证依据", len(v1["basis"]) == 6)

    body = Request(reason="见证员认错秤单，核对原始秤纸后改用首称",
                   choices=[Choice(segment="S-99-E", bag=4, source="first",
                                   note="原始秤纸显示首称 4.00kg 为准")])
    opened = haul_correction.open_correction(cx, "S-99", body, "reviewer@demo.local")
    check("发起更正返回任务", opened["job_id"] > 0 and opened["base_version"] == 1)
    result = run_job(cx, opened["job_id"])
    check("重算生成 v2", result["version"] == 2 and result["stale"] is False)
    check("v2 总重 197.00kg", result["estimated_kg"] == 197.00, str(result["estimated_kg"]))
    check("轮次当前版本切到 v2", cx.tables["rounds"][0]["current_version"] == 2)
    check("旧版 v1 仍保留可查", len(cx.tables["hauls"]) == 2 and
          next(h for h in cx.tables["hauls"] if h["version"] == 1)["estimated_kg"] == Decimal("206.00"))
    v2 = next(h for h in cx.tables["hauls"] if h["version"] == 2)
    fixed = next(b for b in v2["basis"] if b["segment"] == "S-99-E" and b["bag"] == 4)
    check("v2 取证固定为首称 4.00", fixed["accepted_kg"] == 4.0 and fixed["source"] == "first")
    view = haul_correction.view(cx, "S-99")
    check("页面默认取当前 v2", view["report"]["version"] == 2)
    check("页面返回两个版本", [h["version"] for h in view["versions"]] == [1, 2])
    check("更正记录标记成功", view["corrections"][0]["status"] == "succeeded")

    print("场景二：两人同时提交同一版更正，先成者接替，其余提示重新核对")
    cx = FakeCx(); build_round(cx)
    haul_dispatch.prepare(cx, "S-99"); run_job(cx, cx.tables["jobs"][-1]["id"])
    mk = lambda src: Request(reason="并行更正，依据原始秤纸重新核对",
                             choices=[Choice(segment="S-99-E", bag=4, source=src, note="并行核对")])
    a = haul_correction.open_correction(cx, "S-99", mk("first"), "r-a")
    b = haul_correction.open_correction(cx, "S-99", mk("second"), "r-b")
    check("两份更正都基于 v1", a["base_version"] == b["base_version"] == 1)
    ra = run_job(cx, a["job_id"]); rb = run_job(cx, b["job_id"])
    check("先完成者出 v2", ra["version"] == 2 and ra["stale"] is False)
    check("后者判定 stale 并提示重新核对", rb["stale"] is True and "重新核对" in rb["message"])
    check("只新增一张清运单", len(cx.tables["hauls"]) == 2)
    check("后者更正单标记 stale",
          next(c for c in cx.tables["corrections"] if c["id"] == b["correction_id"])["status"] == "stale")
    expect_conflict("stale 更正不能重试", lambda: haul_correction.retry_correction(cx, "S-99", b["correction_id"]))

    print("场景二（续）：锁内交错，后到事务拿锁后判定 stale 且不重复出单")
    cx = FakeCx(); build_round(cx)
    haul_dispatch.prepare(cx, "S-99"); run_job(cx, cx.tables["jobs"][-1]["id"])
    x = haul_correction.open_correction(cx, "S-99", mk("first"), "r-x")
    y = haul_correction.open_correction(cx, "S-99", mk("second"), "r-y")
    real_dispatch = dispatch
    state = {"holder": None}

    def serializing(c, sql, params):
        # 模拟 LOCK TABLE 串行：B 等锁期间，A 已把版本推进到 2，B 拿锁后才继续。
        if sql.startswith("lock table"):
            if state["holder"] is None:
                state["holder"] = "x"
            elif state["holder"] == "x":
                # B 获取锁前，A 的事务已提交并把当前版本推进。
                c.tables["rounds"][0]["current_version"] = 2
                state["holder"] = "b"
            return []
        return real_dispatch(c, sql, params)

    import run_domain_demo as self_module
    self_module.dispatch = serializing
    try:
        rx = run_job(cx, x["job_id"])
        ry = run_job(cx, y["job_id"])
    finally:
        self_module.dispatch = real_dispatch
    check("锁内先到者正常出 v2", rx.get("version") == 2)
    check("锁内后到者判定 stale", ry["stale"] is True and "重新核对" in ry["message"])
    check("锁保护下仍只有一张新版单", len(cx.tables["hauls"]) == 2)
    check("后到更正单落为 stale",
          next(c for c in cx.tables["corrections"] if c["id"] == y["correction_id"])["status"] == "stale")

    print("场景三：重算失败照常用旧单，重试沿用同一取证且不重复出单")
    cx = FakeCx(); build_round(cx)
    haul_dispatch.prepare(cx, "S-99"); run_job(cx, cx.tables["jobs"][-1]["id"])
    opened = haul_correction.open_correction(
        cx, "S-99",
        Request(reason="重算失败演练，取证已固定",
                choices=[Choice(segment="S-99-E", bag=4, source="first", note="固定取证")]),
        "reviewer@demo.local")
    cid = opened["correction_id"]
    # 模拟 worker 重算时写新版清运单失败：抛错并整体回滚，旧版与更正单保持原状。
    job = next(j for j in cx.tables["jobs"] if j["id"] == opened["job_id"])
    job["status"] = "running"
    real_execute = cx.execute
    class RecalcBoom(RuntimeError):
        pass

    def flaky(sql, params=()):
        if "insert into coast_haul" in _squash(sql):
            raise RecalcBoom("后台计算失败，请核对输入后重试")
        return real_execute(sql, params)

    cx.execute = flaky
    try:
        haul_worker.run(cx, job["kind"], job["payload"])
        raised = False
    except RecalcBoom:
        raised = True
    cx.execute = real_execute
    check("重算确实抛出失败", raised)
    job["status"] = "failed"; job["error"] = "后台计算失败，请核对输入后重试"
    check("失败后仍只有 v1", len(cx.tables["hauls"]) == 1 and
          cx.tables["rounds"][0]["current_version"] == 1)
    check("失败后更正单仍是 queued",
          next(c for c in cx.tables["corrections"] if c["id"] == cid)["status"] == "queued")
    retried = haul_correction.retry_correction(cx, "S-99", cid)
    check("重试产生新任务但复用同一更正单", retried["correction_id"] == cid and
          len(cx.tables["corrections"]) == 1)
    result = run_job(cx, retried["job_id"])
    check("重试成功出 v2", result["version"] == 2)
    check("全程只生成两张清运单", len(cx.tables["hauls"]) == 2)
    check("同一取证被沿用",
          next(c for c in cx.tables["corrections"] if c["id"] == cid)["evidence"][0]["source"] == "first")

    print("场景四：守卫与边界")
    cx = FakeCx(); build_round(cx)
    expect_conflict("未签发不能发起更正", lambda: haul_correction.open_correction(
        cx, "S-99", Request(reason="还没出单", choices=[Choice(segment="S-99-E", bag=1, source="first")]), "r"))
    haul_dispatch.prepare(cx, "S-99"); run_job(cx, cx.tables["jobs"][-1]["id"])
    expect_conflict("未见证样袋不能更正", lambda: haul_correction.open_correction(
        cx, "S-99", Request(reason="选了未出单样袋", choices=[Choice(segment="S-99-E", bag=9, source="first")]), "r"))
    expect_conflict("不属于本轮的样袋被拒绝", lambda: haul_correction.open_correction(
        cx, "S-99", Request(reason="别轮样袋", choices=[Choice(segment="S-00-E", bag=1, source="first")]), "r"))
    expect_conflict("同一样袋重复登记被拒绝", lambda: haul_correction.open_correction(
        cx, "S-99", Request(reason="重复样袋校验", choices=[
            Choice(segment="S-99-E", bag=4, source="first"),
            Choice(segment="S-99-E", bag=4, source="second")]), "r"))
    first = haul_correction.open_correction(
        cx, "S-99", Request(reason="连续更正第一单", choices=[Choice(segment="S-99-E", bag=4, source="first", note="n")]), "r")
    run_job(cx, first["job_id"])
    expect_conflict("已成功更正无需重试", lambda: haul_correction.retry_correction(cx, "S-99", first["correction_id"]))
    second = haul_correction.open_correction(
        cx, "S-99", Request(reason="在 v2 基础上继续更正", choices=[Choice(segment="S-99-M", bag=6, source="first", note="n")]), "r")
    check("第二次更正基于 v2", second["base_version"] == 2)
    run_job(cx, second["job_id"])
    check("连续更正推进到 v3", cx.tables["rounds"][0]["current_version"] == 3 and
          len(cx.tables["hauls"]) == 3)
    check("v1 历史重量始终可查",
          next(h for h in cx.tables["hauls"] if h["version"] == 1)["estimated_kg"] == Decimal("206.00"))

    print(f"\n结果：通过 {PASS} 项，失败 {FAIL} 项")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
