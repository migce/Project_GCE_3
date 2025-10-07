from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Iterable, Set

from django.db.models import Q

from ..models import (
    TradingSystem,
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


@dataclass
class Changed:
    ref: 'IndicatorRef'


@dataclass
class PosCount:
    side: str  # 'BUY' or 'SELL'


@dataclass
class HasPos:
    side: str  # 'BUY' or 'SELL'


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
    # HAS_BUY()/HAS_SELL() and COUNT_BUY()/COUNT_SELL()
    if lx.take('HAS_BUY'):
        lx._skip_ws();
        if lx._peek() == '(':
            lx._advance(1)
            lx._skip_ws()
            if lx._peek() != ')':
                raise ParseError('Expected ) in HAS_BUY()')
            lx._advance(1)
        return HasPos('BUY')
    if lx.take('HAS_SELL'):
        lx._skip_ws();
        if lx._peek() == '(':
            lx._advance(1)
            lx._skip_ws()
            if lx._peek() != ')':
                raise ParseError('Expected ) in HAS_SELL()')
            lx._advance(1)
        return HasPos('SELL')
    if lx.take('COUNT_BUY'):
        lx._skip_ws();
        if lx._peek() == '(':
            lx._advance(1)
            lx._skip_ws()
            if lx._peek() != ')':
                raise ParseError('Expected ) in COUNT_BUY()')
            lx._advance(1)
        return PosCount('BUY')
    if lx.take('COUNT_SELL'):
        lx._skip_ws();
        if lx._peek() == '(':
            lx._advance(1)
            lx._skip_ws()
            if lx._peek() != ')':
                raise ParseError('Expected ) in COUNT_SELL()')
            lx._advance(1)
        return PosCount('SELL')
    # CHANGED(ind)
    if lx.take('CHANGED'):
        lx._skip_ws()
        if lx._peek() != '(':
            raise ParseError('Expected ( after CHANGED')
        lx._advance(1)
        ref = parse_value(lx)
        lx._skip_ws()
        if lx._peek() != ')':
            raise ParseError('Expected ) in CHANGED()')
        lx._advance(1)
        return Changed(ref)
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
    if isinstance(node, PosCount):
        try:
            fn = getattr(env_get, 'pos_count')
            return int(fn(node.side))
        except Exception:
            return 0
    if isinstance(node, HasPos):
        try:
            fn = getattr(env_get, 'pos_count')
            return bool(int(fn(node.side)) > 0)
        except Exception:
            return False
    if isinstance(node, Changed):
        # env_get may carry attribute 'changed' to resolve CHANGED queries
        try:
            changed_fn = getattr(env_get, 'changed')
        except Exception:
            changed_fn = None
        if changed_fn is None:
            return False
        return bool(changed_fn(node.ref.name, node.ref.level))
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

    # Global-only mode
    return _generate_signals_global(system, settings, limit_bars)


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

    # Global feed diagnostics only
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
        # Prefer dt for stable equality with legacy Bar.dt mapping
        return b.dt

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

    # Global-only: we no longer map to local Bar/TimeFrame

    events: List[SignalEvent] = []
    # Pre-separate base and non-base requirement keys
    base_names = sorted({n for (n, lvl) in normalized_req if lvl == base_level})
    nonbase_keys = [(n, lvl) for (n, lvl) in normalized_req if lvl != base_level]
    # Keep last seen value per non-base indicator across base bars to compute CHANGED reliably
    nonbase_last_value: Dict[Tuple[str, int], Optional[int]] = {}

    # --- Initialize position counters from persisted SignalEvents up to the first bar
    pos_count: Dict[str, int] = {'BUY': 0, 'SELL': 0}
    first_time = btime_mb(bars[0])
    try:
        seed_qs = SignalEvent.objects.filter(trading_system=system, level=base_level, event_time__lt=first_time)
        # Prefer matching feed if bound
        seed_bind = TradingSystemTFBinding.objects.filter(trading_system=system, level=base_level).select_related('feed').first()
        if seed_bind and getattr(seed_bind, 'feed_id', None):
            seed_qs = seed_qs.filter(feed_id=seed_bind.feed_id)
        for ev in seed_qs.order_by('event_time'):
            side = 'BUY' if ev.direction == 'BUY' else 'SELL'
            if ev.action == 'OPEN':
                pos_count[side] = pos_count.get(side, 0) + 1
            else:
                pos_count[side] = max(0, pos_count.get(side, 0) - 1)
    except Exception:
        pass

    for mb in bars:
        tnow = btime_mb(mb)
        for cur in series.values():
            cur.advance_to(tnow)
        curvals = base_map.get(mb.id, {})

        # CHANGED map for base indicators at this bar (compare with previous base value)
        changed_base: Dict[str, bool] = {}
        for n in base_names:
            prev = base_hist[n][-1] if base_hist[n] else None
            curv = curvals.get(n)
            changed_base[n] = (prev is not None) and (curv != prev)
        # Append current base values after computing changed
        for n in names:
            base_hist[n].append(curvals.get(n))

        # CHANGED map for non-base: true if current value differs from last snapshot
        # across base bars (do not require timestamp equality).
        changed_nonbase: Dict[Tuple[str, int], bool] = {}
        for (n, lvl) in nonbase_keys:
            cur = series.get((n, lvl))
            key = (n, lvl)
            if not cur:
                changed_nonbase[key] = False
                continue
            curr_val = cur.value(0)
            prev_val = nonbase_last_value.get(key)
            # Follow base-level semantics: CHANGED is true only if a previous value exists and differs
            changed_nonbase[key] = (prev_val is not None) and (curr_val != prev_val)
            # Update snapshot for the next base bar
            nonbase_last_value[key] = curr_val

        def env_get(name: str, level: Optional[int], lag: int) -> Optional[int]:
            return _env_get_global(name, level, lag, base_hist, base_level, series)

        def _changed(name: str, level: Optional[int]) -> bool:
            lvl = level or base_level
            if lvl == base_level:
                return bool(changed_base.get(name))
            return bool(changed_nonbase.get((name, lvl)))
        setattr(env_get, 'changed', _changed)

        def _pos_count(side: str) -> int:
            return int(pos_count.get(side, 0))
        setattr(env_get, 'pos_count', _pos_count)

        for r in rules:
            ok = bool(_eval(r.condition, env_get))
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
                    # Suppress CLOSE when no open positions on that side
                    if act_kind == 'CLOSE' and pos_count.get(direction, 0) <= 0:
                        continue
                    # Snapshot indicator values used for this decision
                    snapshot: Dict[str, Optional[int]] = {}
                    for name, lvl in normalized_req:
                        eff = lvl
                        key = f"{name}[L{eff}]"
                        if eff == base_level:
                            snapshot[key] = base_hist.get(name, [None])[-1]
                        else:
                            cur = series.get((name, eff))
                            snapshot[key] = cur.value(0) if cur else None
                    events.append(SignalEvent(
                        trading_system=system,
                        timeframe=None,
                        level=base_level,
                        feed=base_feed,
                        # bar link removed in global-only mode
                        direction=direction,
                        rule_text=str(r),
                        event_time=btime_mb(mb),
                        action=act_kind,
                        ind_values=snapshot,
                    ))
                    # Update local position counters to reflect generated stream
                    if act_kind == 'OPEN':
                        pos_count[direction] = pos_count.get(direction, 0) + 1
                    else:
                        pos_count[direction] = max(0, pos_count.get(direction, 0) - 1)
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
