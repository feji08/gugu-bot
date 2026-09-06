# database/__init__.py
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean, func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 使用绝对路径
db_path = Path(__file__).parent / "gugu.db"
engine = create_engine(f'sqlite:///{db_path}', echo=False)

# 创建一个基类
Base = declarative_base()

# ---------------------------------------------------------------------------
# 作业类型规格表 = 唯一真相源。
#   (名字, 是否上架, 分组)
#   - 顺序即菜单顺序（菜单按本表位置排序，不依赖 DB id 数值）。
#   - 上下架只改这里：启动时会把 DB 里的 active 同步成本表的值，直接改库会在重启时被覆盖。
#   - 名字是与 DB 行匹配的键，改名 = 新类型；历史记录靠 assignment_id 指向老行不受影响。
#   - 分组不进库，只在代码里用（/个人总结 的「综合６选３」按 COMPOSITE_NAMES 统计）。
# ---------------------------------------------------------------------------
ASSIGNMENT_SPEC = [
    ("输出练笔", True, None),
    ("扒文扒榜", True, None),
    ("节奏作业", False, None),  # 2026-09 下架，历史记录保留
    ("摘抄练习", True, None),
    ("其他练习", True, None),
    ("文案作业", True, "综合"),
    ("人设发散", True, "综合"),
    ("人设行为", True, "综合"),
    ("萌梗作业", True, "综合"),
    ("灰姑娘结构", True, "综合"),
    ("视频名场面", True, "综合"),
]
ASSIGNMENT_ORDER = [name for name, _, _ in ASSIGNMENT_SPEC]
COMPOSITE_NAMES = {name for name, _, group in ASSIGNMENT_SPEC if group == "综合"}
COMPOSITE_REQUIRED = 3  # 综合６选３：一周内做满 3 个不重样的
LEAVE_ID = 100          # 「请假」占位作业，固定 id，不进菜单

# 周总结表格图 / xlsx 的单元格按 4 字名调的宽度，5 字名在这里缩写；库里名字不动
REPORT_SHORT = {"灰姑娘结构": "灰姑娘", "视频名场面": "名场面"}


def report_display_name(name) -> str:
    return REPORT_SHORT.get(str(name), str(name))


def assignment_sort_key(assignment) -> int:
    """按规格表位置排菜单；不在规格表里的（老库残留）排最后。"""
    try:
        return ASSIGNMENT_ORDER.index(assignment.name)
    except ValueError:
        return len(ASSIGNMENT_ORDER)

# 定义用户模型
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, nullable=False)
    nickname = Column(String, unique=True, nullable=False)
    cute_name = Column(String, unique=True, nullable=True)
    group_level = Column(Integer, default=0)

# 定义作业类型模型
class Assignment(Base):
    __tablename__ = 'assignments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # 作业类型名称
    active = Column(Boolean, nullable=False, default=True, server_default="1")  # 下架=False，历史记录仍可指向它

# 定义打卡记录模型
class CheckInRecord(Base):
    __tablename__ = 'checkin_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)  # 用户 ID
    assignment_id = Column(Integer, ForeignKey('assignments.id'), nullable=False)  # 作业类型 ID
    checkin_time = Column(DateTime, nullable=False)  # 打卡时间

    # 定义与作业类型表的关系
    assignment = relationship("Assignment", back_populates="checkin_records")

# 反向关系
Assignment.checkin_records = relationship("CheckInRecord", order_by=CheckInRecord.id, back_populates="assignment")

# 早鸟卡记录表
class EarlyBirdRecord(Base):
    __tablename__ = 'early_bird_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey('users.user_id'), nullable=False)  # 用户 ID
    count = Column(Integer, default=0)  # 早鸟卡数量

# 请假记录表
class LeaveRecord(Base):
    __tablename__ = 'leave_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey('users.user_id'), nullable=False)  # 用户 ID
    leave_period_start = Column(DateTime, nullable=False)  # 本周起始时间
    leave_count = Column(Integer, default=0)  # 请假次数

class RewardRecord(Base):
    __tablename__ = 'reward_records'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey('users.user_id'), nullable=False)
    count = Column(Integer, default=0)

# 创建所有表（如果表不存在）
Base.metadata.create_all(engine)

# 启动自迁移：老库补 assignments.active 列。
# SQLite 加列不重建表、老行回填 1，打卡记录不受影响。
# PRAGMA 检查与 ALTER 不是原子的：两个进程同时启动时第二个会撞 duplicate column，当作已迁移忽略。
with engine.begin() as conn:
    cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(assignments)")}
    if "active" not in cols:
        try:
            conn.exec_driver_sql("ALTER TABLE assignments ADD COLUMN active BOOLEAN NOT NULL DEFAULT 1")
        except OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise

# 创建数据库会话
Session = sessionmaker(bind=engine)
session = Session()

# 按规格表同步作业类型：缺的插入（id 由 SQLite 分配，任何逻辑都不依赖其数值）、上下架状态以规格表为准。
# name 无唯一约束，按 trim 后的名字匹配；出现重名行时不再插入、只记日志，留给人工清理。
for name, active, _ in ASSIGNMENT_SPEC:
    matches = session.query(Assignment).filter(func.trim(Assignment.name) == name).all()
    if not matches:
        session.add(Assignment(name=name, active=active))
        continue
    if len(matches) > 1:
        print(f"[database] 作业类型「{name}」在库里有 {len(matches)} 行（id={[m.id for m in matches]}），请人工清理")
    for row in matches:
        if bool(row.active) != active:
            row.active = active
if session.get(Assignment, LEAVE_ID) is None:
    session.add(Assignment(id=LEAVE_ID, name="请假"))

# 提交并关闭会话
session.commit()
session.close()

# 导出Session供其他模块使用
__all__ = [
    "Session", "User", "Assignment", "CheckInRecord", "EarlyBirdRecord", "LeaveRecord", "RewardRecord",
    "ASSIGNMENT_SPEC", "ASSIGNMENT_ORDER", "COMPOSITE_NAMES", "COMPOSITE_REQUIRED", "LEAVE_ID",
    "assignment_sort_key", "report_display_name", "engine",
]