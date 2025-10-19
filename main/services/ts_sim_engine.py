from __future__ import annotations

from typing import Callable, Dict, Any, List
from collections import deque, Counter
from numbers import Number

from django.utils import timezone
from django.db.models import Max

from ..models import (
    TradingSystem,
    TradingSystemTFBinding,
    MarketBar,
    SignalEvent,
    MarketIndicatorDef,
    MarketIndicatorValue,
)


def compute_ts_simulation(system: TradingSystem, base_level: int, start_balance: float, lot_size: float, progress_cb: Callable[[int, str], None] | None = None, spread_pips: float | None = None) -> Dict[str, Any]:
    """Compute trading history KPIs for TradeStation simulation based on persisted SignalEvent.

    Returns a dict with core metrics and last N trades; designed for async usage.
    """
    def report(p: int, msg: str = ''):
        if progress_cb:
            try:
                progress_cb(p, msg)
            except Exception:
                pass

    report(5, 'Loading events')
    qs = SignalEvent.objects.filter(trading_system=system, level=base_level)
    try:
        bind = TradingSystemTFBinding.objects.filter(trading_system=system, level=base_level).select_related('feed').first()
        if bind and bind.feed_id:
            qs = qs.filter(feed_id=bind.feed_id)
    except Exception:
        pass
    evs = list(qs.order_by('event_time'))
    total_events = max(1, len(evs))
    events_from_dt = evs[0].event_time if evs else None
    events_to_dt = evs[-1].event_time if evs else None

    pip_scale = 100 if 'JPY' in (system.symbol or '').upper() else 10000
    open_q = {'BUY': deque(), 'SELL': deque()}
    trades: List[Dict[str, Any]] = []
    wins = 0
    total = 0
    total_pips = 0.0
    # For cycle KPIs
    cycle_uid_open = {}

    def _get_close(ev) -> float | None:
        try:
            if getattr(ev, 'feed_id', None):
                mb = MarketBar.objects.filter(feed_id=ev.feed_id, dt=ev.event_time).only('close').first()
                if mb and mb.close is not None:
                    return float(mb.close)
            lvl = getattr(ev, 'level', None) or getattr(getattr(ev, 'timeframe', None), 'level', None)
            ts = getattr(ev, 'trading_system', None)
            if ts and lvl:
                bind2 = TradingSystemTFBinding.objects.filter(trading_system=ts, level=int(lvl)).select_related('feed').first()
                if bind2:
                    mb = MarketBar.objects.filter(feed=bind2.feed, dt=ev.event_time).only('close').first()
                    if mb and mb.close is not None:
                        return float(mb.close)
        except Exception:
            return None
        return None

    report(15, 'Processing events')
    for i, ev in enumerate(evs, start=1):
        if i % 100 == 0:
            report(15 + int(60 * i / total_events), 'Processing events')
        side = getattr(ev, 'direction', None)
        act = getattr(ev, 'action', 'OPEN')
        if side not in ('BUY', 'SELL'):
            continue
        if act == 'OPEN':
            # Track cycle opened
            uid = getattr(ev, 'cycle_uid', None)
            if uid:
                cycle_uid_open[uid] = ev
            opposite = 'SELL' if side == 'BUY' else 'BUY'
            if open_q[opposite]:
                # Close all opposite positions (reversal system)
                while open_q[opposite]:
                    oe = open_q[opposite].popleft()
                    op = _get_close(oe)
                    cp = _get_close(ev)
                    pnl = None
                    if op is not None and cp is not None:
                        pnl = (cp - op) * pip_scale if oe.direction == 'BUY' else (op - cp) * pip_scale
                        if spread_pips:
                            try:
                                pnl -= float(spread_pips)
                            except Exception:
                                pass
                        total_pips += pnl
                        total += 1
                        if pnl > 0:
                            wins += 1
                    trades.append({'open_time': oe.event_time, 'open_dir': oe.direction, 'open_price': op, 'close_time': ev.event_time, 'close_price': cp, 'pips': pnl, 'cycle_uid': getattr(oe, 'cycle_uid', None) or getattr(ev, 'cycle_uid', None)})
            open_q[side].append(ev)
        else:
            uid = getattr(ev, 'cycle_uid', None)
            if open_q[side]:
                while open_q[side]:
                    oe = open_q[side].popleft()
                    op = _get_close(oe)
                    cp = _get_close(ev)
                    pnl = None
                    if op is not None and cp is not None:
                        pnl = (cp - op) * pip_scale if oe.direction == 'BUY' else (op - cp) * pip_scale
                        if spread_pips:
                            try:
                                pnl -= float(spread_pips)
                            except Exception:
                                pass
                        total_pips += pnl
                        total += 1
                        if pnl > 0:
                            wins += 1
                    trades.append({'open_time': oe.event_time, 'open_dir': oe.direction, 'open_price': op, 'close_time': ev.event_time, 'close_price': cp, 'pips': pnl, 'cycle_uid': getattr(oe, 'cycle_uid', None) or getattr(ev, 'cycle_uid', None)})

    win_rate = (wins / total * 100.0) if total else 0.0
    report(85, 'Computing KPIs')

    # Minimal KPIs
    cycles_done_buy = sum(1 for t in trades if t.get('open_dir') == 'BUY')
    cycles_done_sell = sum(1 for t in trades if t.get('open_dir') == 'SELL')

    # Extended KPIs similar to TS page
    gross_profit = sum((t.get('pips') or 0) for t in trades if (t.get('pips') or 0) > 0)
    gross_loss_abs = sum(-(t.get('pips') or 0) for t in trades if (t.get('pips') or 0) < 0)
    loss_count = max(0, total - wins)
    avg_win = (gross_profit / wins) if wins else 0.0
    avg_loss_abs = (gross_loss_abs / loss_count) if loss_count else 0.0
    profit_factor = (gross_profit / gross_loss_abs) if gross_loss_abs > 1e-9 else None
    payoff = (avg_win / avg_loss_abs) if avg_loss_abs > 1e-9 else None
    expectancy = 0.0
    if total:
        expectancy = (wins / total) * avg_win - (loss_count / total) * avg_loss_abs

    # Max drawdown from cumulative curve
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        cum += float(t.get('pips') or 0)
        if cum > peak:
            peak = cum
        dd = cum - peak
        if dd < max_dd:
            max_dd = dd

    # Avg duration
    durs = []
    for t in trades:
        ot = t.get('open_time'); ct = t.get('close_time')
        if ot and ct:
            try:
                durs.append((ct - ot).total_seconds())
            except Exception:
                pass
    avg_dur_s = (sum(durs) / len(durs)) if durs else 0

    # Streaks
    cur_w = cur_l = 0
    max_w = max_l = 0
    for t in trades:
        p = t.get('pips') or 0
        if p > 0:
            cur_w += 1; cur_l = 0
        elif p < 0:
            cur_l += 1; cur_w = 0
        else:
            cur_w = cur_l = 0
        if cur_w > max_w: max_w = cur_w
        if cur_l > max_l: max_l = cur_l

    # Direction mix
    buy_cnt = sum(1 for t in trades if (t.get('open_dir') == 'BUY'))
    sell_cnt = sum(1 for t in trades if (t.get('open_dir') == 'SELL'))
    tot_dirs = max(1, buy_cnt + sell_cnt)
    buy_pct = buy_cnt / tot_dirs * 100.0
    sell_pct = sell_cnt / tot_dirs * 100.0

    # Cumulative PnL series for sparklines
    vals_all: List[float] = []
    vals_buy: List[float] = []
    vals_sell: List[float] = []
    s_all = s_buy = s_sell = 0.0
    for t in trades:
        p = float(t.get('pips') or 0.0)
        s_all += p; vals_all.append(s_all)
        if t.get('open_dir') == 'BUY':
            s_buy += p
        if t.get('open_dir') == 'SELL':
            s_sell += p
        vals_buy.append(s_buy)
        vals_sell.append(s_sell)

    def _spark(values, overlay_last=None, width=120, height=30, pad=2):
        if not values:
            return {'w': width, 'h': height, 'path': '', 'overlay': '', 'zero_y': height - pad}
        n = len(values)
        if n == 1:
            values = [0.0, values[0]]; n = 2
        vmin = min(values)
        vmax = max(values)
        if overlay_last is not None:
            vmin = min(vmin, overlay_last)
            vmax = max(vmax, overlay_last)
        if vmin == vmax:
            vmin -= 1.0; vmax += 1.0
        sx = (width - 2*pad) / (n - 1)
        sy = (height - 2*pad) / (vmax - vmin)
        parts = []
        for i, v in enumerate(values):
            x = pad + i * sx
            y = height - pad - (v - vmin) * sy
            parts.append(f"{'M' if i==0 else 'L'}{x:.1f},{y:.1f}")
        y0 = height - pad - (0 - vmin) * sy
        overlay_path = ''
        if overlay_last is not None:
            x_last = pad + (n - 1) * sx
            y_last = height - pad - (values[-1] - vmin) * sy
            x_new = width - pad
            y_new = height - pad - (overlay_last - vmin) * sy
            overlay_path = f"M{x_last:.1f},{y_last:.1f} L{x_new:.1f},{y_new:.1f}"
        return {'w': width, 'h': height, 'path': ' '.join(parts), 'overlay': overlay_path, 'zero_y': f"{y0:.1f}"}

    spark_overall = _spark(vals_all)
    spark_buy = _spark(vals_buy)
    spark_sell = _spark(vals_sell)

    # Buy&Hold baseline on base TF feed
    kpi_buy_hold = 0.0
    kpi_short_hold = 0.0
    try:
        bind_b = TradingSystemTFBinding.objects.filter(trading_system=system, level=base_level).select_related('feed').first()
        if bind_b and bind_b.feed_id:
            bars = list(MarketBar.objects.filter(feed=bind_b.feed).only('close').order_by('dt')[:1])
            bars_last = list(MarketBar.objects.filter(feed=bind_b.feed).only('close').order_by('-dt')[:1])
            if bars and bars_last and bars[0].close is not None and bars_last[0].close is not None:
                first_c = float(bars[0].close); last_c = float(bars_last[0].close)
                kpi_buy_hold = (last_c - first_c) * pip_scale
                kpi_short_hold = (first_c - last_c) * pip_scale
    except Exception:
        pass

    kpi_cum_buy_total = s_buy
    kpi_cum_sell_total = s_sell
    kpi_pnl_vs_bh = (total_pips - (kpi_buy_hold or 0.0))
    kpi_buy_vs_bh = (kpi_cum_buy_total - (kpi_buy_hold or 0.0))
    kpi_sell_vs_sh = (kpi_cum_sell_total - (kpi_short_hold or 0.0))

    def _pct(delta, base):
        try:
            b = float(base or 0.0)
            if abs(b) < 1e-9:
                return None
            return float(delta) / abs(b) * 100.0
        except Exception:
            return None

    kpi_pnl_vs_bh_pct = _pct(kpi_pnl_vs_bh, kpi_buy_hold)
    kpi_buy_vs_bh_pct = _pct(kpi_buy_vs_bh, kpi_buy_hold)
    kpi_sell_vs_sh_pct = _pct(kpi_sell_vs_sh, kpi_short_hold)

    # Cycle-based metrics
    cycle_pnls: Dict[str, float] = {}
    for t in trades:
        uid = t.get('cycle_uid')
        p = t.get('pips')
        if uid and p is not None:
            try:
                cycle_pnls[uid] = cycle_pnls.get(uid, 0.0) + float(p)
            except Exception:
                continue
    profits = [v for v in cycle_pnls.values() if v > 0]
    losses = [v for v in cycle_pnls.values() if v < 0]

    cycle_counts: Dict[str, int] = {}
    for t in trades:
        uid = t.get('cycle_uid')
        if uid:
            cycle_counts[uid] = cycle_counts.get(uid, 0) + 1
    counts_list = list(cycle_counts.values())
    kpi_trades_per_cycle_avg = (sum(counts_list) / len(counts_list)) if counts_list else 0.0
    kpi_trades_per_cycle_max = max(counts_list) if counts_list else 0

    # Distribution (#trades -> cycles count)
    kpi_cycle_dist = []
    kpi_cycle_dist_max = 0
    if counts_list:
        hist: Dict[int, int] = {}
        for c in counts_list:
            hist[c] = hist.get(c, 0) + 1
        kpi_cycle_dist = sorted(hist.items())
        try:
            kpi_cycle_dist_max = max(qty for _, qty in kpi_cycle_dist)
        except ValueError:
            kpi_cycle_dist_max = 0

    # Profit by number of trades per cycle
    kpi_profit_by_count = []  # list of dicts
    kpi_profit_by_count_max_abs = 0.0
    if cycle_pnls:
        agg: Dict[int, float] = {}
        for uid, pnl in cycle_pnls.items():
            cnt = cycle_counts.get(uid, 0)
            agg[cnt] = agg.get(cnt, 0.0) + float(pnl or 0.0)
        raw_pairs = sorted(agg.items())
        kpi_profit_by_count = [{'count': c, 'sum': s, 'abs': abs(s), 'pos': (s > 0), 'neg': (s < 0)} for c, s in raw_pairs]
        kpi_profit_by_count_max_abs = max((item['abs'] for item in kpi_profit_by_count), default=0.0)

    def _avg(vals):
        return (sum(vals) / len(vals)) if vals else 0.0
    kpi_cycle_profit_avg = _avg(profits)
    kpi_cycle_profit_max = max(profits) if profits else 0.0
    kpi_cycle_loss_avg = _avg(losses)
    kpi_cycle_loss_max = (min(losses) if losses else 0.0)

    # Build open positions list from remaining queue and estimate unrealized PnL
    open_positions: List[Dict[str, Any]] = []
    try:
        # Determine current price from the most precise available feed
        cur_price = None
        try:
            # prefer the finest resolution feed among bindings
            binds_all = list(TradingSystemTFBinding.objects.filter(trading_system=system).select_related('feed__tfcode'))
            def _rank(b):
                try:
                    code = (b.feed.tfcode.code or '').upper()
                except Exception:
                    code = ''
                if code.startswith('T'):
                    try:
                        ticks = int(code[1:])
                    except Exception:
                        ticks = 10**9
                    return (0, ticks)
                try:
                    mins = int(getattr(b.feed.tfcode, 'minutes', None) or 999999)
                except Exception:
                    mins = 999999
                return (1, mins)
            use_feed = None
            if binds_all:
                binds_all.sort(key=_rank)
                use_feed = binds_all[0].feed
            if not use_feed:
                b0 = TradingSystemTFBinding.objects.filter(trading_system=system, level=base_level).select_related('feed').first()
                use_feed = getattr(b0, 'feed', None)
            if use_feed:
                last_bar = MarketBar.objects.filter(feed=use_feed).only('close').order_by('-dt').first()
                if last_bar and last_bar.close is not None:
                    cur_price = float(last_bar.close)
        except Exception:
            cur_price = None

        remaining = []
        for side in ('BUY', 'SELL'):
            dq = open_q.get(side)
            if dq:
                remaining.extend(list(dq))
        # oldest first
        remaining.sort(key=lambda ev: getattr(ev, 'event_time', None))
        for oe in remaining:
            op = _get_close(oe)
            op_val = float(op) if op is not None else None
            unreal = None
            if cur_price is not None and op_val is not None:
                if getattr(oe, 'direction', None) == 'BUY':
                    unreal = (cur_price - op_val) * pip_scale
                else:
                    unreal = (op_val - cur_price) * pip_scale
            open_positions.append({
                'open_time': getattr(oe, 'event_time', None),
                'open_dir': getattr(oe, 'direction', None),
                'open_price': op_val,
                'cur_price': cur_price,
                'open_pnl': unreal,
                'open_id': getattr(oe, 'id', None),
            })
    except Exception:
        open_positions = []

    # Clean rules text from system settings (drop empty/comment lines)
    rules_clean = ''
    try:
        if getattr(system, 'signal_settings', None):
            raw = getattr(system.signal_settings, 'signal_logic', '') or ''
            lines = []
            for ln in (raw.splitlines() if raw else []):
                s = ln.strip()
                if not s or s.startswith('#'):
                    continue
                lines.append(s)
            rules_clean = "\n".join(lines)
    except Exception:
        rules_clean = ''

    # Staleness: compare rules updated_at vs last signals generation time (created_at)
    rules_updated_at = None
    try:
        rules_updated_at = getattr(getattr(system, 'signal_settings', None), 'updated_at', None)
    except Exception:
        rules_updated_at = None
    try:
        generated_at = SignalEvent.objects.filter(trading_system=system, level=base_level).aggregate(m=Max('created_at')).get('m')
    except Exception:
        generated_at = None

    result = {
        'system_id': system.id,
        'system_sid': system.system_sid,
        'symbol': system.symbol,
        'base_level': base_level,
        'total_trades': total,
        'total_pips': total_pips,
        'win_rate': win_rate,
        'cycles_buy': cycles_done_buy,
        'cycles_sell': cycles_done_sell,
        'trades': trades[-200:],  # last 200 trades for display
        'events_count': len(evs),
        'events_from_dt': events_from_dt.isoformat() if events_from_dt else None,
        'events_to_dt': events_to_dt.isoformat() if events_to_dt else None,
        'rules_updated_at': (rules_updated_at.isoformat() if rules_updated_at else None),
        'signals_generated_at': (generated_at.isoformat() if generated_at else None),
        'signals_stale': (bool(rules_updated_at and generated_at and (rules_updated_at > generated_at))),
        'kpi_profit_factor': profit_factor,
        'kpi_payoff': payoff,
        'kpi_expectancy': expectancy,
        'kpi_max_dd': max_dd,
        'kpi_avg_duration_sec': avg_dur_s,
        'kpi_streaks': {'win': max_w, 'loss': max_l},
        'kpi_dir_mix': {'buy_pct': buy_pct, 'sell_pct': sell_pct},
        'spark_overall': spark_overall,
        'spark_buy': spark_buy,
        'spark_sell': spark_sell,
        'kpi_buy_hold': kpi_buy_hold,
        'kpi_short_hold': kpi_short_hold,
        'kpi_pnl_vs_bh': kpi_pnl_vs_bh,
        'kpi_buy_vs_bh': kpi_buy_vs_bh,
        'kpi_sell_vs_sh': kpi_sell_vs_sh,
        'kpi_cum_buy_total': kpi_cum_buy_total,
        'kpi_cum_sell_total': kpi_cum_sell_total,
        'kpi_pnl_vs_bh_pct': kpi_pnl_vs_bh_pct,
        'kpi_buy_vs_bh_pct': kpi_buy_vs_bh_pct,
        'kpi_sell_vs_sh_pct': kpi_sell_vs_sh_pct,
        'open_positions': open_positions,
        'kpi_open_pnl': sum((p.get('open_pnl') or 0.0) for p in open_positions),
        'rules_clean': rules_clean,
        'kpi_trades_per_cycle_avg': kpi_trades_per_cycle_avg,
        'kpi_trades_per_cycle_max': kpi_trades_per_cycle_max,
        'kpi_cycle_dist': kpi_cycle_dist,
        'kpi_cycle_dist_max': kpi_cycle_dist_max,
        'kpi_profit_by_count': kpi_profit_by_count,
        'kpi_profit_by_count_max_abs': kpi_profit_by_count_max_abs,
        'kpi_cycle_profit_avg': kpi_cycle_profit_avg,
        'kpi_cycle_profit_max': kpi_cycle_profit_max,
        'kpi_cycle_loss_avg': kpi_cycle_loss_avg,
        'kpi_cycle_loss_max': kpi_cycle_loss_max,
        'spread_pips_used': float(spread_pips) if spread_pips is not None else float(getattr(system, 'spread_pips', 0) or 0.0),
    }

    # USD metrics via MT5 (best effort)
    usd_per_pip_per_lot = 10.0
    mt5_tick_size = None
    mt5_tick_value = None
    mt5_reason = None
    try:
        from .mt5_service import MT5Manager  # type: ignore
        import MetaTrader5 as mt5  # type: ignore
        svc = MT5Manager.get_default_service()
        if svc:
            with svc as s:
                if s.is_connected:
                    sym = (system.symbol or '').strip()
                    if sym:
                        mt5.symbol_select(sym, True)
                        info = mt5.symbol_info(sym)
                        if info and getattr(info, 'trade_tick_size', None) and getattr(info, 'trade_tick_value', None):
                            mt5_tick_size = float(info.trade_tick_size)
                            mt5_tick_value = float(info.trade_tick_value)
                            mt5_reason = 'info'
                        else:
                            tsz = mt5.symbol_info_double(sym, mt5.SYMBOL_TRADE_TICK_SIZE)
                            tvl = mt5.symbol_info_double(sym, mt5.SYMBOL_TRADE_TICK_VALUE)
                            if tsz and tvl:
                                mt5_tick_size = float(tsz)
                                mt5_tick_value = float(tvl)
                                mt5_reason = 'double'
    except Exception:
        pass

    try:
        pip_size = 0.01 if 'JPY' in (system.symbol or '').upper() else 0.0001
        if mt5_tick_size and mt5_tick_value and mt5_tick_size > 0:
            usd_per_pip_per_lot = mt5_tick_value / (mt5_tick_size / pip_size)
    except Exception:
        pass

    lot = float(lot_size or 0.01)
    start_bal = float(start_balance or 10000.0)
    kpi_profit_usd = float(total_pips) * usd_per_pip_per_lot * lot
    bal = start_bal
    min_eq = bal
    for t in trades:
        bal += float(t.get('pips') or 0.0) * usd_per_pip_per_lot * lot
        if bal < min_eq:
            min_eq = bal
    result.update({
        'mt5_tick_size': mt5_tick_size,
        'mt5_tick_value': mt5_tick_value,
        'mt5_tick_reason': mt5_reason,
        'usd_per_pip_per_lot': usd_per_pip_per_lot,
        'mt5_usd_per_tick_lot': (mt5_tick_value * lot) if (mt5_tick_value is not None) else None,
        'kpi_profit_usd': kpi_profit_usd,
        'kpi_end_balance': bal,
        'kpi_min_equity': min_eq,
        'kpi_return_pct': ((bal - start_bal) / max(1e-9, start_bal)) * 100.0,
    })

    # Price chart with markers (recent window)
    try:
        bind = TradingSystemTFBinding.objects.filter(trading_system=system, level=base_level).select_related('feed').first()
        pc = None
        if bind and bind.feed_id:
            bars = list(MarketBar.objects.filter(feed=bind.feed).only('dt','open','high','low','close').order_by('-dt')[:250])
            bars.reverse()
            if bars:
                def _to_float(val):
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return None
                highs = [_to_float(b.high) for b in bars]
                lows = [_to_float(b.low) for b in bars]
                opens = [_to_float(b.open) for b in bars]
                closes = [_to_float(b.close) for b in bars]
                valid_highs = [v for v in highs if v is not None]
                valid_lows = [v for v in lows if v is not None]
                pmax = max(valid_highs) if valid_highs else 1.0
                pmin = min(valid_lows) if valid_lows else 0.0
                if pmax == pmin:
                    pmax += 1e-6
                from django.utils import timezone as dj_tz
                dts = []
                for b in bars:
                    try:
                        dtv = getattr(b, 'dt')
                        dt_local = dj_tz.localtime(dtv) if dj_tz.is_aware(dtv) else dtv
                        dts.append(dt_local.strftime('%Y-%m-%d %H:%M:%S'))
                    except Exception:
                        dts.append(str(getattr(b, 'dt')))
                # Build allowed indicator key set from current rules (e.g., NAME[Lk])
                allowed_keys = set()
                try:
                    from .signal_engine import parse_rules, _collect_requirements  # type: ignore
                except Exception:
                    parse_rules = None
                    _collect_requirements = None
                try:
                    raw_rules = getattr(getattr(system, 'signal_settings', None), 'signal_logic', '') or ''
                    if parse_rules and _collect_requirements and raw_rules.strip():
                        rules_parsed = parse_rules(raw_rules)
                        req_pairs = list(_collect_requirements(rules_parsed))
                        for (nm, lv) in req_pairs:
                            eff = int(lv) if (lv is not None) else int(base_level)
                            allowed_keys.add(f"{nm}[L{eff}]")
                except Exception:
                    allowed_keys = set()

                dt_to_idx = {getattr(b, 'dt'): i for i,b in enumerate(bars)}
                markers = []
                for ev in evs:
                    dt_e = getattr(ev, 'event_time', None)
                    if dt_e in dt_to_idx:
                        idx = dt_to_idx[dt_e]
                        mb = bars[idx] if 0 <= idx < len(bars) else None
                        if not mb:
                            continue
                        action = getattr(ev, 'action', 'OPEN')
                        direction = getattr(ev, 'direction', '')
                        price_val = _to_float(mb.close if action == 'CLOSE' else mb.open)
                        if price_val is None:
                            continue
                        # serialize indicators snapshot if present on event
                        raw_ind = getattr(ev, 'ind_values', None)
                        indicators = {}
                        if isinstance(raw_ind, dict):
                            for key, val in raw_ind.items():
                                key_str = str(key)
                                # keep only indicators used in current rules
                                if allowed_keys and key_str not in allowed_keys:
                                    continue
                                if isinstance(val, bool):
                                    indicators[key_str] = bool(val)
                                elif isinstance(val, int):
                                    indicators[key_str] = int(val)
                                elif isinstance(val, Number):
                                    try:
                                        indicators[key_str] = float(val)
                                    except Exception:
                                        indicators[key_str] = float(val)
                                else:
                                    indicators[key_str] = str(val)
                        mtype = 'buy-open' if action == 'OPEN' and direction == 'BUY' else (
                                'sell-open' if action == 'OPEN' and direction == 'SELL' else (
                                'buy-close' if action == 'CLOSE' and direction == 'BUY' else (
                                'sell-close' if action == 'CLOSE' and direction == 'SELL' else 'other')))
                        markers.append({'idx': idx, 'price': price_val, 'klass': mtype, 'type': f"{direction} {action}".strip(), 'indicators': indicators})
                # Indicators subplot: collect series used in rules and sample to base bar times
                inds_payload = []
                try:
                    from .signal_engine import parse_rules, _collect_requirements  # type: ignore
                except Exception:
                    parse_rules = None
                    _collect_requirements = None
                try:
                    raw_rules = getattr(getattr(system, 'signal_settings', None), 'signal_logic', '') or ''
                    req = []
                    if parse_rules and _collect_requirements and raw_rules.strip():
                        try:
                            rules_parsed = parse_rules(raw_rules)
                            req = list(_collect_requirements(rules_parsed))
                        except Exception:
                            req = []
                    feeds_by_level = {base_level: bind.feed}
                    try:
                        for bb in TradingSystemTFBinding.objects.filter(trading_system=system).select_related('feed'):
                            lvlv = int(getattr(bb, 'level', 0) or 0)
                            if lvlv not in feeds_by_level:
                                feeds_by_level[lvlv] = bb.feed
                    except Exception:
                        pass
                    from django.utils import timezone as dj_tz
                    def _norm_dt(dt):
                        try:
                            if dj_tz.is_aware(dt):
                                # normalize to local timezone then drop tzinfo for comparable naive dt
                                return dj_tz.localtime(dt).replace(tzinfo=None)
                        except Exception:
                            pass
                        return dt

                    # Precompute normalized base bar times for sampling
                    base_times = [ _norm_dt(getattr(b, 'dt')) for b in bars ]

                    for (iname, lvl) in req:
                        eff_lvl = int(lvl) if (lvl is not None) else int(base_level)
                        f = feeds_by_level.get(eff_lvl)
                        if not f:
                            continue
                        idef = MarketIndicatorDef.objects.filter(feed=f, name=iname).first()
                        if not idef:
                            continue
                        vqs = list(MarketIndicatorValue.objects.filter(indicator=idef).select_related('bar').order_by('bar__dt'))
                        times = [_norm_dt(getattr(v, 'bar').dt) for v in vqs]
                        vals = [None if getattr(v, 'value', None) is None else float(getattr(v, 'value')) for v in vqs]
                        out = []
                        j = 0
                        m = len(times)
                        for tb in base_times:
                            while j + 1 < m and times[j + 1] <= tb:
                                j += 1
                            if m == 0:
                                out.append(None)
                            else:
                                out.append(vals[j] if (j < m and times[j] <= tb) else None)
                        inds_payload.append({'name': iname, 'level': eff_lvl, 'values': [ (None if v is None else float(v)) for v in out ]})
                except Exception:
                    inds_payload = []

                pc = {
                    'w': 900,
                    'h': 220,
                    'pad': 6,
                    'pmin': f"{pmin:.6f}",
                    'pmax': f"{pmax:.6f}",
                    'n': len(bars),
                    'dts': dts,
                    'highs': [f"{(v if v is not None else float('nan')):.6f}" if v is not None else 'nan' for v in highs],
                    'lows': [f"{(v if v is not None else float('nan')):.6f}" if v is not None else 'nan' for v in lows],
                    'opens': [f"{(v if v is not None else float('nan')):.6f}" if v is not None else 'nan' for v in opens],
                    'closes': [f"{(v if v is not None else float('nan')):.6f}" if v is not None else 'nan' for v in closes],
                    'markers': markers,
                    'inds': inds_payload,
                }
        result['price_chart'] = pc
        if pc and pc.get('dts'):
            try:
                result['bars_from_dt'] = pc['dts'][0]
                result['bars_to_dt'] = pc['dts'][-1]
            except Exception:
                pass
    except Exception:
        result['price_chart'] = None
    report(100, 'Done')
    return result
