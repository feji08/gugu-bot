import os
from pathlib import Path
import random
from nonebot import on_command
from nonebot.adapters.qq.message import MessageSegment
from nonebot.adapters.qq import Bot, Event
from nonebot import on_regex
from nonebot.params import RegexMatched
from ..database import Session, User, EarlyBirdRecord
from ..myGlobals import SPY_PREFIXES
from src.plugins.group_manage import send_summary

ping = on_command("咕咕咕")

@ping.handle()
async def handle_first_receive(bot: Bot, event: Event):
    # await ping.send("咕咕咕咕咕咕咕")
    import pandas as pd
    import matplotlib.pyplot as plt

    # 设置 Matplotlib 字体，确保支持中文
    plt.rcParams["font.family"] = ["SimHei"]  # Windows 用户
    # plt.rcParams["font.family"] = ["Arial Unicode MS"]  # Mac 用户

    # 模拟从数据库导出的打卡记录
    data = {
        "日期": ["2023-10-01", "2023-10-01", "2023-10-01", "2023-10-02", "2023-10-02"],
        "姓名": ["帽帽", "香香", "孟春", "粥粥", "娓娓"],
        "打卡时间": ["08:30", "09:00", "08:45", "08:50", "09:10"],
        "作业": ["练笔"]*5
    }
    df = pd.DataFrame(data)

    # 按日期分组，找到每天第一个打卡的人
    df["是否第一个"] = df.groupby("日期")["打卡时间"].transform(lambda x: x == x.min())

    # 创建二维表格，行索引为 "打卡时间"，列索引为 "姓名"，单元格填充打卡日期
    df_pivot = df.pivot(index="姓名", columns="日期", values="作业")

    # 生成背景色矩阵（默认浅灰色）
    def generate_colors(df, df_pivot):
        colors = [["#FBFFE4"] * df_pivot.shape[1] for _ in range(df_pivot.shape[0])]  # 默认背景色
        for i, name in enumerate(df_pivot.index):  # 遍历行（姓名）
            for j, date in enumerate(df_pivot.columns):  # 遍历列（日期）
                first_check_names = df[(df["日期"] == date) & (df["是否第一个"])]["姓名"].tolist()  # 获取当天最早打卡者
                if name in first_check_names:
                    colors[i][j] = "#B3D8A8"  # 该姓名的单元格高亮
        return colors

    cell_colors = generate_colors(df, df_pivot)

    # 创建绘图画布
    fig, ax = plt.subplots(figsize=(0.08+0.96*2, 4))  # 设置图像大小
    ax.axis("off")  # 隐藏坐标轴

    # 创建表格并应用颜色
    table = plt.table(
        cellText=df_pivot.values,  # 显示日期
        colLabels=df_pivot.columns,  # 表头（姓名）
        rowLabels=df_pivot.index,  # 行标签（打卡时间）
        cellLoc="center",
        loc="center",
        cellColours=cell_colors,  # 颜色矩阵
    )

    # HEADER_GREEN = "#77DD77"  # 头部浅绿色
    # EDGE_COLOR = "#006400"  # 深绿色边框
    table.add_cell(0, -1, width=0.2, height = 0.054, text="昵称")

    # 调整表格格式
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.2)  # 适当放大表格

    # **保存为图片**
    save_path = Path("打卡表格.png")
    plt.savefig(save_path, dpi=300, bbox_inches="tight", pad_inches=0.1)  # 高分辨率保存
    plt.show()

    print(f"图片已保存到: {save_path}")
    await ping.send("周总结（全体）已生成，图片正在赶来的路上，请耐心等候~")

    file_message = MessageSegment.file_image(save_path)
    # 发送消息
    await ping.send("咕咕咕咕咕咕咕" + file_message)

# 使用正则匹配 "偷看xxx的鸟鸟卡"
spy = on_regex(r"/偷看(?P<target>.+)的鸟鸟卡", priority=5, block=True)
@spy.handle()
async def handle_first_receive(bot: Bot, event: Event):
    # 打印事件的原始消息
    print(f"Event message: {event.get_message()}")
    # 手动解析正则
    import re
    match = re.match(r"/?偷看(?P<target>.+?)的鸟鸟卡", str(event.get_message()))
    if match:
        target = match.group("target")
        session = Session()
        try:
            # 查询用户 ID
            user = session.query(User).filter_by(cute_name=target).first()
            if not user:
                await spy.send(f"没有叫{target}的咕咕哦（捂眼睛）~")
                return

            # 查询早鸟记录的 count 值
            record = session.query(EarlyBirdRecord).filter_by(user_id=user.user_id).first()
            if random.random() < 0.8:
                # 随机选择一个前缀
                prefix = random.choice(SPY_PREFIXES)
                if target == '帽帽':
                    await spy.send(f"帽帽偷偷给自己添加了100张鸟鸟卡，并把你抓进了小黑屋")
                else:
                    await spy.send(f"{prefix}{target}居然有{record.count}张鸟鸟卡！")
            else:
                cute_names = session.query(User.cute_name).distinct().all()
                cute_names = [cute_name[0] for cute_name in cute_names]
                thief = random.choice(cute_names)
                await spy.send(f"偷看失败,鸟鸟卡被{thief}偷走了~")

        except Exception as e:
            cute_names = session.query(User.cute_name).distinct().all()
            cute_names = [cute_name[0] for cute_name in cute_names if cute_name != target]
            thief = random.choice(cute_names)
            await spy.send(f"偷看失败,鸟鸟卡被{thief}偷走了~")
        finally:
            session.close()
    else:
        await spy.send("叫错咕咕啦~")