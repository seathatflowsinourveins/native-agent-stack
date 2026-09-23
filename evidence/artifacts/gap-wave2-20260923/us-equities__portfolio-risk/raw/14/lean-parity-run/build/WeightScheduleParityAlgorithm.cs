using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using QuantConnect;
using QuantConnect.Algorithm;
using QuantConnect.Data;
using QuantConnect.Data.Market;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Orders.Fills;
using QuantConnect.Orders.Slippage;
using QuantConnect.Securities;

// Gap 14 (portfolio-risk, gap wave 2): replay one skfolio fold-weight schedule for a Nautilus/LEAN accounting diff.
// Local integration fixture using upstream LEAN APIs; not an investment strategy.

// Declared convention: a market order fills at the close of the daily bar that triggered it (16:00 New York),
// mirroring the Nautilus bar-close fill. LEAN's MarketOrder helper would convert a daily-resolution order into
// MarketOnOpen/MarketOnClose, so the algorithm submits OrderType.Market directly and this model fills it.
public class DailyCloseFillModel : FillModel
{
    public override OrderEvent MarketFill(Security asset, MarketOrder order)
    {
        var fill = new OrderEvent(order, asset.LocalTime.ConvertToUtc(asset.Exchange.TimeZone), OrderFee.Zero);
        if (order.Status == OrderStatus.Canceled) return fill;
        var bar = asset.GetLastData() as TradeBar;
        if (bar == null || bar.EndTime != asset.LocalTime)
            throw new InvalidOperationException($"no daily bar ending at {asset.LocalTime:o} for {asset.Symbol}");
        fill.FillPrice = bar.Close;
        fill.FillQuantity = order.Quantity;
        fill.Status = OrderStatus.Filled;
        return fill;
    }
}

public class WeightScheduleParityAlgorithm : QCAlgorithm
{
    private static readonly string[] Assets = { "SPY", "QQQ", "IWM" };
    private readonly Dictionary<DateTime, decimal[]> _plan = new();
    private readonly HashSet<DateTime> _done = new();
    private readonly List<string> _ledger = new();
    private Symbol[] _symbols;
    private DateTime _final;
    private string _ledgerPath;
    private const decimal Invest = 0.99m;

    public override void Initialize()
    {
        if (LiveMode) throw new InvalidOperationException("Backtesting fixture only.");
        var culture = CultureInfo.InvariantCulture;
        Settings.DailyPreciseEndTime = true;
        var schedule = File.ReadAllLines(GetParameter("schedule-path"));
        _final = DateTime.ParseExact(GetParameter("final-close"), "yyyy-MM-dd", culture);
        _ledgerPath = GetParameter("ledger-path");
        foreach (var line in schedule.Skip(1).Where(l => l.Length > 0))
        {
            var cells = line.Split(',');
            _plan[DateTime.ParseExact(cells[0], "yyyy-MM-dd", culture)] =
                cells.Skip(1).Select(c => decimal.Parse(c, NumberStyles.Float, culture)).ToArray();
        }
        var fee = GetParameter("fee-usd", 1m);
        var first = _plan.Keys.Min();
        SetStartDate(first.Year, first.Month, first.Day);
        SetEndDate(_final.Year, _final.Month, _final.Day);
        SetCash(decimal.Parse(GetParameter("capital"), culture));
        _symbols = Assets.Select(a =>
        {
            var s = AddEquity(a, Resolution.Daily, fillForward: false, leverage: 1m,
                              dataNormalizationMode: DataNormalizationMode.Raw);
            s.SetFeeModel(new ConstantFeeModel(fee));
            s.SetFillModel(new DailyCloseFillModel());
            s.SetSlippageModel(new ConstantSlippageModel(0m));
            return s.Symbol;
        }).ToArray();
        _ledger.Add("kind,time_utc,a,b,c,d,e");
    }

    private decimal Cash => Portfolio.CashBook["USD"].Amount;

    private string Num(decimal v) => v.ToString(CultureInfo.InvariantCulture);

    public override void OnData(Slice data)
    {
        foreach (var d in data.Dividends.Values)
            _ledger.Add($"dividend,{UtcTime:o},{d.Symbol.Value},{Num(d.Distribution)},{Num(Portfolio[d.Symbol].Quantity)},{Num(Cash)},");
        if (!_symbols.All(s => data.Bars.ContainsKey(s))) return;
        var day = Time.Date;
        var liquidate = day == _final;
        if (!liquidate && !_plan.ContainsKey(day)) return;
        var close = _symbols.Select(s => data.Bars[s].Close).ToArray();
        var held = _symbols.Select(s => (long)Portfolio[s].Quantity).ToArray();
        var equity = Cash + Enumerable.Range(0, 3).Sum(i => held[i] * close[i]);
        var target = liquidate ? new long[3] : Enumerable.Range(0, 3)
            .Select(i => (long)decimal.Floor(equity * Invest * _plan[day][i] / close[i])).ToArray();
        _ledger.Add($"decision,{UtcTime:o},{day:yyyy-MM-dd},{Num(equity)},{target[0]},{target[1]},{target[2]}");
        foreach (var sells in new[] { true, false })
        {
            for (var i = 0; i < 3; i++)
            {
                var delta = target[i] - held[i];
                if (delta == 0 || (delta < 0) != sells) continue;
                var ticket = SubmitOrderRequest(new SubmitOrderRequest(OrderType.Market, SecurityType.Equity, _symbols[i],
                    delta, 0m, 0m, UtcTime, sells ? "sell" : "buy"));
                Transactions.WaitForOrder(ticket.OrderId);
                if (ticket.Status != OrderStatus.Filled)
                    throw new InvalidOperationException($"order {ticket.OrderId} {_symbols[i]} {delta} not filled: {ticket.Status}");
                var fill = ticket.OrderEvents.Last(e => e.Status == OrderStatus.Filled);
                _ledger.Add($"fill,{fill.UtcTime:o},{_symbols[i].Value},{Num(fill.FillQuantity)},{Num(fill.FillPrice)},{Num(fill.OrderFee.Value.Amount)},{Num(Cash)}");
            }
        }
        _done.Add(day);
    }

    public override void OnEndOfAlgorithm()
    {
        var held = _symbols.Select(s => Num(Portfolio[s].Quantity)).ToArray();
        _ledger.Add($"final,{UtcTime:o},{Num(Cash)},{held[0]},{held[1]},{held[2]},");
        File.WriteAllLines(_ledgerPath, _ledger);
        if (!_plan.Keys.All(_done.Contains) || !_done.Contains(_final) || Portfolio.Invested)
            throw new InvalidOperationException("schedule not fully replayed or not flat at the end");
    }
}
