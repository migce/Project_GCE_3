from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Iterable, Set

from django.db.models import Q

from ..models import (
    TradingSystem,
    TimeFrame,
    Bar,
    IndicatorDefinition,
    IndicatorValue,
    TradingSystemSignalSettings,
    SignalEvent,
)
from ..models import (
    DataFeed,
    MarketBar,
    MarketIndicatorDef,
    MarketIndicatorValue,
    TradingSystemTFBinding,
)


# -----------------------------
# DSL parsing
# -----------------------------

@dataclass
class IndicatorRef:
    name: str
    level: Optional[int]  # None => base level
    lag: int = 0


@dataclass
class Compare:
    left: Any
    op: str
    right: Any


@dataclass
class Not:
    expr: Any


@dataclass
class And:
    left: Any
    right: Any


@dataclass
class Or:
    left: Any
    right: Any


@dataclass
class Rule:
    condition: Any
    action_then: List[str]  # list of actions
    action_else: Optional[List[str]] = None


class ParseError(Exception):
    pass


class Lexer:
    def __init__(self, s: str):
        self.s = s
        self.i = 0

    def _peek(self) -> str:
        return self.s[self.i:self.i+1]

    def _advance(self, n=1):
        self.i += n

    def _skip_ws(self):
        while self._peek() and self._peek().isspace():
            self._advance()

    def take(self, pat: str) -> bool:
        if self.s[self.i:].upper().startswith(pat):
            self._advance(len(pat))
            return True
        return False

    def number(self) -> Optional[float]:
        j = self.i
        dot = False
        while self._peek() and (self._peek().isdigit() or (self._peek() == '.' and not dot)):
            if self._peek() == '.':
                dot = True
            self._advance()
        if self.i == j:
            return None
        return float(self.s[j:self.i])

    def ident(self) -> Optional[str]:
        j = self.i
        p = self._peek()
        if not (p.isalpha() or p == '_'):
            return None
        while self._peek() and (self._peek().isalnum() or self._peek() in '_'):
            self._advance()
        return self.s[j:self.i]


def parse_rules(text: str) -> List[Rule]:
    """Parse multi-line rules. Supports full-line comments starting with #.

    A line is ignored if, after trimming whitespace, it is empty or starts with '#'.
    """
    lines: List[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith('#'):
            continue
        lines.append(s)
    return [parse_rule(line) for line in lines]


def parse_rule(line: str) -> Rule:
    lx = Lexer(line)
    lx._skip_ws()
    if not lx.take('IF'):
        raise ParseError('Rule must start with IF')
    cond = parse_expr(lx)
    lx._skip_ws()
    if not lx.take('THEN'):
        raise ParseError('Expected THEN')
    action_then = parse_action_list(lx)
    lx._skip_ws()
    action_else = None
    if lx.take('ELSE'):
        action_else = parse_action_list(lx)
    return Rule(cond, action_then, action_else)


def parse_action(lx: Lexer) -> str:
    lx._skip_ws()
    for act in (
        'BUY', 'SELL', 'NONE',
        'CLOSE_LONG', 'CLOSE_SHORT',
        'CLOSE_BUY', 'CLOSE_SELL',
        'EXIT_LONG', 'EXIT_SHORT',
    ):
        if lx.take(act):
            return act
    raise ParseError('Unknown action (expected BUY/SELL/NONE)')


def parse_action_list(lx: Lexer) -> List[str]:
    """Parse one or more actions.

    Supports either a single action token or a block in braces with separators:
    THEN { CLOSE_SHORT; BUY } or THEN { CLOSE_SHORT, BUY } or THEN { CLOSE_SHORT + BUY }
    """
    lx._skip_ws()
    actions: List[str] = []
    if lx._peek() == '{':
        lx._advance(1)
        while True:
            lx._skip_ws()
            actions.append(parse_action(lx))
            lx._skip_ws()
            ch = lx._peek()
            if ch == '}':
                lx._advance(1)
                break
            if ch in ',;':
                lx._advance(1)
                continue
            if lx.take('+'):
                continue
            raise ParseError('Expected , ; + or } in action list')
    else:
        actions.append(parse_action(lx))
    return actions


def parse_expr(lx: Lexer):
    lx._skip_ws()
    node = parse_term(lx)
    lx._skip_ws()
    while lx.take('OR'):
        rhs = parse_term(lx)
        node = Or(node, rhs)
        lx._skip_ws()
    return node


def parse_term(lx: Lexer):
    lx._skip_ws()
    node = parse_factor(lx)
    lx._skip_ws()
    while lx.take('AND'):
        rhs = parse_factor(lx)
        node = And(node, rhs)
        lx._skip_ws()
    return node


def parse_factor(lx: Lexer):
    lx._skip_ws()
    if lx.take('NOT'):
        return Not(parse_factor(lx))
    if lx._peek() == '(':
        lx._advance(1)
        node = parse_expr(lx)
        lx._skip_ws()
        if lx._peek() != ')':
            raise ParseError('Expected )')
        lx._advance(1)
        return node
    # function or comparison atom
    # changed(
    if lx.take('CHANGED'):
        lx._skip_ws()
        if lx._peek() != '(':
            raise ParseError('Expected ( after CHANGED')
        lx._advance(1)
        ref = parse_value(lx)
        lx._skip_ws()
        if lx._peek() != ')':
            raise ParseError('Expected ) in changed()')
        lx._advance(1)
        # changed(x) => prev(x) != x
        return Compare(IndicatorRef(ref.name, ref.level, max(ref.lag, 1)), '!=', IndicatorRef(ref.name, ref.level, 0))
    # prev(x[,n])
    if lx.take('PREV'):
        lx._skip_ws()
        if lx._peek() != '(':
            raise ParseError('Expected ( after PREV')
        lx._advance(1)
        ref = parse_value(lx)
        lag = 1
        lx._skip_ws()
        if lx._peek() == ',':
            lx._advance(1)
            lx._skip_ws()
            num = lx.number()
            if num is None:
                raise ParseError('Expected number for prev lag')
            lag = int(num)
        lx._skip_ws()
        if lx._peek() != ')':
            raise ParseError('Expected ) in prev()')
        lx._advance(1)
        return IndicatorRef(ref.name, ref.level, lag)
    # comparison
    left = parse_value(lx)
    lx._skip_ws()
    op = None
    for cand in ('>=', '<=', '!=', '==', '>', '<'):
        if lx.take(cand):
            op = cand
            break
    if op is None:
        raise ParseError('Expected comparison operator')
    right = parse_value(lx)
    return Compare(left, op, right)


def parse_value(lx: Lexer):
    lx._skip_ws()
    # number
    num = lx.number()
    if num is not None:
        return num
    # indicator ref: NAME [Lk] [n]
    ident = lx.ident()
    if not ident:
        raise ParseError('Expected value')
    level = None
    lag = 0
    lx._skip_ws()
    if lx._peek() == '[':
        # [Lk]
        lx._advance(1)
        lx._skip_ws()
        if lx.take('L'):
            num = lx.number()
            if num is None:
                raise ParseError('Expected level number after L')
            level = int(num)
        else:
            raise ParseError('Expected Lx in first []')
        lx._skip_ws()
        if lx._peek() != ']':
            raise ParseError('Expected ]')
        lx._advance(1)
        lx._skip_ws()
        # optional [n]
        if lx._peek() == '[':
            lx._advance(1)
            lx._skip_ws()
            num = lx.number()
            if num is None:
                raise ParseError('Expected lag number in []')
            lag = int(num)
            lx._skip_ws()
            if lx._peek() != ']':
                raise ParseError('Expected ] for lag')
            lx._advance(1)
    return IndicatorRef(ident, level, lag)


# -----------------------------
# Evaluation
# -----------------------------

@dataclass
class SeriesCursor:
    # Time-ordered pairs for an indicator at a given level
    times: List[Any]
    values: List[Optional[int]]
    idx: int = -1  # last position with time <= current base time

    def advance_to(self, t):
        while self.idx + 1 < len(self.times) and self.times[self.idx + 1] <= t:
            self.idx += 1

    def value(self, lag: int) -> Optional[int]:
        i = self.idx - lag
        if i < 0 or i >= len(self.values):
            return None
        return self.values[i]


def _collect_requirements(rules: List[Rule]) -> Set[Tuple[str, Optional[int]]]:
    req: Set[Tuple[str, Optional[int]]] = set()

    def visit(node):
        if isinstance(node, IndicatorRef):
            req.add((node.name, node.level))
        elif isinstance(node, (And, Or)):
            visit(node.left); visit(node.right)
        elif isinstance(node, Not):
            visit(node.expr)
        elif isinstance(node, Compare):
            visit(node.left); visit(node.right)

    for r in rules:
        visit(r.condition)
    return req


def _eval(node, env_get):
    if isinstance(node, IndicatorRef):
        return env_get(node.name, node.level, node.lag)
    if isinstance(node, (int, float)):
        return node
    if isinstance(node, Not):
        v = _eval(node.expr, env_get)
        return not bool(v)
    if isinstance(node, And):
        return bool(_eval(node.left, env_get)) and bool(_eval(node.right, env_get))
    if isinstance(node, Or):
        return bool(_eval(node.left, env_get)) or bool(_eval(node.right, env_get))
    if isinstance(node, Compare):
        l = _eval(node.left, env_get)
        r = _eval(node.right, env_get)
        if l is None or r is None:
            return False
        if node.op == '==': return l == r
        if node.op == '!=': return l != r
        if node.op == '>': return l > r
        if node.op == '<': return l < r
        if node.op == '>=': return l >= r
        if node.op == '<=': return l <= r
    return False


def generate_signals_for_system(system: TradingSystem, limit_bars: int = 500) -> List[SignalEvent]:
    """Parse system rules and generate SignalEvent objects (not saved) for last N bars.

    If system.signal_settings.use_global_feed is True, reads series from global feed layer using
    TradingSystemTFBinding for TF level routing; otherwise uses legacy per-system Bar/Indicator tables.
    """
    # Load settings
    try:
        settings = system.signal_settings
    except TradingSystemSignalSettings.DoesNotExist:
        return []
    if not settings.signal_logic:
        return []

    if getattr(settings, 'use_global_feed', False):
        return _generate_signals_global(system, settings, limit_bars)

    rules = parse_rules(settings.signal_logic)

    # Determine base timeframe by level
    base_level = settings.signal_base_tf_level or 1
    base_tf = TimeFrame.objects.filter(trading_system=system, level=base_level).first()
    if not base_tf:
        return []

    # Collect requirements (indicator name + level), include base level for indicators without explicit level
    req = _collect_requirements(rules)
    normalized_req: Set[Tuple[str, int]] = set()
    for name, lvl in req:
        normalized_req.add((name, lvl or base_level))

    # All indicator names used
    names = sorted({name for name, _ in normalized_req})
    defs = {d.name: d for d in IndicatorDefinition.objects.filter(trading_system=system, name__in=names)}
    # If no indicator definitions yet, nothing to do
    if not defs:
        return []

    # Load last N base bars (most recent), then evaluate in chronological order
    bars_desc = list(Bar.objects.filter(timeframe=base_tf).order_by('-dt')[:limit_bars])
    bars = list(reversed(bars_desc))
    if not bars:
        return []
    # Prefer server time for alignment with external charts; fallback to dt
    def btime(b: Bar):
        return getattr(b, 'dt_server', None) or b.dt
    bar_times = [btime(b) for b in bars]

    # Preload indicator series per (name, level)
    series: Dict[Tuple[str, int], SeriesCursor] = {}
    for name, lvl in normalized_req:
        ind = defs.get(name)
        if not ind:
            continue
        qs = IndicatorValue.objects.filter(
            indicator=ind,
            bar__timeframe__trading_system=system,
            bar__timeframe__level=lvl,
        ).select_related('bar').order_by('bar__dt')
        times = [(getattr(iv.bar, 'dt_server', None) or iv.bar.dt) for iv in qs]
        vals = [iv.value_int for iv in qs]
        series[(name, lvl)] = SeriesCursor(times, vals)

    # For base TF, we also need current and historical values on each bar for used indicators
    base_series: Dict[str, List[Optional[int]]] = {name: [] for name in names}
    qs_base = IndicatorValue.objects.filter(
        indicator__trading_system=system,
        indicator__name__in=names,
        bar__timeframe=base_tf,
        bar__in=[b.id for b in bars],
    ).select_related('bar', 'indicator').order_by('bar__dt')
    # Build map of bar_id -> {name: value}
    base_map: Dict[int, Dict[str, Optional[int]]] = {}
    for iv in qs_base:
        base_map.setdefault(iv.bar_id, {})[iv.indicator.name] = iv.value_int
    base_hist: Dict[str, List[Optional[int]]] = {n: [] for n in names}

    # Helper to get value
    def env_get(name: str, level: Optional[int], lag: int) -> Optional[int]:
        lvl = level or base_level
        if lvl == base_level:
            hist = base_hist.get(name)
            if hist is None:
                return None
            i = len(hist) - 1 - lag
            if i < 0 or i >= len(hist):
                return None
            return hist[i]
        cur = series.get((name, lvl))
        if not cur:
            return None
        return cur.value(lag)

    # Evaluate rules
    events: List[SignalEvent] = []
    for b in bars:
        # advance non-base series to current bar server time
        tnow = btime(b)
        for cur in series.values():
            cur.advance_to(tnow)
        # append base values at this bar
        curvals = base_map.get(b.id, {})
        for n in names:
            base_hist[n].append(curvals.get(n))

        for r in rules:
            ok = bool(_eval(r.condition, env_get))
            actions = r.action_then if ok else (r.action_else or [])
            for action in actions:
                if action in ('BUY', 'SELL', 'CLOSE_LONG', 'CLOSE_SHORT', 'CLOSE_BUY', 'CLOSE_SELL', 'EXIT_LONG', 'EXIT_SHORT'):
                    # Map action to direction + open/close
                    if action in ('BUY', 'SELL'):
                        direction = action
                        act_kind = 'OPEN'
                    elif action in ('CLOSE_LONG', 'CLOSE_BUY', 'EXIT_LONG'):
                        direction = 'BUY'
                        act_kind = 'CLOSE'
                    elif action in ('CLOSE_SHORT', 'CLOSE_SELL', 'EXIT_SHORT'):
                        direction = 'SELL'
                        act_kind = 'CLOSE'
                    else:
                        continue
                    events.append(SignalEvent(
                        trading_system=system,
                        timeframe=base_tf,
                        bar=b,
                        direction=direction,
                        rule_text=str(r),
                        event_time=b.dt_server or b.dt,
                        action=act_kind,
                    ))
    return events


def diagnose_system_for_signals(system: TradingSystem, limit_bars: int = 500) -> List[str]:
    """Return human-readable diagnostics explaining why signals may not be produced.

    This does not raise; it gives actionable hints (missing bindings, no bars, missing indicators, etc.).
    """
    msgs: List[str] = []
    try:
        settings = system.signal_settings
    except TradingSystemSignalSettings.DoesNotExist:
        return ["Signal settings not configured"]
    if not (settings.signal_logic or '').strip():
        msgs.append('Empty signal_logic')
        return msgs

    try:
        rules = parse_rules(settings.signal_logic)
    except Exception as e:
        msgs.append(f'Rule parse error: {e}')
        return msgs

    req = _collect_requirements(rules)
    base_level = settings.signal_base_tf_level or 1

    if getattr(settings, 'use_global_feed', False):
        # Global feed diagnostics
        base_binding = TradingSystemTFBinding.objects.filter(trading_system=system, level=base_level).select_related('feed').first()
        if not base_binding:
            return [f'No TF binding for base level L{base_level}']
        base_feed = base_binding.feed
        base_bar_cnt = MarketBar.objects.filter(feed=base_feed).count()
        if base_bar_cnt == 0:
            msgs.append(f'No MarketBar for base feed {base_feed}')
        names = sorted({name for name, _ in req})
        # Check presence of indicator defs per referenced level
        missing_defs: List[str] = []
        for name, lvl in req:
            the_level = lvl or base_level
            bind = TradingSystemTFBinding.objects.filter(trading_system=system, level=the_level).select_related('feed').first()
            if not bind:
                msgs.append(f'No TF binding for L{the_level} (needed by {name})')
                continue
            if not MarketIndicatorDef.objects.filter(feed=bind.feed, name=name).exists():
                missing_defs.append(f'{name}@L{the_level} (feed {bind.feed})')
        if missing_defs:
            msgs.append('Missing indicator defs: ' + ', '.join(missing_defs[:6]) + (' …' if len(missing_defs) > 6 else ''))
        # Check base series values in window
        bars_desc = list(MarketBar.objects.filter(feed=base_feed).order_by('-dt')[:limit_bars])
        bars = list(reversed(bars_desc))
        if bars:
            dts = [b.dt for b in bars]
            base_names = [n for (n, lvl) in req if (lvl or base_level) == base_level]
            if base_names:
                defs = list(MarketIndicatorDef.objects.filter(feed=base_feed, name__in=base_names))
                val_cnt = MarketIndicatorValue.objects.filter(indicator__in=defs, bar__dt__in=dts).count()
                if val_cnt == 0:
                    msgs.append('No indicator values for base feed in the evaluated window')
        return msgs or ['No rule condition matched in the evaluated window']
    else:
        # Legacy diagnostics
        base_tf = TimeFrame.objects.filter(trading_system=system, level=base_level).first()
        if not base_tf:
            return [f'No TimeFrame with level L{base_level}']
        bar_cnt = Bar.objects.filter(timeframe=base_tf).count()
        if bar_cnt == 0:
            msgs.append('No Bars on base timeframe')
        names = sorted({name for name, _ in req})
        missing_defs: List[str] = []
        for name in names:
            if not IndicatorDefinition.objects.filter(trading_system=system, name=name).exists():
                missing_defs.append(name)
        if missing_defs:
            msgs.append('Missing indicator defs: ' + ', '.join(missing_defs[:6]) + (' …' if len(missing_defs) > 6 else ''))
        return msgs or ['No rule condition matched in the evaluated window']


def _generate_signals_global(system: TradingSystem, settings: TradingSystemSignalSettings, limit_bars: int) -> List[SignalEvent]:
    """Global-feed backed signal generation."""
    try:
        rules = parse_rules(settings.signal_logic)
    except ParseError:
        return []

    base_level = settings.signal_base_tf_level or 1
    base_binding = TradingSystemTFBinding.objects.filter(trading_system=system, level=base_level).select_related('feed__tfcode', 'feed__instrument').first()
    if not base_binding:
        return []
    base_feed = base_binding.feed

    # Collect requirements
    req = _collect_requirements(rules)
    normalized_req: Set[Tuple[str, int]] = set()
    for name, lvl in req:
        normalized_req.add((name, (lvl or base_level)))
    names = sorted({name for name, _ in normalized_req})

    # Load last N base bars from MarketBar
    bars_desc = list(MarketBar.objects.filter(feed=base_feed).order_by('-dt')[:limit_bars])
    bars = list(reversed(bars_desc))
    if not bars:
        return []

    def btime_mb(b: MarketBar):
        return getattr(b, 'dt_server', None) or b.dt

    bar_times = [btime_mb(b) for b in bars]

    # Prepare cursor series for non-base levels
    # Map TF level -> feed
    feed_by_level: Dict[int, DataFeed] = {}
    for _, lvl in normalized_req:
        if lvl == base_level:
            continue
        if lvl not in feed_by_level:
            b = TradingSystemTFBinding.objects.filter(trading_system=system, level=lvl).select_related('feed').first()
            if not b:
                # requirement references unbound level; skip entire run
                return []
            feed_by_level[lvl] = b.feed

    # Indicator definitions per feed
    defs_per_feed: Dict[Tuple[DataFeed, str], MarketIndicatorDef] = {}
    for name, lvl in normalized_req:
        f = base_feed if lvl == base_level else feed_by_level.get(lvl)
        if not f:
            return []
        d = MarketIndicatorDef.objects.filter(feed=f, name=name).first()
        if d:
            defs_per_feed[(f, name)] = d
    if not defs_per_feed:
        return []

    # Build series for non-base levels
    series: Dict[Tuple[str, int], SeriesCursor] = {}
    for name, lvl in normalized_req:
        if lvl == base_level:
            continue
        f = feed_by_level.get(lvl)
        ind = defs_per_feed.get((f, name)) if f else None
        if not ind:
            continue
        qs = MarketIndicatorValue.objects.filter(indicator=ind).select_related('bar').order_by('bar__dt')
        times = [(getattr(iv.bar, 'dt_server', None) or iv.bar.dt) for iv in qs]
        vals = [iv.value_int for iv in qs]
        series[(name, lvl)] = SeriesCursor(times, vals)

    # Base series values over our base bars window
    base_defs = {name: defs_per_feed.get((base_feed, name)) for name in names}
    base_map: Dict[int, Dict[str, Optional[int]]] = {}
    qs_base = MarketIndicatorValue.objects.filter(
        indicator__in=[d for d in base_defs.values() if d],
        bar__in=[b.id for b in bars],
    ).select_related('bar', 'indicator').order_by('bar__dt')
    for iv in qs_base:
        base_map.setdefault(iv.bar_id, {})[iv.indicator.name] = iv.value_int
    base_hist: Dict[str, List[Optional[int]]] = {n: [] for n in names}

    # Resolve TimeFrame for events (base level)
    base_tf = TimeFrame.objects.filter(trading_system=system, level=base_level).first()

    # Optionally map MarketBar.dt to local Bar for event.bar
    # Build local bar map by dt if timeframe available
    local_bar_map: Dict[Any, Bar] = {}
    if base_tf:
        dts = [b.dt for b in bars]
        for lb in Bar.objects.filter(timeframe=base_tf, dt__in=dts):
            local_bar_map[lb.dt] = lb

    events: List[SignalEvent] = []
    for mb in bars:
        tnow = btime_mb(mb)
        for cur in series.values():
            cur.advance_to(tnow)
        curvals = base_map.get(mb.id, {})
        for n in names:
            base_hist[n].append(curvals.get(n))

        for r in rules:
            ok = bool(_eval(r.condition, lambda name, level, lag: _env_get_global(name, level, lag, base_hist, base_level, series)))
            actions = r.action_then if ok else (r.action_else or [])
            for action in actions:
                if action in ('BUY', 'SELL', 'CLOSE_LONG', 'CLOSE_SHORT', 'CLOSE_BUY', 'CLOSE_SELL', 'EXIT_LONG', 'EXIT_SHORT'):
                    if action in ('BUY', 'SELL'):
                        direction = action
                        act_kind = 'OPEN'
                    elif action in ('CLOSE_LONG', 'CLOSE_BUY', 'EXIT_LONG'):
                        direction = 'BUY'
                        act_kind = 'CLOSE'
                    else:
                        direction = 'SELL'
                        act_kind = 'CLOSE'
                    ev_bar = local_bar_map.get(mb.dt) if local_bar_map else None
                    events.append(SignalEvent(
                        trading_system=system,
                        timeframe=base_tf if base_tf else TimeFrame.objects.filter(trading_system=system, level=base_level).first(),
                        bar=ev_bar,
                        direction=direction,
                        rule_text=str(r),
                        event_time=btime_mb(mb),
                        action=act_kind,
                    ))
    return events


def _env_get_global(name: str, level: Optional[int], lag: int, base_hist: Dict[str, List[Optional[int]]], base_level: int, series: Dict[Tuple[str, int], SeriesCursor]) -> Optional[int]:
    lvl = level or base_level
    if lvl == base_level:
        hist = base_hist.get(name)
        if hist is None:
            return None
        i = len(hist) - 1 - lag
        if i < 0 or i >= len(hist):
            return None
        return hist[i]
    cur = series.get((name, lvl))
    if not cur:
        return None
    return cur.value(lag)
