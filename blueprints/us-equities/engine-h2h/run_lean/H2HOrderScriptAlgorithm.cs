using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using QuantConnect;
using QuantConnect.Algorithm;
using QuantConnect.Brokerages;
using QuantConnect.Data;
using QuantConnect.Orders;
using QuantConnect.Scheduling;

// Executes the frozen engine-H2H order script (order_script.json) through LEAN's own
// order API. Offline it runs over LEAN's bundled SPY minute data under the Alpaca
// brokerage model; for paper, run.py launches the same class under the official
// Alpaca brokerage with the paper flag forced. It is not a trading strategy: every
// order is fixed by the script and the latest bid/ask, never by fills or returns.
//
// Fault steps (paper only): at "kill"/"stop" the algorithm journals a fault point and
// waits for the orchestrator to end the process; the orchestrator restarts it with
// the "resume" parameter set to the case id, and the new process re-binds the open
// orders the brokerage reported at startup, then continues after the "restart" step.
public class H2HOrderScriptAlgorithm : QCAlgorithm
{
    private static readonly string[] StatusOrder =
        { "passed", "passed_with_deviation", "refused_explicit", "unsupported", "failed", "not_run_offline", "not_observable" };

    private sealed class Work
    {
        public string Phase, Case, Session;
        public int Run, Repeat, Index;
        public JsonElement Step;
        // One case instance per phase run: a failure aborts only this day's instance.
        public string Instance => $"{Run}|{Phase}|{Case}|{Repeat}";
    }

    private int _phaseRuns;

    private Symbol _spy;
    private JsonElement _script;
    private string _journal;
    private bool _paper;
    private string _resumeCase;
    private readonly Queue<Work> _queue = new();
    private Work _active;
    private DateTime _activeSinceUtc;
    private bool _activeStarted;
    private decimal? _requestedPrice;
    private readonly Dictionary<string, OrderTicket> _refs = new();
    private readonly HashSet<string> _abortedInstances = new();
    private readonly Dictionary<string, (string Status, string Detail)> _results = new();
    private readonly HashSet<int> _partiallyFilledOrders = new();

    public override void Initialize()
    {
        _paper = GetParameter("mode", "backtest") == "paper";
        if (LiveMode != _paper) throw new InvalidOperationException("mode parameter does not match the engine mode");
        _journal = GetParameter("journal");
        _resumeCase = GetParameter("resume", "");
        using (var document = JsonDocument.Parse(File.ReadAllText(GetParameter("script"))))
            _script = document.RootElement.Clone();
        if (_script.GetProperty("schema").GetString() != "engine-h2h-order-script/v1")
            throw new InvalidOperationException("unexpected order script schema");

        if (!_paper)
        {
            SetStartDate(2013, 10, 7);
            SetEndDate(2013, 10, 11);
            SetCash(100000);
        }
        SetTimeZone(TimeZones.NewYork);
        SetBrokerageModel(BrokerageName.Alpaca, AccountType.Margin);
        _spy = AddEquity(_script.GetProperty("symbol").GetString(), Resolution.Minute, fillForward: false,
            extendedMarketHours: true, dataNormalizationMode: DataNormalizationMode.Raw).Symbol;

        using (var plan = JsonDocument.Parse(GetParameter("plan")))
        {
            foreach (var day in plan.RootElement.EnumerateObject())
            {
                foreach (var phaseName in day.Value.EnumerateArray().Select(x => x.GetString()).ToList())
                {
                    var at = TimeSpan.ParseExact(_script.GetProperty("phases").GetProperty(phaseName).GetProperty("at_et").GetString(),
                        "hh\\:mm", CultureInfo.InvariantCulture);
                    IDateRule dateRule = DateRules.Today;
                    if (day.Name != "today")
                    {
                        var date = DateTime.ParseExact(day.Name, "yyyy-MM-dd", CultureInfo.InvariantCulture);
                        dateRule = DateRules.On(date.Year, date.Month, date.Day);
                    }
                    Schedule.On(dateRule, TimeRules.At(at.Hours, at.Minutes), () => Enqueue(phaseName));
                }
            }
        }
        // The step machine also advances between data slices.
        Schedule.On(DateRules.EveryDay(_spy), TimeRules.Every(TimeSpan.FromMinutes(1)), Advance);
        Record("run_start", new { mode = _paper ? "paper" : "backtest", resume = _resumeCase });
        if (GetParameter("probe", "") == "alpaca-plugin") ProbeAlpacaPlugin();
    }

    // Offline compatibility check: does this engine build's own composer load the
    // official Alpaca plugin from "plugin-directory", and does the plugin reference the
    // loaded LEAN assembly versions? Constructs only the factory and brokerage model;
    // the brokerage itself (network, QuantConnect license check) is never created.
    private void ProbeAlpacaPlugin()
    {
        var factories = QuantConnect.Util.Composer.Instance.GetExportedValues<QuantConnect.Interfaces.IBrokerageFactory>().ToList();
        var alpaca = factories.FirstOrDefault(f => f.GetType().Name == "AlpacaBrokerageFactory");
        object detail = null;
        if (alpaca != null)
        {
            var assembly = alpaca.GetType().Assembly;
            var loaded = AppDomain.CurrentDomain.GetAssemblies().GroupBy(a => a.GetName().Name, StringComparer.Ordinal)
                .ToDictionary(g => g.Key, g => string.Join("|", g.Select(a => a.GetName().Version?.ToString()).Distinct()), StringComparer.Ordinal);
            var references = assembly.GetReferencedAssemblies().Where(a => a.Name.StartsWith("QuantConnect.", StringComparison.Ordinal))
                .Select(a => new { name = a.Name, referenced = a.Version?.ToString(), loaded = loaded.GetValueOrDefault(a.Name) }).ToList();
            detail = new
            {
                assembly = assembly.GetName().ToString(),
                brokerage_type = alpaca.BrokerageType.FullName,
                data_keys = alpaca.BrokerageData.Keys.OrderBy(k => k, StringComparer.Ordinal).ToList(),
                model = alpaca.GetBrokerageModel(Transactions).GetType().FullName,
                references,
                all_references_match = references.All(r => r.referenced == r.loaded)
            };
        }
        Record("alpaca_plugin_probe", new { factories = factories.Count, found = alpaca != null, detail });
    }

    private JsonElement Case(string id) => _script.GetProperty("cases").GetProperty(id);

    private void Enqueue(string phaseName)
    {
        var phase = _script.GetProperty("phases").GetProperty(phaseName);
        var session = phase.GetProperty("session").GetString();
        var run = ++_phaseRuns;
        foreach (var caseId in phase.GetProperty("cases").EnumerateArray().Select(x => x.GetString()))
        {
            var spec = Case(caseId);
            if (!_paper && spec.TryGetProperty("paper_only", out var paperOnly) && paperOnly.GetBoolean())
            {
                Result(caseId, "not_run_offline", "fault case needs a live process and a broker");
                continue;
            }
            var repeats = 1;
            if (spec.TryGetProperty("repeat", out var repeat))
                repeats = _script.GetProperty("constants").GetProperty(repeat.GetString()).GetInt32();
            for (var r = 0; r < repeats; r++)
                EnqueueSteps(run, phaseName, caseId, session, r, 0);
        }
        Record("phase_enqueued", new { phase = phaseName, run, queued = _queue.Count });
        Advance();
    }

    private void EnqueueSteps(int run, string phaseName, string caseId, string session, int repeat, int fromIndex)
    {
        var index = 0;
        foreach (var step in Case(caseId).GetProperty("steps").EnumerateArray())
        {
            if (index >= fromIndex)
                _queue.Enqueue(new Work { Run = run, Phase = phaseName, Case = caseId, Session = session, Repeat = repeat, Index = index, Step = step });
            index++;
        }
    }

    // Paper restart: continue the fault case after its "restart" step, re-binding the
    // open orders the brokerage reported at startup (limit -> "a", stop -> "b").
    private void Resume()
    {
        var caseId = _resumeCase;
        _resumeCase = "";
        var steps = Case(caseId).GetProperty("steps").EnumerateArray().ToList();
        var restart = steps.FindIndex(s => s.GetProperty("do").GetString() == "restart");
        if (restart < 0) throw new InvalidOperationException("resume case has no restart step");
        var run = ++_phaseRuns;
        foreach (var ticket in Transactions.GetOpenOrderTickets(_spy))
        {
            var key = ticket.OrderType == OrderType.Limit ? "a" : ticket.OrderType == OrderType.StopMarket ? "b" : null;
            if (key != null) _refs[$"{run}|faults|{caseId}|0|{key}"] = ticket;
        }
        Record("resumed", new { @case = caseId, run, adopted = Transactions.GetOpenOrderTickets(_spy).Count() });
        EnqueueSteps(run, "faults", caseId, "regular", 0, restart + 1);
    }

    public override void OnData(Slice slice) => Advance();

    private void Advance()
    {
        if (_resumeCase != "") Resume();
        while (true)
        {
            if (_active == null)
            {
                if (_queue.Count == 0) return;
                _active = _queue.Dequeue();
                if (_abortedInstances.Contains(_active.Instance)) { _active = null; continue; }
                _activeSinceUtc = UtcTime;
                _activeStarted = false;
            }
            if (!_activeStarted)
            {
                _activeStarted = true;
                if (_active.Index == 0 && Case(_active.Case).TryGetProperty("requires_position", out var required)
                    && Portfolio[_spy].Quantity != required.GetInt32())
                {
                    FinishStep(false, "failed", $"precondition_position:{Portfolio[_spy].Quantity}");
                    continue;
                }
                string unsupported;
                try { unsupported = Execute(_active); }
                catch (InvalidOperationException error) when (error.Message == "no_quote")
                {
                    // The script defers a step without a usable quote for up to 60 s.
                    _activeStarted = false;
                    if ((UtcTime - _activeSinceUtc).TotalSeconds <= 60) return;
                    FinishStep(false, "failed", "no_quote");
                    continue;
                }
                if (unsupported != null) { FinishStep(false, "unsupported", unsupported); continue; }
            }
            var (done, ok, status, detail) = Check(_active);
            var timeout = _active.Step.TryGetProperty("timeout_s", out var t) ? t.GetInt32() : 60;
            if (!done && (UtcTime - _activeSinceUtc).TotalSeconds <= timeout) return;
            if (!done) { ok = false; status = "failed"; detail = "timeout:" + (detail ?? Observe(_active).State); }
            FinishStep(ok, status, detail);
        }
    }

    private void FinishStep(bool ok, string status, string detail)
    {
        var work = _active;
        _active = null;
        var steps = Case(work.Case).GetProperty("steps").GetArrayLength();
        Record("step_done", new { phase = work.Phase, @case = work.Case, repeat = work.Repeat, step = work.Index, ok, status, detail });
        if (!ok)
        {
            _abortedInstances.Add(work.Instance);
            Cleanup(work);
            Result(work.Case, status ?? "failed", detail);
        }
        else if (work.Index == steps - 1)
        {
            Result(work.Case, status ?? "passed", detail);
        }
        else if (status == "passed_with_deviation")
        {
            Result(work.Case, status, detail);
        }
    }

    private decimal Rule(string name)
    {
        var rule = _script.GetProperty("price_rules").GetProperty(name);
        var security = Securities[_spy];
        var bid = security.BidPrice > 0 ? security.BidPrice : security.Price;
        var ask = security.AskPrice > 0 ? security.AskPrice : security.Price;
        if (bid <= 0 || ask < bid) throw new InvalidOperationException("no_quote");
        var baseValue = rule.GetProperty("side_of_book").GetString() == "bid" ? bid : ask;
        var raw = baseValue * decimal.Parse(rule.GetProperty("multiplier").GetString(), CultureInfo.InvariantCulture);
        var rounded = rule.GetProperty("rounding").GetString() == "floor_cent"
            ? Math.Floor(raw * 100m) / 100m : Math.Ceiling(raw * 100m) / 100m;
        var add = rule.TryGetProperty("add", out var a) ? decimal.Parse(a.GetString(), CultureInfo.InvariantCulture) : 0m;
        return rounded + add;
    }

    private int Qty(JsonElement order)
    {
        var qty = order.GetProperty("qty");
        return qty.ValueKind == JsonValueKind.Number ? qty.GetInt32()
            : _script.GetProperty("constants").GetProperty(qty.GetString()).GetInt32();
    }

    // Returns null when the step was executed, or the reason it is unsupported.
    private string Execute(Work work)
    {
        var step = work.Step;
        var kind = step.GetProperty("do").GetString();
        var tag = $"h2h:{work.Phase}:{work.Case}:{work.Repeat}:{work.Index}";
        var refKey = step.TryGetProperty("ref", out var r) ? $"{work.Instance}|{r.GetString()}" : null;
        switch (kind)
        {
            case "submit":
                var order = step.GetProperty("order");
                var orderClass = order.TryGetProperty("class", out var c) ? c.GetString() : "simple";
                if (orderClass != "simple")
                {
                    // LEAN added contingent orders after this pin (QuantConnect/Lean#9828, 2026-09-25);
                    // the Alpaca plugin's support is still an open pull request (Lean.Brokerages.Alpaca#83).
                    return "contingent_orders_absent_at_pin:" + orderClass;
                }
                _requestedPrice = null;
                var sign = order.GetProperty("side").GetString() == "buy" ? 1 : -1;
                var quantity = (decimal)(sign * Qty(order));
                var tif = order.GetProperty("tif").GetString();
                // "opg"/"cls" map to LEAN's own MarketOnOpen/MarketOnClose types, which the
                // Alpaca plugin sends as opg/cls whatever the LEAN TIF; they keep LEAN's
                // default TIF (a Day TIF would expire a MOC before LEAN's close fill).
                var props = new AlpacaOrderProperties
                {
                    OutsideRegularTradingHours = order.TryGetProperty("extended_hours", out var ext) && ext.GetBoolean()
                };
                if (tif == "day") props.TimeInForce = TimeInForce.Day;
                OrderTicket ticket;
                switch (order.GetProperty("type").GetString())
                {
                    case "limit":
                        _requestedPrice = Rule(order.GetProperty("limit").GetString());
                        ticket = LimitOrder(_spy, quantity, _requestedPrice.Value, true, tag, props);
                        break;
                    case "market":
                        ticket = tif == "opg" ? MarketOnOpenOrder(_spy, quantity, true, tag, props)
                            : tif == "cls" ? MarketOnCloseOrder(_spy, quantity, true, tag, props)
                            : MarketOrder(_spy, quantity, true, tag, props);
                        break;
                    case "stop":
                        ticket = StopMarketOrder(_spy, quantity, Rule(order.GetProperty("stop").GetString()), true, tag, props);
                        break;
                    case "stop_limit":
                        ticket = StopLimitOrder(_spy, quantity, Rule(order.GetProperty("stop").GetString()),
                            Rule(order.GetProperty("limit").GetString()), true, tag, props);
                        break;
                    case "trailing_stop":
                        var percent = decimal.Parse(_script.GetProperty("constants")
                            .GetProperty(order.GetProperty("trail_percent").GetString()).GetString(), CultureInfo.InvariantCulture);
                        ticket = TrailingStopOrder(_spy, quantity, percent / 100m, true, true, tag, props);
                        break;
                    default:
                        return "order_type";
                }
                _refs[refKey] = ticket;
                Record("submit", new { tag, order_id = ticket.OrderId, requested_price = _requestedPrice, status = ticket.Status.ToString() });
                return null;
            case "replace":
                _requestedPrice = Rule(step.GetProperty("limit").GetString());
                var response = _refs[refKey].UpdateLimitPrice(_requestedPrice.Value, tag);
                Record("replace", new { tag, ok = response.IsSuccess, error = response.ErrorMessage });
                return null;
            case "cancel":
            case "cancel_if_open":
                if (_refs.TryGetValue(refKey, out var target) && (kind == "cancel" || IsOpen(target.Status)))
                    Record("cancel", new { tag, ok = target.Cancel(tag).IsSuccess });
                return null;
            case "flatten":
                // LEAN's own liquidation: cancels the symbol's open orders and closes the position.
                Liquidate(_spy, true, tag);
                Record("flatten", new { tag });
                return null;
            case "kill":
            case "stop":
            case "drop_stream":
                Record("fault_point", new { tag, kind });
                return null;
            default:
                // "await", "reconcile" and the "restart" marker only check state.
                return null;
        }
    }

    private static bool IsOpen(OrderStatus status) =>
        status is OrderStatus.New or OrderStatus.Submitted or OrderStatus.PartiallyFilled
            or OrderStatus.UpdateSubmitted or OrderStatus.CancelPending;

    private (string State, decimal Filled, decimal? Price) Observe(Work work)
    {
        if (!work.Step.TryGetProperty("ref", out var r) || !_refs.TryGetValue($"{work.Instance}|{r.GetString()}", out var ticket))
            return ("unknown", 0m, null);
        var state = ticket.Status switch
        {
            OrderStatus.New => "submitted",
            OrderStatus.Submitted or OrderStatus.UpdateSubmitted or OrderStatus.CancelPending =>
                ticket.QuantityFilled != 0 ? "partially_filled" : "open",
            OrderStatus.PartiallyFilled => "partially_filled",
            OrderStatus.Filled => "filled",
            OrderStatus.Canceled => "canceled",
            OrderStatus.Invalid => "refused",
            _ => "unknown"
        };
        decimal? price = ticket.OrderType is OrderType.Limit or OrderType.StopLimit ? ticket.Get(OrderField.LimitPrice) : null;
        return (state, Math.Abs(ticket.QuantityFilled), price);
    }

    private (bool Done, bool Ok, string Status, string Detail) Check(Work work)
    {
        var kind = work.Step.GetProperty("do").GetString();
        if (kind is "kill" or "stop") return (false, false, null, null);   // the orchestrator ends this process
        var expect = work.Step.TryGetProperty("expect", out var e) ? e.GetString() : null;
        if (expect == null) return (true, true, null, null);
        if (expect == "flat")
        {
            var flat = Portfolio[_spy].Quantity == 0 && !Transactions.GetOpenOrders(_spy).Any();
            return (flat, flat, null, flat ? null : $"position={Portfolio[_spy].Quantity}");
        }
        if (expect == "adopted_once")
        {
            var expected = Case(work.Case).GetProperty("steps").EnumerateArray()
                .Take(work.Index).Count(s => s.GetProperty("do").GetString() == "submit");
            var adopted = Transactions.GetOpenOrderTickets(_spy).Count();
            return (true, adopted == expected, adopted > expected ? "failed" : null, $"adopted={adopted};expected={expected}");
        }
        if (kind == "cancel_if_open" && !_refs.ContainsKey($"{work.Instance}|{work.Step.GetProperty("ref").GetString()}"))
            return (true, true, null, null);
        var (state, filled, price) = Observe(work);
        if (kind == "replace")
        {
            // A replace passes only when the new price is live in LEAN's own order state.
            if (state == "open" && price.HasValue && price.Value == _requestedPrice) return (true, true, null, null);
            if (state is "filled" or "partially_filled" or "canceled" or "refused") return (true, false, "failed", state);
            return (false, false, null, null);
        }
        switch (expect)
        {
            case "submitted":
                if (state is "submitted" or "open" or "partially_filled" or "filled") return (true, true, null, null);
                return (state is "refused" or "canceled", false, state == "refused" ? "refused_explicit" : "failed", state);
            case "open":
                if (state == "open" && filled == 0) return (true, true, null, null);
                if (filled > 0) return (true, false, "failed", "unintended_execution");
                return (state is "canceled" or "refused", false, state == "refused" ? "refused_explicit" : "failed", state);
            case "filled":
            case "filled_once":
                if (state == "filled") return (true, true, null, null);
                return (state is "canceled" or "refused", false, state == "refused" ? "refused_explicit" : "failed", state);
            case "canceled":
                if (state == "canceled" && filled == 0) return (true, true, null, null);
                if (filled > 0) return (true, false, "failed", "unintended_execution");
                return (state == "refused", false, "failed", state);
            case "refused":
            case "canceled_or_refused":
                if (filled > 0) return (true, false, "failed", "unintended_execution");
                var refused = state == "refused" || (expect == "canceled_or_refused" && state == "canceled");
                return (refused, refused, null, refused ? "refused_by_engine_or_broker" : null);
            case "refused_or_rounded":
                if (filled > 0) return (true, false, "failed", "unintended_execution");
                if (state == "refused") return (true, true, null, "refused_by_engine_or_broker");
                if (state == "open" && price.HasValue && _requestedPrice.HasValue && price.Value != _requestedPrice.Value
                    && price.Value == Math.Round(price.Value, 2))
                    return (true, true, "passed_with_deviation", $"rounded_in_engine_state:{_requestedPrice}->{price}");
                return (false, false, null, null);
            default:
                return (true, false, "failed", "unhandled_expectation:" + expect);
        }
    }

    private void Cleanup(Work work)
    {
        foreach (var ticket in Transactions.GetOpenOrderTickets(_spy).ToList())
            ticket.Cancel("h2h:cleanup");
        var quantity = Portfolio[_spy].Quantity;
        if (quantity == 0) return;
        if (work.Session == "regular")
        {
            Liquidate(_spy, true, "h2h:cleanup");
            return;
        }
        // Extended hours accept limit orders only.
        var security = Securities[_spy];
        var bid = security.BidPrice > 0 ? security.BidPrice : security.Price;
        var ask = security.AskPrice > 0 ? security.AskPrice : security.Price;
        var limit = quantity > 0 ? Math.Floor(bid * 0.995m * 100m) / 100m : Math.Ceiling(ask * 1.005m * 100m) / 100m;
        LimitOrder(_spy, -quantity, limit, true, "h2h:cleanup",
            new AlpacaOrderProperties { TimeInForce = TimeInForce.Day, OutsideRegularTradingHours = true });
    }

    private void Result(string caseId, string status, string detail)
    {
        if (!_results.TryGetValue(caseId, out var previous)
            || Array.IndexOf(StatusOrder, status) > Array.IndexOf(StatusOrder, previous.Status))
            _results[caseId] = (status, detail);
        Record("case_result", new { @case = caseId, status, detail });
    }

    public override void OnOrderEvent(OrderEvent orderEvent)
    {
        var order = Transactions.GetOrderById(orderEvent.OrderId);
        if (orderEvent.Status == OrderStatus.PartiallyFilled)
            _partiallyFilledOrders.Add(orderEvent.OrderId);
        Record("order_event", new
        {
            order_id = orderEvent.OrderId, status = orderEvent.Status.ToString(), fill_qty = orderEvent.FillQuantity,
            fill_price = orderEvent.FillPrice, message = orderEvent.Message, tag = order?.Tag,
            broker_ids = order?.BrokerId, event_utc = orderEvent.UtcTime.ToString("O")
        });
    }

    public override void OnEndOfAlgorithm()
    {
        if (_active != null || _queue.Count != 0)
            Record("unfinished", new { active = _active?.Case, queued = _queue.Count });
        Record("run_end", new
        {
            results = _results.ToDictionary(x => x.Key, x => new { status = x.Value.Status, detail = x.Value.Detail }),
            partially_filled_orders = _partiallyFilledOrders.Count,
            final_quantity = Portfolio[_spy].Quantity,
            open_orders = Transactions.GetOpenOrders(_spy).Count
        });
    }

    private void Record(string kind, object data)
    {
        var line = JsonSerializer.Serialize(new { kind, time_et = Time.ToString("O"), utc = UtcTime.ToString("O"), data });
        File.AppendAllText(_journal, line + "\n");
    }
}
