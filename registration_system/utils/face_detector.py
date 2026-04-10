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
    Пробует несколько каскадов и параметров для максимального охвата.

    Returns:
        True если найдено хотя бы одно лицо, иначе False
    """
    def _detect(data: bytearray) -> bool:
        try:
            import cv2
            import numpy as np

            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return False

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Выравниваем яркость для лучшей детекции
            gray = cv2.equalizeHist(gray)

            # Каскады: фронтальный + профильный
            cascade_files = [
                'haarcascade_frontalface_default.xml',
                'haarcascade_frontalface_alt.xml',
                'haarcascade_frontalface_alt2.xml',
                'haarcascade_profileface.xml',
            ]

            # Наборы параметров: от строгих к мягким
            param_sets = [
                {'scaleFactor': 1.1, 'minNeighbors': 5, 'minSize': (30, 30)},
                {'scaleFactor': 1.1, 'minNeighbors': 3, 'minSize': (20, 20)},
                {'scaleFactor': 1.05, 'minNeighbors': 3, 'minSize': (20, 20)},
            ]

            for cascade_file in cascade_files:
                cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + cascade_file
                )
                if cascade.empty():
                    continue
                for params in param_sets:
                    faces = cascade.detectMultiScale(gray, **params)
                    if len(faces) > 0:
                        logger.debug(
                            f"face_detector: лицо найдено каскадом {cascade_file} "
                            f"minNeighbors={params['minNeighbors']}"
                        )
                        return True

            return False

        except Exception as e:
            logger.error(f"face_detector: ошибка при детекции лица: {e}")
            return False

    return await asyncio.to_thread(_detect, byte_array)
