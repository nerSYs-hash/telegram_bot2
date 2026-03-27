"""
face_detector.py — детектор человеческих лиц через OpenCV (Haar Cascade).
Используется при одобрении заявок для выбора аватарки с реальным лицом.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def has_human_face(byte_array: bytearray) -> bool:
    """
    Проверяет наличие человеческого лица на изображении.
    Использует asyncio.to_thread чтобы не блокировать event loop.

    Args:
        byte_array: изображение в виде bytearray

    Returns:
        True если найдено хотя бы одно лицо, иначе False
    """
    def _detect(data: bytearray) -> bool:
        try:
            import cv2
            import numpy as np

            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )

            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return False

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            return len(faces) > 0

        except Exception as e:
            logger.error(f"face_detector: ошибка при детекции лица: {e}")
            return False

    return await asyncio.to_thread(_detect, byte_array)
