#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal
from utils.helpers import to_decimal, round_decimal

def _d(val) -> Decimal:
    return to_decimal(val)

def _calc_index(val, coeff, norm=Decimal('1')) -> Decimal:
    """Расчёт компонента индекса через Decimal."""
    return Decimal(str(coeff)) * (_d(val) / _d(norm))

def calculate_chat_health_indices(raw, det, divisor):
    """
    Рассчитывает итоговый индекс здоровья чата и все промежуточные показатели.
    
    raw: данные из chat_stats (chars, avg_len, words, media)
    det: данные из user_stats (korp, kprp, kopyup, kopyap, kupp, pivdvp)
    divisor: Decimal (знаменатель — кол-во живых участников)
    """
    # Вычисляем каждый индекс по отдельности
    indices = {
        'oksp':   _calc_index(raw['chars'],    Decimal('0.05'), Decimal('100')) / divisor,
        'sdsp':   _calc_index(raw['avg_len'],  Decimal('0.05'), Decimal('100')) / divisor,
        'cho':    _calc_index(raw['words'],    Decimal('0.05'))                 / divisor,
        'media':  _calc_index(raw['media'],    Decimal('0.07'))                 / divisor,
        'korp':   _calc_index(det['korp'],     Decimal('0.08'))                 / divisor,
        'kprp':   _calc_index(det['kprp'],     Decimal('0.10'))                 / divisor,
        'kopyup': _calc_index(det['kopyup'],   Decimal('0.18'))                 / divisor,
        'kopyap': _calc_index(det['kopyap'],   Decimal('0.15'))                 / divisor,
        'kupp':   _calc_index(det['kupp'],     Decimal('0.15'))                 / divisor,
        'pivdvp': _calc_index(det['pivdvp'],   Decimal('0.12'))                 / divisor,
    }

    # Итоговый индекс — это сумма всех компонентов
    health_index = sum(indices.values())
    
    return health_index, indices