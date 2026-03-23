from decimal import Decimal
from utils.helpers import to_decimal, round_decimal

def _d(val) -> Decimal:
    return to_decimal(val)

def _calc_index(val, coeff, norm=Decimal('1')) -> Decimal:
    """Расчёт компонента индекса через Decimal."""
    return Decimal(str(coeff)) * (_d(val) / _d(norm))

def calculate_health_index(raw_stats, detailed_stats, divisor):
    """
    Рассчитывает итоговый индекс здоровья чата.
    Переносим сюда всю логику с oksp_idx, sdsp_idx и т.д.
    """
    # ... логика расчета из generate_export_file ...
    return health_index # и промежуточные индексы