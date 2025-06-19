from src.config import BASE_START, BASE_ID, BASE_END, PIXEL_URL, PIXEL_CHECK_URL


def get_id(x: int, y: int) -> str:
    """Получить ID ячейки по координатам"""
    pid = str(BASE_ID + (x - BASE_START) + (y - BASE_START) * 1024)

    return pid


def get_pixel_url(x: int, y: int) -> str:
    return PIXEL_URL.format(x=x, y=y)


def get_check_url(pixel_id) -> str:
    return PIXEL_CHECK_URL.format(pixel_id=pixel_id)
