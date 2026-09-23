using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using QuantConnect;
using QuantConnect.Algorithm;
using QuantConnect.Data;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Orders.Fills;
using QuantConnect.Orders.Slippage;
using QuantConnect.Securities;

// Local offline stress integration over upstream LEAN models; not a trading strategy.
public class HistoricalSimulationAlgorithm : QCAlgorithm
{
    private Symbol _spy;
    private string _ledger;
    private decimal _peak = 100000m;
    private bool _entered, _exited, _reduced;
    private bool _adaptive, _reject;
    private decimal _target;

    private decimal Seconds(DateTime utc) => (utc.Ticks - DateTime.UnixEpoch.Ticks) / 10000000m;
    private void Record(object item) => File.AppendAllText(_ledger, JsonSerializer.Serialize(item) + "\n");

    public override void Initialize()
    {
        if (LiveMode) throw new InvalidOperationException("Offline simulation only.");
        _ledger = GetParameter("ledger");
        _target = GetParameter("target", 1m);
        _adaptive = GetParameter("adaptive", 0) == 1;
        _reject = GetParameter("reject", 0) == 1;
        SetStartDate(2019, 12, 2);
        SetEndDate(2020, 4, 30);
        SetCash(100000);
        SetTimeZone(TimeZones.NewYork);
        SetBrokerageModel(QuantConnect.Brokerages.BrokerageName.Alpaca, AccountType.Margin);
        var security = AddEquity("SPY", Resolution.Hour, fillForward: false,
            extendedMarketHours: false, dataNormalizationMode: DataNormalizationMode.Raw);
        _spy = security.Symbol;
        security.SetBuyingPowerModel(new SecurityMarginModel(2m));
        security.SetFeeModel(new ConstantFeeModel(GetParameter("fee-usd", 0m)));
        security.SetSlippageModel(new ConstantSlippageModel(GetParameter("slippage", 0m)));
        security.SetFillModel(new EquityFillModel());
    }

    private void Submit(string reason, decimal target)
    {
        // Freeze sizing at decision time. Gaps may alter actual achieved exposure.
        var desired = Math.Floor(Portfolio.TotalPortfolioValue * target * 0.98m / Securities[_spy].Price);
        var quantity = desired - Portfolio[_spy].Quantity;
        if (quantity == 0) throw new InvalidOperationException("Expected a nonzero stress order.");
        var ticket = MarketOnOpenOrder(_spy, quantity, tag: reason);
        Record(new { kind = "intent", utc_seconds = Seconds(UtcTime), local = Time.ToString("O"),
            order_id = ticket.OrderId, quantity, target, reason, status = ticket.Status.ToString() });
    }

    public override void OnData(Slice data)
    {
        foreach (var dividend in data.Dividends.Values)
            Record(new { kind = "dividend", utc_seconds = Seconds(UtcTime),
                per_share = dividend.Distribution, quantity = Portfolio[dividend.Symbol].Quantity,
                amount = dividend.Distribution * Portfolio[dividend.Symbol].Quantity });
        if (data.Splits.Count != 0) throw new InvalidOperationException("Split accounting is outside this fixture.");
        if (!data.Bars.ContainsKey(_spy)) return;
        var equity = Portfolio.TotalPortfolioValue;
        _peak = Math.Max(_peak, equity);
        var drawdown = 1m - equity / _peak;
        Record(new { kind = "mark", utc_seconds = Seconds(UtcTime), local = Time.ToString("O"),
            data_end = data.Bars[_spy].EndTime.ToString("O"), equity, cash = Portfolio.Cash,
            quantity = Portfolio[_spy].Quantity, price = Securities[_spy].Price,
            gross = equity > 0 ? Math.Abs(Portfolio[_spy].HoldingsValue) / equity : -1,
            margin_used = Portfolio.TotalMarginUsed, margin_remaining = Portfolio.MarginRemaining,
            peak = _peak, drawdown });
        // Completed 16:00 bars only; no signal-based order uses its triggering bar's price.
        if (Time.Hour != 16 || Time.Minute != 0) return;
        if (!_entered && Time.Date == new DateTime(2019, 12, 31))
        {
            _entered = true;
            Submit("entry", _target);
        }
        else if (_entered && !_reject && !_exited && Time.Date == new DateTime(2020, 4, 29))
        {
            _exited = true;
            Submit("exit", 0m);
        }
        else if (_adaptive && _entered && !_reduced && !_exited && Portfolio.Invested && drawdown >= 0.05m)
        {
            _reduced = true;
            Record(new { kind = "reduction", utc_seconds = Seconds(UtcTime), equity, peak = _peak, drawdown });
            Submit("reduce", 0.5m);
        }
    }

    public override void OnOrderEvent(OrderEvent orderEvent)
    {
        Record(new { kind = "order", utc_seconds = Seconds(orderEvent.UtcTime),
            order_id = orderEvent.OrderId, status = orderEvent.Status.ToString(),
            message = orderEvent.Message, quantity = orderEvent.FillQuantity, price = orderEvent.FillPrice });
    }

    public override void OnMarginCallWarning()
    {
        Record(new { kind = "margin_warning", utc_seconds = Seconds(UtcTime),
            equity = Portfolio.TotalPortfolioValue, margin_remaining = Portfolio.MarginRemaining });
    }

    public override void OnMarginCall(List<SubmitOrderRequest> requests)
    {
        Record(new { kind = "margin_call", utc_seconds = Seconds(UtcTime), count = requests.Count,
            equity = Portfolio.TotalPortfolioValue, margin_remaining = Portfolio.MarginRemaining });
        // Upstream default liquidation remains enabled; no request mutation.
    }

    public override void OnEndOfAlgorithm()
    {
        Record(new { kind = "final", utc_seconds = Seconds(UtcTime), cash = Portfolio.Cash,
            equity = Portfolio.TotalPortfolioValue, quantity = Portfolio[_spy].Quantity });
        if (!_entered || Portfolio.Invested || (!_reject && !_exited) || (_adaptive && !_reduced))
            throw new InvalidOperationException("Expected stress lifecycle did not complete.");
    }
}
