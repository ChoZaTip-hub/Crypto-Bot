"""Trade simulator for backtesting."""

from dataclasses import dataclass


@dataclass
class SimulatedTrade:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    qty: float
    entry_ts: int
    exit_ts: int

    @property
    def pnl(self) -> float:
        if self.side == "BUY":
            return (self.exit_price - self.entry_price) * self.qty
        return (self.entry_price - self.exit_price) * self.qty


class TradeSimulator:
    def __init__(self, initial_balance: float = 10_000.0, slippage_bps: float = 5.0) -> None:
        self._balance = initial_balance
        self._slippage = slippage_bps / 10_000
        self._trades: list[SimulatedTrade] = []
        self._position: dict | None = None

    def process_bar(
        self,
        symbol: str,
        ts: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        signal: str,
        stop: float | None,
        take_profit: float | None,
    ) -> None:
        slip = self._slippage
        if self._position:
            pos = self._position
            exit_price = None
            if pos["side"] == "BUY":
                if stop and low <= stop:
                    exit_price = stop * (1 - slip)
                elif take_profit and high >= take_profit:
                    exit_price = take_profit * (1 - slip)
                elif signal == "SELL":
                    exit_price = close * (1 - slip)
            if exit_price:
                trade = SimulatedTrade(
                    symbol=symbol,
                    side=pos["side"],
                    entry_price=pos["entry"],
                    exit_price=exit_price,
                    qty=pos["qty"],
                    entry_ts=pos["ts"],
                    exit_ts=ts,
                )
                self._trades.append(trade)
                self._balance += trade.pnl
                self._position = None

        if self._position is None and signal in ("BUY", "SELL"):
            entry = close * (1 + slip) if signal == "BUY" else close * (1 - slip)
            qty = self._balance * 0.01 / entry
            self._position = {"side": signal, "entry": entry, "qty": qty, "ts": ts}

    @property
    def trades(self) -> list[SimulatedTrade]:
        return self._trades

    @property
    def balance(self) -> float:
        return self._balance
