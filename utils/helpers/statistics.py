#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Класс Statistics и генерация HTML-отчётов."""

from utils.helpers.time_utils import get_moscow_time


class Statistics:
    """Helper class for statistics calculations"""
    
    @staticmethod
    def calculate_percentage(part, total):
        """Calculate percentage"""
        if total == 0:
            return 0.0
        return round((part / total) * 100, 2)
    
    @staticmethod
    def get_rank_emoji(rank):
        """Get emoji for rank"""
        emojis = {
            1: '🥇',
            2: '🥈',
            3: '🥉',
            4: '4️⃣',
            5: '5️⃣'
        }
        return emojis.get(rank, '▪️')
    
    @staticmethod
    def format_activity_score(score, as_percentage=False, total_sum=None):
        """Format activity score"""
        if as_percentage and total_sum and total_sum > 0:
            percentage = (score / total_sum) * 100
            return f"{percentage:.2f}%"
        return f"{score:.2f}"

def create_html_report(data, title, headers, filename):
    """Create HTML report file"""
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f1f1f1;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            color: #7f8c8d;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <table>
        <thead>
            <tr>
"""
    
    for header in headers:
        html_content += f"                <th>{header}</th>\n"
    
    html_content += """            </tr>
        </thead>
        <tbody>
"""
    
    for row in data:
        html_content += "            <tr>\n"
        for cell in row:
            html_content += f"                <td>{cell}</td>\n"
        html_content += "            </tr>\n"
    
    html_content += """        </tbody>
    </table>
    <div class="footer">
        <p>Сгенерировано: """ + get_moscow_time().strftime('%d.%m.%Y %H:%M:%S') + """ МСК</p>
    </div>
</body>
</html>"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return filename
