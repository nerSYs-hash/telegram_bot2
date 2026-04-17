import shutil, os

src_dir = r'C:\Users\Илья\Desktop\Обновление БОТА\Не выгружено'
dst_dir = r'C:\bot_2\telegram_bot2\assets\banners'

os.makedirs(dst_dir, exist_ok=True)

files = [
    ('KmHm4-fotor-20260410205813.jpg', 'lottery_banner.jpg'),
    ('M8uau-fotor-2026041021039.jpg',  'bingo_banner.jpg'),
    ('yjND6-fotor-20260410213214.jpg', 'donate_banner.jpg'),
    ('eNmRY-fotor-20260410213653.jpg', 'gift_banner.jpg'),
]

for src_name, dst_name in files:
    src = os.path.join(src_dir, src_name)
    dst = os.path.join(dst_dir, dst_name)
    shutil.copy(src, dst)
    print(f'Copied: {dst_name}')

print('Done.')
