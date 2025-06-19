import asyncio
import aiohttp
import json

from src.okens import token_manager
from src.onfig import HEADERS
from pprint import pprint


async def check_single_cell(session, cell_id):
    url = f'https://notpixel.org/api/v1/battle-canvas/pixels/{cell_id}'
    try:
        async with session.get(url) as response:
            try:
                data = await response.json()
                return cell_id, data, response.status
            except json.decoder.JSONDecodeError:
                return cell_id, None, response.status

    except Exception as e:
        print(f"Ошибка для ячейки {cell_id}: {e}")
    return cell_id, None


async def quick_check_cells(cell_ids):
    """Быстрая проверка конкретных ячеек по их ID"""

    req_headers = HEADERS.copy()

    access_token = await token_manager.get_valid_access_token()
    req_headers['Authorization'] = f'Bearer {access_token}'

    async with aiohttp.ClientSession(headers=req_headers) as session:
        tasks = [check_single_cell(session, cell_id) for cell_id in cell_ids]
        results = await asyncio.gather(*tasks)

        for cell_id, data, status in results:
            if data:
                pprint(f'{status=}\n{data=}')
                # item_address = data.get('metaData', {}).get('itemAddress', '')
                # if item_address == '':
                #     # Вычисляем координаты
                #     base_id = 393601
                #     start_x = 384
                #     start_y = 384
                #     width = 256
                #     delta = cell_id - base_id
                #     y = start_y + delta // width
                #     x = start_x + delta % width
                #     link = f'https://t.me/notpixel/app?startapp=x{x}_y{y}_mbattle'
                #     print(f"найдена свободная ячейка ид {cell_id} координаты: {x}, {y}: {link}")



if __name__ == '__main__':
    # Пример использования для проверки конкретных ячеек
    asyncio.run(quick_check_cells([393601]))
    asyncio.run(quick_check_cells([653839]))
