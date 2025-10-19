import logging
from datetime import timedelta
from decimal import Decimal

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

_CACHE = {}
_CACHE_TIMEOUT = timedelta(hours=12)


def get_exchange_rate(base_currency: str, target_currency: str) -> Decimal:
    base = (base_currency or 'USD').upper()
    target = (target_currency or 'USD').upper()
    if base == target:
        return Decimal('1')

    key = (base, target)
    cached = _CACHE.get(key)
    now = timezone.now()
    if cached and now - cached['timestamp'] < _CACHE_TIMEOUT:
        return cached['rate']

    try:
        response = requests.get(
            'https://api.exchangerate.host/convert',
            params={'from': base, 'to': target},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json() or {}
        rate = Decimal(str(data.get('result') or 0))
        if rate > 0:
            _CACHE[key] = {'rate': rate, 'timestamp': now}
            return rate
    except Exception as exc:  # pragma: no cover
        logger.warning('Currency conversion failed: %s', exc)

    return Decimal('1')


def convert_amount(amount: Decimal, base_currency: str, target_currency: str) -> Decimal:
    rate = get_exchange_rate(base_currency, target_currency)
    return (Decimal(amount) * rate).quantize(Decimal('0.01'))
