"""Market-specific sessions and instrument configuration.

CAC 40 price uses ^FCHI. Constituent stock volumes are an imperfect
participation proxy; never interpret them as index volume.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Market:
    key: str
    name: str
    symbol: str
    timezone: str
    start: str  # end timestamp of first completed 5-minute candle
    end: str
    currency: str
    leaders: tuple[str, ...]
    min_breadth_count: int = 20

NASDAQ = Market(
    'nasdaq', 'Nasdaq 100 (QQQ)', 'QQQ', 'America/New_York',
    '09:35', '16:00', '$',
    ('AAPL','MSFT','NVDA','AMZN','META','GOOGL','GOOG','AVGO','TSLA','COST',
     'NFLX','AMD','ADBE','PEP','CSCO','TMUS','INTC','AMAT','QCOM','INTU',
     'TXN','ISRG','BKNG','MU','PANW','ADP','LRCX','KLAC','CRWD'))

CAC = Market(
    'cac', 'CAC 40 (^FCHI)', '^FCHI', 'Europe/Paris',
    '09:05', '17:30', '€',
    ('AI.PA','AIR.PA','ALO.PA','ACA.PA','BNP.PA','CAP.PA','CA.PA','CS.PA',
     'DSY.PA','EDEN.PA','ENGI.PA','EL.PA','ERF.PA','RMS.PA','KER.PA',
     'LR.PA','OR.PA','MC.PA','ML.PA','ORA.PA','RI.PA','SAF.PA',
     'SGO.PA','SAN.PA','SU.PA','GLE.PA','STLAP.PA','STMPA.PA',
     'TEP.PA','TTE.PA','VIE.PA','DG.PA','VIV.PA'))

MARKETS = {'CAC 40 — Paris': CAC, 'Nasdaq 100 — New York': NASDAQ}
