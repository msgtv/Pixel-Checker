import asyncio
import logging
from scanner import PixelScanner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    scanner = PixelScanner()
    await scanner.scan_canvas(max_concurrent=30)

    print("\n" + "=" * 50)
    print("ИТОГОВАЯ СТАТИСТИКА:")
    print(f"Всего ДОСТУПНЫХ ДЛЯ МИНТА ячеек для минта: {len(scanner.free_cells)}")
    print(f"Всего НЕ ДОСТУПНЫХ ДЛЯ МИНТА ячеек: {len(scanner.free_cells_not_available)}")
    print(f'Ячеек доступных для покупки: {len(scanner.available_cells)}')
    print(f"Всего занятых ячеек: {len(scanner.occupied_cells)}")
    print(f"Ошибок при проверке: {len(scanner.error_cells)}")


if __name__ == "__main__":
    asyncio.run(main())
