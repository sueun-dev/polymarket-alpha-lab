# core/models.py
from __future__ import annotations

from pydantic import BaseModel, Field, computed_field
from datetime import datetime
from typing import Any, Optional, List, Dict

class Market(BaseModel):
    condition_id: str
    question: str
    slug: str = ""
    tokens: List[dict] = Field(default_factory=list)
    end_date_iso: Optional[str] = None
    active: bool = True
    volume: float = 0.0
    liquidity: float = 0.0
    category: str = ""
    description: str = ""
    resolution_source: Optional[str] = None
    event_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    enable_order_book: bool = False

class Opportunity(BaseModel):
    market_id: str
    question: str
    market_price: float
    category: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Signal(BaseModel):
    market_id: str
    token_id: str
    side: str  # "buy" or "sell"
    estimated_prob: float
    market_price: float
    confidence: float
    strategy_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @computed_field
    @property
    def edge(self) -> float:
        return self.estimated_prob - self.market_price

class Order(BaseModel):
    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    strategy_name: str
    order_id: Optional[str] = None
    status: str = "pending"
    timestamp: Optional[datetime] = None

    @computed_field
    @property
    def total_cost(self) -> float:
        return self.price * self.size

class Position(BaseModel):
    market_id: str
    token_id: str
    side: str
    entry_price: float
    size: float
    current_price: float
    strategy_name: str

    @computed_field
    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.size
