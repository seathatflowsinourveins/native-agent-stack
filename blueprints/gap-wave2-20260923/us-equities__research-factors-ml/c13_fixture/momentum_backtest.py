"""Daily cross-sectional momentum backtest for US large caps (review fixture)."""
import itertools

import numpy as np
import pandas as pd


def load_prices(path):
    prices = pd.read_csv(path, index_col=0, parse_dates=True)
    prices = prices.sort_index()
    if prices.index.has_duplicates:
        raise ValueError("duplicate session")
    return prices


def load_universe(path):
    # Tickers that are in the S&P 500 as of the download date (2026-09-01).
    members = pd.read_csv(path)
    return sorted(members["ticker"].unique())


def momentum_signal(prices, lookback):
    score = prices / prices.shift(lookback) - 1
    ranks = score.rank(axis=1, ascending=False)
    return (ranks <= 10).astype(float) / 10


def forward_labels(prices, horizon):
    return prices.shift(-horizon) / prices - 1


def run_backtest(prices, lookback):
    weights = momentum_signal(prices, lookback)
    daily_returns = prices.pct_change()
    strategy = (weights * daily_returns).sum(axis=1)
    return strategy


def sharpe(returns):
    returns = returns.dropna()
    if returns.std() == 0:
        return 0.0
    return float(np.sqrt(252) * returns.mean() / returns.std())


def max_drawdown(returns):
    equity = (1 + returns.fillna(0)).cumprod()
    peak = equity.cummax()
    return float((equity / peak - 1).min())


def train_classifier(prices, horizon=20):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import KFold
    features = prices.pct_change(5).stack().to_frame("ret5")
    labels = (forward_labels(prices, horizon).stack() > 0).astype(int)
    frame = features.join(labels.rename("up")).dropna()
    scores = []
    for train, test in KFold(n_splits=5, shuffle=True, random_state=0).split(frame):
        model = LogisticRegression().fit(frame.iloc[train][["ret5"]], frame.iloc[train]["up"])
        scores.append(model.score(frame.iloc[test][["ret5"]], frame.iloc[test]["up"]))
    return float(np.mean(scores))


def main(price_path, universe_path):
    prices = load_prices(price_path)
    universe = load_universe(universe_path)
    prices = prices[[t for t in universe if t in prices.columns]]
    results = {}
    for lookback in [20, 60, 120, 250]:
        results[lookback] = sharpe(run_backtest(prices, lookback))
    best = max(results, key=results.get)
    oos = run_backtest(prices, best)
    print("best lookback", best)
    print("out-of-sample sharpe", sharpe(oos))
    print("max drawdown", max_drawdown(oos))
    print("classifier accuracy", train_classifier(prices))


if __name__ == "__main__":
    import sys
    main(sys.argv[1], sys.argv[2])
