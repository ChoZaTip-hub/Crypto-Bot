"""Resolve which symbols the bot trades this cycle."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.exchange_account_repo import ExchangeAccountRepository
from app.db.repositories.position_repo import PositionRepository
from app.services.coin_scanner_service import CoinScannerService, ScannerSnapshot

logger = get_logger(__name__)

_last_scan: ScannerSnapshot | None = None


class TradingUniverseService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._positions = PositionRepository(session)

    async def resolve(self) -> tuple[list[str], ScannerSnapshot | None]:
        global _last_scan
        symbols: list[str] = []
        scan_snap: ScannerSnapshot | None = None

        if self._settings.scanner_enabled:
            scanner = CoinScannerService(self._session, self._settings)
            scan_snap = await scanner.scan()
            _last_scan = scan_snap
            symbols.extend(scan_snap.top_symbols)
            logger.info(
                "scanner_complete",
                top=scan_snap.top_symbols[:10],
                checked=scan_snap.candidates_checked,
            )

        symbols.extend(self._settings.symbol_whitelist)

        open_positions = await self._positions.get_open_positions()
        for pos in open_positions:
            symbols.append(pos.symbol)

        # Dedupe preserve order
        seen: set[str] = set()
        ordered: list[str] = []
        for s in symbols:
            su = s.upper()
            if su in seen:
                continue
            seen.add(su)
            ordered.append(su)

        cap = self._settings.max_symbols_per_cycle
        return ordered[:cap], scan_snap

    @staticmethod
    def last_scan_snapshot() -> ScannerSnapshot | None:
        return _last_scan
