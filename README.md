# 潮线称重 · 净滩样袋抽查

用少量见证样袋推算三段海滩总重量，按段输出可交接的估计和证据。

**模拟客户**　南湾净滩小队，5 位段长和两个交接站

**现有流程**　过去每个段长用即时通信上报。重袋容易被优先抽查、见证条丢失、总重量没有对应总袋数出处。

**业务交接**　段长点袋后抽样，见证员核对复称，后台形成区段估计，再转给下游清运班组。

## 一日工作剧本

1. 06:30 接收 S-02 沙线登记，东口 20 袋、中心 40 袋、西口 10 袋。
2. 06:50 每段登记预先抽中的两袋净重。记录首称与复称差。
3. 07:00 东口第 4 袋首称 4.0 kg，复称 4.9 kg，触发分歧。
4. 07:15 见证员核验秤单，确定接受复称后提交。
5. 07:25 每段至少两袋见证样后，复核员锁定本轮抽查。
6. 07:30 推算东口及另外两段的重量，输出带样本量的清运交接。

## 算法和演示边界

以区段为分层。每段净重比率为见证通过样袋的总净重 / 见证通过样袋数。按每段登记总袋数放大再加总。首称与复称差绝对值超过 0.5 kg 需复核员明确选择证据并说明。

演示以公斤计量。抽袋的随机化由现场完成。系统校验样袋序号不得超过该段已登记袋数。

## 快速启动

```sh
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

- 前端浏览器地址为 `http://127.0.0.1:18452`。
- FastAPI 文档地址为 `http://127.0.0.1:19452/docs`。
- PostgreSQL 本地端口为 `17952`。后端与后台 worker 共用数据库事务和 Redis 健康探测。
- 开发 HTML、CSS、ES modules 后运行 `docker compose up -d --build frontend`。Python 代码修改后运行 `docker compose up -d --build backend worker`。
- `SEED_DEMO` 控制自动填充。可改三项宿主端口、`DEMO_PASSWORD`、`JWT_SECRET`、`POSTGRES_PASSWORD`。持久卷保存业务数据和队列状态。停机并保留数据使用 `docker compose down`。
- 技术栈为 Python 3.11、FastAPI、PostgreSQL 16、Redis 7、Nginx 与原生浏览器 JS。后端业务模块、SQL 迁移都在 `backend/`。界面和交互在 `frontend/`。

| 账号 | 密码 | 典型权限 |
|---|---|---|
| operator@demo.local | Demo2026! | 登记样袋双称 |
| reviewer@demo.local | Demo2026! | 见证称重并锁定清运交接 |
| viewer@demo.local | Demo2026! | 查阅记录和经计算的指标 |

共享角色和任务状态枚举分别位于 `backend/core.py` 的 `ROLES`、`JOB_STATES` 和 `frontend/base.js` 的 `roles`、`jobStates`。数据库检查约束与服务状态以相应 SQL 和模块为准。

许可证见 LICENSE。
