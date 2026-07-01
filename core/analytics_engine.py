from datetime import datetime

def _weighted_median(buckets: list[tuple[int, int]]) -> float:
    """Compute weighted median from (value, weight) pairs."""
    total_weight = sum(weight for _value, weight in buckets)
    if total_weight == 0:
        return 0.0
    sorted_buckets = sorted(buckets, key=lambda x: x[0])
    running = 0
    midpoint = total_weight / 2
    for value, weight in sorted_buckets:
        running += weight
        if running >= midpoint:
            return float(value)
    return float(sorted_buckets[-1][0])

def _calculate_max_drawdown(daily_pnl_totals: dict[str, int]) -> int:
    """Calculate max drawdown from daily realized P/L totals."""
    if not daily_pnl_totals:
        return 0
    cumulative = 0
    peak = 0
    max_drawdown = 0
    for date_key in sorted(daily_pnl_totals.keys()):
        cumulative += daily_pnl_totals[date_key]
        if cumulative > peak:
            peak = cumulative
        drawdown = cumulative - peak
        if drawdown < max_drawdown:
            max_drawdown = drawdown
    return max_drawdown

def calculate_advanced_metrics(
    filtered_pnl_results: list[dict],
    trades_by_id: dict,
    sell_totals: dict[int, int],
    daily_pnl_totals: dict[str, int]
) -> dict:
    """
    Calculate advanced trading analytics like win rate, profit factor, 
    expectancy, holding days, and max drawdown.
    """
    wins = sum(1 for pnl in sell_totals.values() if pnl > 0)
    losses = sum(1 for pnl in sell_totals.values() if pnl < 0)
    total_trades = len(sell_totals)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

    win_values = [pnl for pnl in sell_totals.values() if pnl > 0]
    loss_values = [pnl for pnl in sell_totals.values() if pnl < 0]
    avg_win = float(sum(win_values) / len(win_values)) if win_values else 0
    avg_loss = float(sum(loss_values) / len(loss_values)) if loss_values else 0

    if losses == 0:
        win_loss_ratio = "∞" if wins > 0 else "0.00"
    else:
        win_loss_ratio = f"{wins / losses:.2f}"

    total_profit_val = sum(win_values)
    total_loss_abs = abs(sum(loss_values))
    if total_loss_abs == 0:
        profit_factor = "∞" if total_profit_val > 0 else "0.00"
    else:
        profit_factor = f"{total_profit_val / total_loss_abs:.2f}"

    loss_rate = 1 - (wins / total_trades) if total_trades > 0 else 0.0
    expectancy = int((avg_win * (win_rate / 100)) + (avg_loss * loss_rate))

    total_qty = 0
    total_days = 0
    holding_buckets: list[tuple[int, int]] = []
    for match in filtered_pnl_results:
        buy_date = trades_by_id[match['buy_id']]['trade_date']
        sell_date = trades_by_id[match['sell_id']]['trade_date']
        days = abs((datetime.strptime(sell_date, '%Y-%m-%d') - datetime.strptime(buy_date, '%Y-%m-%d')).days)
        qty = match['matched_quantity']
        total_days += days * qty
        total_qty += qty
        holding_buckets.append((days, qty))
        
    avg_holding_days = (total_days / total_qty) if total_qty > 0 else 0.0
    median_holding_days = _weighted_median(holding_buckets) if holding_buckets else 0.0

    max_drawdown = _calculate_max_drawdown(daily_pnl_totals)

    return {
        'win_loss_ratio': win_loss_ratio,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'expectancy': expectancy,
        'avg_holding_days': avg_holding_days,
        'median_holding_days': median_holding_days,
        'max_drawdown': max_drawdown
    }
