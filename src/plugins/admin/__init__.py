from nonebot import get_driver
from .routes import router

driver = get_driver()


@driver.on_startup
async def mount_admin():
    from nonebot import get_app
    app = get_app()
    app.include_router(router, prefix="/admin")
    from nonebot.log import logger
    logger.info("管理面板: http://127.0.0.1:8080/admin/")
