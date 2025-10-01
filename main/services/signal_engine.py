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
    action_then: str  # BUY/SELL/NONE
    action_else: Optional[str] = None


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
    # Split by lines with non-empty content
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
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
    action_then = parse_action(lx)
    lx._skip_ws()
    action_else = None
    if lx.take('ELSE'):
        action_else = parse_action(lx)
    return Rule(cond, action_then, action_else)


def parse_action(lx: Lexer) -> str:
    lx._skip_ws()
    for act in ('BUY', 'SELL', 'NONE'):
        if lx.take(act):
            return act
    raise ParseError('Unknown action (expected BUY/SELL/NONE)')


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
    if lx.take('CHANGED') and lx._peek() == '(':
        lx._advance(1)
        ref = parse_value(lx)
        lx._skip_ws()
        if lx._peek() != ')':
            raise ParseError('Expected ) in changed()')
        lx._advance(1)
        # changed(x) => prev(x) != x
        return Compare(IndicatorRef(ref.name, ref.level, max(ref.lag, 1)), '!=', IndicatorRef(ref.name, ref.level, 0))
    # prev(x[,n])
    if lx.take('PREV') and lx._peek() == '(':
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
    """Parse system rules and generate SignalEvent objects (not saved) for last N bars on base TF."""
    # Load settings
    try:
        settings = system.signal_settings
    except TradingSystemSignalSettings.DoesNotExist:
        return []
    if not settings.signal_logic:
        return []

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
            action = r.action_then if ok else (r.action_else or 'NONE')
            if action in ('BUY', 'SELL'):
                events.append(SignalEvent(
                    trading_system=system,
                    timeframe=base_tf,
                    bar=b,
                    direction=action,
                    rule_text=str(r),
                    event_time=b.dt_server or b.dt,
                ))
    return events
