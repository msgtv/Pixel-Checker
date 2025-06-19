import asyncio
import logging

from src.scanner.scanner import PixelScanner
from src.config import PIXELS_DATA_FILENAME

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def main():
    scanner = PixelScanner(PIXELS_DATA_FILENAME)

    await scanner.scan_canvas(max_concurrent=1)


if __name__ == "__main__":
    asyncio.run(main())
