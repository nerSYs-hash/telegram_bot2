#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Экспорт статистики в CSV."""

from utils.helpers.time_utils import get_moscow_time


def export_stats_to_csv(stats_data, filename):
    """Export statistics to CSV file"""
    try:
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            
            # Title
            writer.writerow([stats_data['title']])
            writer.writerow([])
            
            # General stats
            writer.writerow(['📊 ОБЩАЯ СТАТИСТИКА'])
            for key, value in stats_data['general'].items():
                writer.writerow([key, value])
            
            writer.writerow([])
            
            # Top messages
            writer.writerow(['🏆 ТОП-5 ПО СООБЩЕНИЯМ'])
            writer.writerow(['Место', 'Пользователь', 'Сообщений', 'Заработано'])
            for user_data in stats_data['top_messages']:
                writer.writerow([
                    user_data['rank'],
                    user_data['username'],
                    user_data['messages'],
                    user_data.get('earned', 0)
                ])
            
            writer.writerow([])
            
            # Top earners
            writer.writerow(['💰 ТОП-5 ПО ЗАРАБОТКУ'])
            writer.writerow(['Место', 'Пользователь', 'Заработано'])
            for user_data in stats_data['top_earners']:
                writer.writerow([
                    user_data['rank'],
                    user_data['username'],
                    user_data['earned']
                ])
            
            writer.writerow([])
            writer.writerow([f'Сгенерировано: {get_moscow_time().strftime("%d.%m.%Y %H:%M:%S")} МСК'])
        
        return filename
    except Exception as e:
        print(f"Error creating CSV: {e}")
        return None
