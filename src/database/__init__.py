# database/__init__.py
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 使用绝对路径
db_path = Path(__file__).parent / "gugu.db"
engine = create_engine(f'sqlite:///{db_path}', echo=False)

# 创建一个基类
Base = declarative_base()

# 定义用户模型
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, nullable=False)
    nickname = Column(String, unique=True, nullable=False)
    group_level = Column(Integer, default=0)

# 定义作业类型模型
class Assignment(Base):
    __tablename__ = 'assignments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # 作业类型名称

# 定义打卡记录模型
class CheckInRecord(Base):
    __tablename__ = 'checkin_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)  # 用户 ID
    assignment_id = Column(Integer, ForeignKey('assignments.id'), nullable=False)  # 作业类型 ID
    checkin_time = Column(DateTime, default=datetime.utcnow)  # 打卡时间

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

# 创建所有表（如果表不存在）
Base.metadata.create_all(engine)

# 创建数据库会话
Session = sessionmaker(bind=engine)
session = Session()

# 插入默认的作业类型
default_assignments = ["输出练笔", "扒文扒榜", "其他练习"]

for assignment_name in default_assignments:
    # 检查作业类型是否已经存在
    existing_assignment = session.query(Assignment).filter_by(name=assignment_name).first()
    if not existing_assignment:
        # 插入新的作业类型
        new_assignment = Assignment(name=assignment_name)
        session.add(new_assignment)
leave_assignment = Assignment(id=100,name='请假')
if not leave_assignment:
    session.add(leave_assignment)

# 提交并关闭会话
session.commit()
session.close()

# 导出Session供其他模块使用
__all__ = ["Session", "User"]