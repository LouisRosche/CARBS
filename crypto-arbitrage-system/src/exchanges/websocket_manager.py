"""
WebSocket Manager for Real-Time Exchange Data

Production-grade WebSocket management:
- Multi-exchange support
- Automatic reconnection with backoff
- Message parsing and normalization
- Order book management
- Trade stream handling
- Connection health monitoring
- Subscription management

Supported exchanges:
- Binance
- MEXC
- KuCoin
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set
import aiohttp
import hashlib
import hmac

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection state"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"


class StreamType(Enum):
    """Types of data streams"""
    ORDERBOOK = "orderbook"
    TRADE = "trade"
    TICKER = "ticker"
    KLINE = "kline"
    USER_DATA = "user_data"


@dataclass
class OrderBookUpdate:
    """Normalized order book update"""
    exchange: str
    symbol: str
    bids: List[tuple]  # [(price, quantity), ...]
    asks: List[tuple]
    timestamp: datetime
    is_snapshot: bool = False


@dataclass
class TradeUpdate:
    """Normalized trade update"""
    exchange: str
    symbol: str
    trade_id: str
    price: Decimal
    quantity: Decimal
    side: str  # 'buy' or 'sell'
    timestamp: datetime


@dataclass
class TickerUpdate:
    """Normalized ticker update"""
    exchange: str
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume_24h: Decimal
    timestamp: datetime


@dataclass
class ConnectionMetrics:
    """Connection statistics"""
    connected_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    messages_received: int = 0
    reconnect_count: int = 0
    errors: int = 0


class WebSocketHandler(ABC):
    """Base class for exchange WebSocket handlers"""

    def __init__(self, exchange: str):
        self.exchange = exchange
        self.state = ConnectionState.DISCONNECTED
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._subscriptions: Set[str] = set()
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._metrics = ConnectionMetrics()
        self._running = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._ping_interval = 30.0
        self._ping_task: Optional[asyncio.Task] = None

    @property
    @abstractmethod
    def ws_url(self) -> str:
        """WebSocket URL"""
        pass

    @abstractmethod
    def _build_subscribe_message(self, channels: List[str]) -> Dict:
        """Build subscription message"""
        pass

    @abstractmethod
    def _parse_message(self, data: Dict) -> Optional[Any]:
        """Parse incoming message"""
        pass

    async def connect(self):
        """Establish WebSocket connection"""
        if self.state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING]:
            return

        self.state = ConnectionState.CONNECTING
        self._running = True

        try:
            self._session = aiohttp.ClientSession()
            self._ws = await self._session.ws_connect(
                self.ws_url,
                heartbeat=30,
                receive_timeout=60
            )

            self.state = ConnectionState.CONNECTED
            self._metrics.connected_at = datetime.now(timezone.utc)
            self._reconnect_delay = 1.0

            logger.info(f"{self.exchange} WebSocket connected")

            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())

            # Resubscribe if reconnecting
            if self._subscriptions:
                await self._resubscribe()

        except Exception as e:
            logger.error(f"{self.exchange} WebSocket connection failed: {e}")
            self.state = ConnectionState.DISCONNECTED
            self._metrics.errors += 1
            raise

    async def disconnect(self):
        """Close WebSocket connection"""
        self._running = False
        self.state = ConnectionState.CLOSING

        if self._ping_task:
            self._ping_task.cancel()

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._session:
            await self._session.close()
            self._session = None

        self.state = ConnectionState.DISCONNECTED
        logger.info(f"{self.exchange} WebSocket disconnected")

    async def subscribe(self, stream_type: StreamType, symbols: List[str]):
        """Subscribe to data streams"""
        channels = self._get_channels(stream_type, symbols)

        if self.state == ConnectionState.CONNECTED and self._ws:
            message = self._build_subscribe_message(channels)
            await self._ws.send_json(message)

        self._subscriptions.update(channels)
        logger.info(f"{self.exchange} subscribed to {len(channels)} channels")

    async def unsubscribe(self, stream_type: StreamType, symbols: List[str]):
        """Unsubscribe from data streams"""
        channels = self._get_channels(stream_type, symbols)

        if self.state == ConnectionState.CONNECTED and self._ws:
            message = self._build_unsubscribe_message(channels)
            await self._ws.send_json(message)

        self._subscriptions -= set(channels)

    def on_orderbook(self, callback: Callable[[OrderBookUpdate], Coroutine]):
        """Register order book callback"""
        self._callbacks[StreamType.ORDERBOOK.value].append(callback)

    def on_trade(self, callback: Callable[[TradeUpdate], Coroutine]):
        """Register trade callback"""
        self._callbacks[StreamType.TRADE.value].append(callback)

    def on_ticker(self, callback: Callable[[TickerUpdate], Coroutine]):
        """Register ticker callback"""
        self._callbacks[StreamType.TICKER.value].append(callback)

    async def run(self):
        """Main receive loop"""
        while self._running:
            try:
                if self.state != ConnectionState.CONNECTED:
                    await self._reconnect()
                    continue

                async for msg in self._ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_message(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"{self.exchange} WS error: {self._ws.exception()}")
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        logger.warning(f"{self.exchange} WS closed")
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"{self.exchange} WS error: {e}")
                self._metrics.errors += 1

            if self._running:
                await self._reconnect()

    async def _handle_message(self, raw_data: str):
        """Handle incoming message"""
        try:
            data = json.loads(raw_data)
            self._metrics.messages_received += 1
            self._metrics.last_message_at = datetime.now(timezone.utc)

            update = self._parse_message(data)
            if update:
                await self._dispatch(update)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse message: {e}")

    async def _dispatch(self, update: Any):
        """Dispatch update to callbacks"""
        if isinstance(update, OrderBookUpdate):
            callbacks = self._callbacks.get(StreamType.ORDERBOOK.value, [])
        elif isinstance(update, TradeUpdate):
            callbacks = self._callbacks.get(StreamType.TRADE.value, [])
        elif isinstance(update, TickerUpdate):
            callbacks = self._callbacks.get(StreamType.TICKER.value, [])
        else:
            return

        for callback in callbacks:
            try:
                await callback(update)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def _reconnect(self):
        """Reconnect with exponential backoff"""
        self.state = ConnectionState.RECONNECTING
        self._metrics.reconnect_count += 1

        logger.info(f"{self.exchange} reconnecting in {self._reconnect_delay}s...")
        await asyncio.sleep(self._reconnect_delay)

        # Exponential backoff
        self._reconnect_delay = min(
            self._reconnect_delay * 2,
            self._max_reconnect_delay
        )

        try:
            await self.connect()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")

    async def _resubscribe(self):
        """Resubscribe to all channels after reconnect"""
        if self._subscriptions and self._ws:
            message = self._build_subscribe_message(list(self._subscriptions))
            await self._ws.send_json(message)
            logger.info(f"{self.exchange} resubscribed to {len(self._subscriptions)} channels")

    async def _ping_loop(self):
        """Send periodic pings"""
        while self._running and self.state == ConnectionState.CONNECTED:
            try:
                await asyncio.sleep(self._ping_interval)
                if self._ws:
                    await self._ws.ping()
            except Exception as e:
                logger.debug(f"{self.exchange} ping failed, triggering reconnect: {e}")
                break

    def _get_channels(self, stream_type: StreamType, symbols: List[str]) -> List[str]:
        """Get channel names for subscription"""
        return [f"{stream_type.value}:{s}" for s in symbols]

    def _build_unsubscribe_message(self, channels: List[str]) -> Dict:
        """Build unsubscribe message (default implementation)"""
        return {"method": "UNSUBSCRIBE", "params": channels}

    @property
    def metrics(self) -> ConnectionMetrics:
        return self._metrics


class BinanceWebSocket(WebSocketHandler):
    """Binance WebSocket handler"""

    def __init__(self, testnet: bool = False):
        super().__init__("binance")
        self._testnet = testnet
        self._stream_id = 1

    @property
    def ws_url(self) -> str:
        if self._testnet:
            return "wss://testnet.binance.vision/ws"
        return "wss://stream.binance.com:9443/ws"

    def _get_channels(self, stream_type: StreamType, symbols: List[str]) -> List[str]:
        """Get Binance stream names"""
        channels = []
        for symbol in symbols:
            s = symbol.lower()
            if stream_type == StreamType.ORDERBOOK:
                channels.append(f"{s}@depth20@100ms")
            elif stream_type == StreamType.TRADE:
                channels.append(f"{s}@trade")
            elif stream_type == StreamType.TICKER:
                channels.append(f"{s}@ticker")
            elif stream_type == StreamType.KLINE:
                channels.append(f"{s}@kline_1m")
        return channels

    def _build_subscribe_message(self, channels: List[str]) -> Dict:
        self._stream_id += 1
        return {
            "method": "SUBSCRIBE",
            "params": channels,
            "id": self._stream_id
        }

    def _parse_message(self, data: Dict) -> Optional[Any]:
        """Parse Binance message"""
        if "e" not in data:
            return None

        event_type = data["e"]

        if event_type == "depthUpdate":
            return OrderBookUpdate(
                exchange=self.exchange,
                symbol=data["s"],
                bids=[(Decimal(p), Decimal(q)) for p, q in data["b"]],
                asks=[(Decimal(p), Decimal(q)) for p, q in data["a"]],
                timestamp=datetime.fromtimestamp(data["E"] / 1000, tz=timezone.utc),
                is_snapshot=False
            )

        elif event_type == "trade":
            return TradeUpdate(
                exchange=self.exchange,
                symbol=data["s"],
                trade_id=str(data["t"]),
                price=Decimal(data["p"]),
                quantity=Decimal(data["q"]),
                side="sell" if data["m"] else "buy",  # m = is buyer maker
                timestamp=datetime.fromtimestamp(data["T"] / 1000, tz=timezone.utc)
            )

        elif event_type == "24hrTicker":
            return TickerUpdate(
                exchange=self.exchange,
                symbol=data["s"],
                bid=Decimal(data["b"]),
                ask=Decimal(data["a"]),
                last=Decimal(data["c"]),
                volume_24h=Decimal(data["v"]),
                timestamp=datetime.fromtimestamp(data["E"] / 1000, tz=timezone.utc)
            )

        return None


class MEXCWebSocket(WebSocketHandler):
    """MEXC WebSocket handler"""

    def __init__(self):
        super().__init__("mexc")
        self._stream_id = 1

    @property
    def ws_url(self) -> str:
        return "wss://wbs.mexc.com/ws"

    def _get_channels(self, stream_type: StreamType, symbols: List[str]) -> List[str]:
        """Get MEXC stream names"""
        channels = []
        for symbol in symbols:
            if stream_type == StreamType.ORDERBOOK:
                channels.append(f"spot@public.limit.depth.v3.api@{symbol}@20")
            elif stream_type == StreamType.TRADE:
                channels.append(f"spot@public.deals.v3.api@{symbol}")
            elif stream_type == StreamType.TICKER:
                channels.append(f"spot@public.miniTicker.v3.api@{symbol}")
        return channels

    def _build_subscribe_message(self, channels: List[str]) -> Dict:
        self._stream_id += 1
        return {
            "method": "SUBSCRIPTION",
            "params": channels,
            "id": self._stream_id
        }

    def _parse_message(self, data: Dict) -> Optional[Any]:
        """Parse MEXC message"""
        if "c" not in data:
            return None

        channel = data.get("c", "")
        payload = data.get("d", {})

        if "depth" in channel:
            symbol = channel.split("@")[-2] if "@" in channel else ""
            return OrderBookUpdate(
                exchange=self.exchange,
                symbol=symbol,
                bids=[(Decimal(b["p"]), Decimal(b["v"])) for b in payload.get("bids", [])],
                asks=[(Decimal(a["p"]), Decimal(a["v"])) for a in payload.get("asks", [])],
                timestamp=datetime.now(timezone.utc),
                is_snapshot=True
            )

        elif "deals" in channel:
            symbol = channel.split("@")[-1] if "@" in channel else ""
            deals = payload.get("deals", [])
            if deals:
                d = deals[0]
                return TradeUpdate(
                    exchange=self.exchange,
                    symbol=symbol,
                    trade_id=str(d.get("t", "")),
                    price=Decimal(d.get("p", "0")),
                    quantity=Decimal(d.get("v", "0")),
                    side="buy" if d.get("S") == 1 else "sell",
                    timestamp=datetime.fromtimestamp(d.get("t", 0) / 1000, tz=timezone.utc)
                )

        elif "miniTicker" in channel:
            return TickerUpdate(
                exchange=self.exchange,
                symbol=payload.get("s", ""),
                bid=Decimal(payload.get("b", "0") or "0"),
                ask=Decimal(payload.get("a", "0") or "0"),
                last=Decimal(payload.get("c", "0")),
                volume_24h=Decimal(payload.get("v", "0")),
                timestamp=datetime.now(timezone.utc)
            )

        return None


class KuCoinWebSocket(WebSocketHandler):
    """KuCoin WebSocket handler"""

    def __init__(self):
        super().__init__("kucoin")
        self._token: Optional[str] = None
        self._endpoint: Optional[str] = None
        self._connect_id = 0

    @property
    def ws_url(self) -> str:
        if self._endpoint and self._token:
            return f"{self._endpoint}?token={self._token}&connectId={self._connect_id}"
        return ""

    async def connect(self):
        """Get token and connect"""
        await self._get_token()
        await super().connect()

    async def _get_token(self):
        """Get KuCoin WebSocket token"""
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.kucoin.com/api/v1/bullet-public") as resp:
                data = await resp.json()
                if data.get("code") == "200000":
                    self._token = data["data"]["token"]
                    servers = data["data"]["instanceServers"]
                    if servers:
                        self._endpoint = servers[0]["endpoint"]
                        self._ping_interval = servers[0].get("pingInterval", 18000) / 1000
                else:
                    raise Exception(f"Failed to get KuCoin token: {data}")

    def _convert_symbol(self, symbol: str) -> str:
        """Convert BTCUSDT to BTC-USDT"""
        for quote in ['USDT', 'USDC', 'BTC', 'ETH']:
            if symbol.endswith(quote) and '-' not in symbol:
                return f"{symbol[:-len(quote)]}-{quote}"
        return symbol

    def _get_channels(self, stream_type: StreamType, symbols: List[str]) -> List[str]:
        """Get KuCoin topic names"""
        channels = []
        for symbol in symbols:
            s = self._convert_symbol(symbol)
            if stream_type == StreamType.ORDERBOOK:
                channels.append(f"/market/level2:{s}")
            elif stream_type == StreamType.TRADE:
                channels.append(f"/market/match:{s}")
            elif stream_type == StreamType.TICKER:
                channels.append(f"/market/ticker:{s}")
        return channels

    def _build_subscribe_message(self, channels: List[str]) -> Dict:
        self._connect_id += 1
        return {
            "id": self._connect_id,
            "type": "subscribe",
            "topic": ",".join(channels),
            "response": True
        }

    def _parse_message(self, data: Dict) -> Optional[Any]:
        """Parse KuCoin message"""
        msg_type = data.get("type")

        if msg_type == "pong":
            return None

        if msg_type != "message":
            return None

        topic = data.get("topic", "")
        payload = data.get("data", {})

        if "/market/level2" in topic:
            symbol = topic.split(":")[-1].replace("-", "")
            changes = payload.get("changes", {})
            return OrderBookUpdate(
                exchange=self.exchange,
                symbol=symbol,
                bids=[(Decimal(b[0]), Decimal(b[1])) for b in changes.get("bids", [])],
                asks=[(Decimal(a[0]), Decimal(a[1])) for a in changes.get("asks", [])],
                timestamp=datetime.fromtimestamp(
                    int(payload.get("time", time.time() * 1000)) / 1000,
                    tz=timezone.utc
                ),
                is_snapshot=False
            )

        elif "/market/match" in topic:
            symbol = topic.split(":")[-1].replace("-", "")
            return TradeUpdate(
                exchange=self.exchange,
                symbol=symbol,
                trade_id=payload.get("tradeId", ""),
                price=Decimal(payload.get("price", "0")),
                quantity=Decimal(payload.get("size", "0")),
                side=payload.get("side", "buy"),
                timestamp=datetime.fromtimestamp(
                    int(payload.get("time", time.time() * 1000000000)) / 1000000000,
                    tz=timezone.utc
                )
            )

        elif "/market/ticker" in topic:
            symbol = topic.split(":")[-1].replace("-", "")
            return TickerUpdate(
                exchange=self.exchange,
                symbol=symbol,
                bid=Decimal(payload.get("bestBid", "0") or "0"),
                ask=Decimal(payload.get("bestAsk", "0") or "0"),
                last=Decimal(payload.get("price", "0")),
                volume_24h=Decimal(payload.get("size", "0")),
                timestamp=datetime.now(timezone.utc)
            )

        return None

    async def _ping_loop(self):
        """KuCoin-specific ping"""
        while self._running and self.state == ConnectionState.CONNECTED:
            try:
                await asyncio.sleep(self._ping_interval)
                if self._ws:
                    self._connect_id += 1
                    await self._ws.send_json({
                        "id": self._connect_id,
                        "type": "ping"
                    })
            except Exception as e:
                logger.debug(f"KuCoin ping failed, triggering reconnect: {e}")
                break


class LocalOrderBook:
    """
    Local order book management

    Maintains synchronized order book from WebSocket updates
    """

    def __init__(self, exchange: str, symbol: str, depth: int = 20):
        self.exchange = exchange
        self.symbol = symbol
        self.depth = depth
        self.bids: Dict[Decimal, Decimal] = {}  # price -> quantity
        self.asks: Dict[Decimal, Decimal] = {}
        self.last_update: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def apply_update(self, update: OrderBookUpdate):
        """Apply order book update"""
        async with self._lock:
            if update.is_snapshot:
                # Full snapshot - replace everything
                self.bids.clear()
                self.asks.clear()
                for price, qty in update.bids:
                    if qty > 0:
                        self.bids[price] = qty
                for price, qty in update.asks:
                    if qty > 0:
                        self.asks[price] = qty
            else:
                # Delta update
                for price, qty in update.bids:
                    if qty > 0:
                        self.bids[price] = qty
                    elif price in self.bids:
                        del self.bids[price]

                for price, qty in update.asks:
                    if qty > 0:
                        self.asks[price] = qty
                    elif price in self.asks:
                        del self.asks[price]

            self.last_update = update.timestamp

    def get_top_bids(self, n: int = None) -> List[tuple]:
        """Get top n bids (highest prices)"""
        n = n or self.depth
        sorted_bids = sorted(self.bids.items(), key=lambda x: x[0], reverse=True)
        return sorted_bids[:n]

    def get_top_asks(self, n: int = None) -> List[tuple]:
        """Get top n asks (lowest prices)"""
        n = n or self.depth
        sorted_asks = sorted(self.asks.items(), key=lambda x: x[0])
        return sorted_asks[:n]

    @property
    def best_bid(self) -> Optional[tuple]:
        """Get best bid (highest)"""
        bids = self.get_top_bids(1)
        return bids[0] if bids else None

    @property
    def best_ask(self) -> Optional[tuple]:
        """Get best ask (lowest)"""
        asks = self.get_top_asks(1)
        return asks[0] if asks else None

    @property
    def spread(self) -> Optional[Decimal]:
        """Get current spread"""
        bid = self.best_bid
        ask = self.best_ask
        if bid and ask:
            return ask[0] - bid[0]
        return None

    @property
    def spread_bps(self) -> Optional[Decimal]:
        """Get spread in basis points"""
        bid = self.best_bid
        ask = self.best_ask
        if bid and ask and bid[0] > 0:
            return (ask[0] - bid[0]) / bid[0] * Decimal("10000")
        return None


class WebSocketManager:
    """
    Central WebSocket manager for all exchanges

    Features:
    - Multi-exchange support
    - Unified data interface
    - Connection health monitoring
    - Local order book management
    - Arbitrage opportunity detection
    """

    def __init__(self):
        self._handlers: Dict[str, WebSocketHandler] = {}
        self._order_books: Dict[str, Dict[str, LocalOrderBook]] = defaultdict(dict)
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)

    def add_exchange(self, handler: WebSocketHandler):
        """Add exchange WebSocket handler"""
        self._handlers[handler.exchange] = handler

        # Register callbacks
        handler.on_orderbook(self._on_orderbook_update)
        handler.on_trade(self._on_trade_update)
        handler.on_ticker(self._on_ticker_update)

        logger.info(f"Added WebSocket handler for {handler.exchange}")

    async def start(self):
        """Start all WebSocket connections"""
        self._running = True

        for name, handler in self._handlers.items():
            task = asyncio.create_task(self._run_handler(handler))
            self._tasks.append(task)

        logger.info(f"Started {len(self._handlers)} WebSocket handlers")

    async def stop(self):
        """Stop all WebSocket connections"""
        self._running = False

        for task in self._tasks:
            task.cancel()

        for handler in self._handlers.values():
            await handler.disconnect()

        self._tasks.clear()
        logger.info("All WebSocket handlers stopped")

    async def subscribe_orderbook(self, exchange: str, symbols: List[str]):
        """Subscribe to order book updates"""
        handler = self._handlers.get(exchange)
        if handler:
            await handler.subscribe(StreamType.ORDERBOOK, symbols)

            # Initialize local order books
            for symbol in symbols:
                self._order_books[exchange][symbol] = LocalOrderBook(
                    exchange=exchange,
                    symbol=symbol
                )

    async def subscribe_trades(self, exchange: str, symbols: List[str]):
        """Subscribe to trade updates"""
        handler = self._handlers.get(exchange)
        if handler:
            await handler.subscribe(StreamType.TRADE, symbols)

    async def subscribe_tickers(self, exchange: str, symbols: List[str]):
        """Subscribe to ticker updates"""
        handler = self._handlers.get(exchange)
        if handler:
            await handler.subscribe(StreamType.TICKER, symbols)

    def on_arbitrage_opportunity(
        self,
        callback: Callable[[Dict], Coroutine]
    ):
        """Register callback for arbitrage opportunities"""
        self._callbacks["arbitrage"].append(callback)

    def get_order_book(self, exchange: str, symbol: str) -> Optional[LocalOrderBook]:
        """Get local order book"""
        return self._order_books.get(exchange, {}).get(symbol)

    def get_best_prices(self, symbol: str) -> Dict[str, Dict]:
        """Get best bid/ask from all exchanges for a symbol"""
        prices = {}

        for exchange, books in self._order_books.items():
            book = books.get(symbol)
            if book:
                bid = book.best_bid
                ask = book.best_ask
                if bid and ask:
                    prices[exchange] = {
                        "bid": bid[0],
                        "bid_qty": bid[1],
                        "ask": ask[0],
                        "ask_qty": ask[1],
                        "spread_bps": book.spread_bps,
                        "last_update": book.last_update
                    }

        return prices

    def get_connection_status(self) -> Dict[str, Dict]:
        """Get connection status for all handlers"""
        status = {}

        for name, handler in self._handlers.items():
            status[name] = {
                "state": handler.state.value,
                "connected_at": handler.metrics.connected_at.isoformat() if handler.metrics.connected_at else None,
                "messages_received": handler.metrics.messages_received,
                "reconnect_count": handler.metrics.reconnect_count,
                "errors": handler.metrics.errors,
                "subscriptions": len(handler._subscriptions)
            }

        return status

    async def _run_handler(self, handler: WebSocketHandler):
        """Run a WebSocket handler"""
        while self._running:
            try:
                await handler.connect()
                await handler.run()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Handler {handler.exchange} error: {e}")
                await asyncio.sleep(5)

    async def _on_orderbook_update(self, update: OrderBookUpdate):
        """Handle order book update"""
        book = self._order_books.get(update.exchange, {}).get(update.symbol)
        if book:
            await book.apply_update(update)

            # Check for arbitrage opportunities
            await self._check_arbitrage(update.symbol)

    async def _on_trade_update(self, update: TradeUpdate):
        """Handle trade update"""
        for callback in self._callbacks.get("trade", []):
            try:
                await callback(update)
            except Exception as e:
                logger.error(f"Trade callback error: {e}")

    async def _on_ticker_update(self, update: TickerUpdate):
        """Handle ticker update"""
        for callback in self._callbacks.get("ticker", []):
            try:
                await callback(update)
            except Exception as e:
                logger.error(f"Ticker callback error: {e}")

    async def _check_arbitrage(self, symbol: str):
        """Check for arbitrage opportunities across exchanges"""
        prices = self.get_best_prices(symbol)

        if len(prices) < 2:
            return

        exchanges = list(prices.keys())

        for i, buy_ex in enumerate(exchanges):
            for sell_ex in exchanges[i + 1:]:
                buy_price = prices[buy_ex]["ask"]
                sell_price = prices[sell_ex]["bid"]

                if sell_price > buy_price:
                    spread_bps = (sell_price - buy_price) / buy_price * Decimal("10000")

                    opportunity = {
                        "symbol": symbol,
                        "buy_exchange": buy_ex,
                        "sell_exchange": sell_ex,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "spread_bps": float(spread_bps),
                        "buy_quantity": prices[buy_ex]["ask_qty"],
                        "sell_quantity": prices[sell_ex]["bid_qty"],
                        "timestamp": datetime.now(timezone.utc)
                    }

                    for callback in self._callbacks.get("arbitrage", []):
                        try:
                            await callback(opportunity)
                        except Exception as e:
                            logger.error(f"Arbitrage callback error: {e}")

                # Check reverse direction
                buy_price = prices[sell_ex]["ask"]
                sell_price = prices[buy_ex]["bid"]

                if sell_price > buy_price:
                    spread_bps = (sell_price - buy_price) / buy_price * Decimal("10000")

                    opportunity = {
                        "symbol": symbol,
                        "buy_exchange": sell_ex,
                        "sell_exchange": buy_ex,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "spread_bps": float(spread_bps),
                        "buy_quantity": prices[sell_ex]["ask_qty"],
                        "sell_quantity": prices[buy_ex]["bid_qty"],
                        "timestamp": datetime.now(timezone.utc)
                    }

                    for callback in self._callbacks.get("arbitrage", []):
                        try:
                            await callback(opportunity)
                        except Exception as e:
                            logger.error(f"Arbitrage callback error: {e}")


# Factory function
def create_websocket_manager(exchanges: List[str]) -> WebSocketManager:
    """Create WebSocket manager with specified exchanges"""
    manager = WebSocketManager()

    for exchange in exchanges:
        if exchange == "binance":
            manager.add_exchange(BinanceWebSocket())
        elif exchange == "mexc":
            manager.add_exchange(MEXCWebSocket())
        elif exchange == "kucoin":
            manager.add_exchange(KuCoinWebSocket())
        else:
            logger.warning(f"Unknown exchange: {exchange}")

    return manager


__all__ = [
    "ConnectionState",
    "StreamType",
    "OrderBookUpdate",
    "TradeUpdate",
    "TickerUpdate",
    "ConnectionMetrics",
    "WebSocketHandler",
    "BinanceWebSocket",
    "MEXCWebSocket",
    "KuCoinWebSocket",
    "LocalOrderBook",
    "WebSocketManager",
    "create_websocket_manager"
]
