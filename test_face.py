"""Тест face_detector.py — запускать локально"""
import asyncio
import sys
import importlib.util, pathlib

spec = importlib.util.spec_from_file_location(
    "face_detector",
    pathlib.Path(__file__).parent / "registration_system/utils/face_detector.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
has_human_face = mod.has_human_face


async def test(path: str):
    with open(path, 'rb') as f:
        data = bytearray(f.read())
    result = await has_human_face(data)
    print(f"{'✅ Лицо найдено' if result else '❌ Лицо не найдено'} — {path}")


async def main():
    if len(sys.argv) < 2:
        print("Использование: python test_face.py фото.jpg [фото2.jpg ...]")
        sys.exit(1)
    for p in sys.argv[1:]:
        await test(p)

if __name__ == '__main__':
    asyncio.run(main())
