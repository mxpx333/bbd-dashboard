#!/usr/bin/env python3
"""
Fetch live stock prices and write data.json for the BBD dashboard.
Runs locally or via GitHub Actions on a schedule.
"""

import json
import sys
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance required. Install with: pip install yfinance")
    sys.exit(1)

# ─── PORTFOLIO DATA ──────────────────────────────────────────────────────────
PORTFOLIO_START_DATE = "2025-08-18"
RESHUFFLE_DATE = "2026-02-25"
ORIGINAL_CAPITAL = 85187.00

QUALITY_SCORES = {
    'NVDA': 85.1, 'V': 79.3, 'LLY': 79.1, 'MA': 78.7, 'NOW': 78.4,
    'AVGO': 73.9, 'ADBE': 73.8, 'MSFT': 71.9, 'GOOGL': 71.5, 'META': 71.2,
    'CRM': 69.1, 'AAPL': 66.9, 'NFLX': 66.7, 'AMZN': 63.3,
}

POSITIONS = {
    ('AVGO', '2797'): {'shares': 25, 'avg_cost': 332.23, 'cost_basis': 8305.63},
    ('LLY', '2797'):  {'shares': 8,  'avg_cost': 1033.32, 'cost_basis': 8266.56},
    ('MSFT', '2797'): {'shares': 4,  'avg_cost': 397.58,  'cost_basis': 1590.30},
    ('NFLX', '2797'): {'shares': 61, 'avg_cost': 81.99,   'cost_basis': 5001.09},
    ('AMZN', '0309'): {'shares': 40, 'avg_cost': 209.28,  'cost_basis': 8371.00},
    ('MA', '0309'):   {'shares': 16, 'avg_cost': 508.41,  'cost_basis': 8134.48},
    ('META', '0309'): {'shares': 12, 'avg_cost': 746.88,  'cost_basis': 8962.60},
    ('MSFT', '0309'): {'shares': 4,  'avg_cost': 515.99,  'cost_basis': 2063.96},
    ('NFLX', '0309'): {'shares': 33, 'avg_cost': 81.85,   'cost_basis': 2701.13},
    ('NVDA', '0309'): {'shares': 2,  'avg_cost': 197.35,  'cost_basis': 394.70},
    ('AAPL', '2667'): {'shares': 30, 'avg_cost': 273.47,  'cost_basis': 8204.00},
    ('ADBE', '2667'): {'shares': 32, 'avg_cost': 254.91,  'cost_basis': 8157.00},
    ('CRM', '2667'):  {'shares': 44, 'avg_cost': 189.25,  'cost_basis': 8327.00},
    ('GOOGL', '2667'):{'shares': 26, 'avg_cost': 249.88,  'cost_basis': 6497.00},
    ('MSFT', '2667'): {'shares': 13, 'avg_cost': 516.00,  'cost_basis': 6708.00},
    ('NFLX', '2667'): {'shares': 31, 'avg_cost': 82.13,   'cost_basis': 2546.00},
    ('NOW', '2667'):  {'shares': 81, 'avg_cost': 103.57,  'cost_basis': 8389.00},
    ('NVDA', '2667'): {'shares': 45, 'avg_cost': 184.02,  'cost_basis': 8281.00},
    ('V', '2667'):    {'shares': 26, 'avg_cost': 311.54,  'cost_basis': 8100.00},
}


def aggregate_positions():
    tickers = {}
    for (ticker, acct), pos in POSITIONS.items():
        if ticker not in tickers:
            tickers[ticker] = {'shares': 0, 'cost_basis': 0, 'score': QUALITY_SCORES.get(ticker, 0)}
        tickers[ticker]['shares'] += pos['shares']
        tickers[ticker]['cost_basis'] += pos['cost_basis']
    for ticker, data in tickers.items():
        data['avg_cost'] = data['cost_basis'] / data['shares'] if data['shares'] > 0 else 0
    return tickers


def fetch_prices(tickers):
    data = yf.download(tickers, period='1d', progress=False)
    prices = {}
    for t in tickers:
        try:
            prices[t] = float(data['Close'][t].iloc[-1])
        except (KeyError, IndexError):
            prices[t] = None
    return prices


def build_portfolio_data():
    agg = aggregate_positions()
    total_basis = sum(d['cost_basis'] for d in agg.values())
    prices = fetch_prices(list(QUALITY_SCORES.keys()))

    holdings = []
    total_value = 0
    sorted_tickers = sorted(agg.keys(), key=lambda t: QUALITY_SCORES.get(t, 0), reverse=True)

    for ticker in sorted_tickers:
        data = agg[ticker]
        price = prices.get(ticker)
        if price is None:
            continue
        current_value = data['shares'] * price
        cost_basis = data['cost_basis']
        gain_loss = current_value - cost_basis
        gain_pct = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0
        total_value += current_value
        holdings.append({
            'ticker': ticker, 'score': data['score'], 'shares': data['shares'],
            'avg_cost': round(data['avg_cost'], 2), 'cost_basis': round(cost_basis, 2),
            'current_price': round(price, 2), 'current_value': round(current_value, 2),
            'gain_loss': round(gain_loss, 2), 'gain_pct': round(gain_pct, 2),
        })

    total_gain = total_value - ORIGINAL_CAPITAL
    total_gain_pct = (total_gain / ORIGINAL_CAPITAL * 100) if ORIGINAL_CAPITAL > 0 else 0
    gain_vs_basis = total_value - total_basis
    gain_vs_basis_pct = (gain_vs_basis / total_basis * 100) if total_basis > 0 else 0

    days_held = (datetime.now() - datetime(2025, 8, 18)).days
    years_held = days_held / 365.25
    cagr = ((total_value / ORIGINAL_CAPITAL) ** (1 / years_held) - 1) * 100 if years_held > 0 else 0

    n_stocks = len(holdings)
    target_weight = 100.0 / n_stocks if n_stocks > 0 else 0
    for h in holdings:
        h['weight'] = round(h['current_value'] / total_value * 100, 2) if total_value > 0 else 0
        h['target_weight'] = round(target_weight, 2)

    return {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'portfolio_start': PORTFOLIO_START_DATE,
        'reshuffle_date': RESHUFFLE_DATE,
        'days_held': days_held,
        'years_held': round(years_held, 2),
        'original_capital': ORIGINAL_CAPITAL,
        'total_cost_basis': round(total_basis, 2),
        'total_value': round(total_value, 2),
        'total_gain': round(total_gain, 2),
        'total_gain_pct': round(total_gain_pct, 2),
        'gain_vs_basis': round(gain_vs_basis, 2),
        'gain_vs_basis_pct': round(gain_vs_basis_pct, 2),
        'cagr': round(cagr, 2),
        'num_stocks': n_stocks,
        'holdings': holdings,
    }


if __name__ == '__main__':
    print("Fetching prices...")
    data = build_portfolio_data()
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Updated data.json — ${data['total_value']:,.0f} total value, "
          f"+{data['total_gain_pct']:.1f}% return, {data['cagr']:.1f}% CAGR")
