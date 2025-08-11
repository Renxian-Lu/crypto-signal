from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel

class OHLCVQuery(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 300
    exchange: str = "binance"

class IndicatorQuery(OHLCVQuery):
    indicators: Optional[List[Literal["RSI","MACD"]]] = None

class SignalResponse(BaseModel):
    symbol: str
    timeframe: str
    action: Literal["buy","sell","wait"]
    scores: Dict[str, float]
    reasons: List[str]
    levels: Dict[str, float]
    meta: Dict[str, Any]
