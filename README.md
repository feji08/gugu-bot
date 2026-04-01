# gugu-bot

写作群考勤打卡 QQ 机器人，基于 NoneBot2 + QQ 适配器。

## 功能

- 每日打卡（多种作业类型）
- 请假 / 早鸟卡 / 奖励管理
- 个人统计查询
- 月度考勤报告（xlsx 导出）
- Web 管理后台（用户、打卡、请假、配置、月报）

## 依赖

- Python >= 3.8
- NoneBot2 + nonebot-adapter-qq
- FastAPI（Web 后台 + Bot ASGI 驱动）
- SQLAlchemy + SQLite
- pandas + openpyxl（报表生成）
- Jinja2（模板渲染）

## 环境变量

| 变量 | 说明 |
|------|------|
| `QQ_BOTS` | QQ 机器人凭据，格式：`[{"id":"appid","token":"...","secret":"...","intent":{"c2c_group_at_messages":true}}]` |

本地开发放 Windows 用户环境变量，服务器部署放 `/root/gugu-bot/.env.secret`。

## 启动

```bash
# 安装依赖
pip install -r requirements.txt

# 运行（开发模式，热重载）
nb run --reload
```

管理后台访问：`http://127.0.0.1:8080/admin/`

## 部署

使用 systemd 管理进程，GitHub Actions 自动部署。详见 `.github/workflows/deploy.yml`。

## Documentation

See [NoneBot2 Docs](https://nonebot.dev/)
