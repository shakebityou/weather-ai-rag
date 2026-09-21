"""SQL Server 数据访问层：文档持久化存储，自动建库建表、空库灌入示例数据。"""
import pyodbc

from app.config import settings

SAMPLE_DOCS = [
    "员工年假规则：入职满一年可享5天带薪年假，此后每满一年增加1天，上限15天。",
    "报销流程：在OA系统提交报销单，附上发票照片，部门主管审批后3个工作日内到账。",
    "服务器部署规范：所有服务必须容器化部署，禁止在宿主机直接运行业务进程。",
    "请假制度：病假需提供医院证明，事假提前3天在OA申请。",
]

DDL = """
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='documents' AND xtype='U')
CREATE TABLE documents (
    id INT IDENTITY(1,1) PRIMARY KEY,
    content NVARCHAR(MAX) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def _conn_str(with_db: bool = True) -> str:
    parts = [
        f"DRIVER={{{settings.mssql_driver}}};",
        f"SERVER={settings.mssql_server};",
    ]
    if with_db:
        parts.append(f"DATABASE={settings.mssql_db};")
    # 用户名密码为空 → Windows 身份验证
    if settings.mssql_user:
        parts.append(f"UID={settings.mssql_user};")
        parts.append(f"PWD={settings.mssql_password};")
    else:
        parts.append("Trusted_Connection=yes;")
    return "".join(parts)


def _connect(with_db: bool = True):
    return pyodbc.connect(_conn_str(with_db), timeout=10)


def init_db():
    """建库建表，空库时灌入示例文档。数据库不可用时静默跳过。"""
    try:
        # 1. 连 master 建库
        conn = _connect(with_db=False)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name='{settings.mssql_db}') "
                f"CREATE DATABASE [{settings.mssql_db}];"
            )
        conn.close()

        # 2. 连目标库建表 + 灌数据
        conn = _connect()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute("SELECT COUNT(*) FROM documents")
            if cur.fetchone()[0] == 0:
                cur.fast_executemany = True
                cur.executemany(
                    "INSERT INTO documents (content) VALUES (?)",
                    [(d,) for d in SAMPLE_DOCS])
        conn.close()
    except Exception as e:
        print(f"[db] SQL Server 初始化跳过（将使用内置文档）：{e}")


def fetch_documents() -> list[str]:
    """从 SQL Server 拉取全部文档内容，失败返回空列表。"""
    try:
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute("SELECT content FROM documents ORDER BY id")
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        print(f"[db] SQL Server 读取失败：{e}")
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass
