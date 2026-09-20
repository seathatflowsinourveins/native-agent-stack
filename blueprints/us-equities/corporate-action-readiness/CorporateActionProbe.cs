using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text.Json;
using QuantConnect;
using QuantConnect.Configuration;
using QuantConnect.Data.Auxiliary;
using QuantConnect.Data.Market;
using QuantConnect.Securities;

public static class CorporateActionProbe
{
    static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
    static string Num(decimal value) => value.ToString(Inv);
    static string Day(DateTime value) => value.ToString("yyyy-MM-dd", Inv);

    static decimal ScaleAtDecision(CorporateFactorProvider provider, DateTime barDate, DateTime decision)
    {
        if (barDate > decision) throw new ArgumentException("bar date exceeds decision cutoff");
        return provider.GetPriceScale(barDate, DataNormalizationMode.ScaledRaw, endDateTime: decision);
    }

    public static void Main(string[] args)
    {
        if (args.Length != 1) throw new ArgumentException("one output path required");
        Config.Set("data-folder", "/data");
        var start = new DateTime(2020, 8, 3);
        var end = new DateTime(2020, 9, 4);
        var pre = new DateTime(2020, 8, 28);
        var factorRows = CorporateFactorRow.Parse(File.ReadLines("/data/equity/usa/factor_files/aapl.csv"), out var minimum);
        if (factorRows.Count == 0) throw new Exception("empty factor input");
        var provider = new CorporateFactorProvider("AAPL", factorRows, minimum);
        var map = new MapFile("AAPL", File.ReadLines("/data/equity/usa/map_files/aapl.csv")
            .Select(line => MapFileRow.Parse(line, Market.USA, SecurityType.Equity)));
        var symbol = new Symbol(SecurityIdentifier.GenerateEquity(new DateTime(1998, 1, 2), "AAPL", Market.USA), "AAPL");
        var hours = MarketHoursDatabase.FromDataFolder().GetExchangeHours(Market.USA, symbol, SecurityType.Equity);
        var events = provider.GetSplitsAndDividends(symbol, hours).Where(x => x.Time.Date >= start && x.Time.Date <= end).ToList();
        var eventRows = new List<object>();
        foreach (var item in events)
        {
            if (item is Split split)
                eventRows.Add(new { kind = "split", date = Day(split.Time), factor = Num(split.SplitFactor),
                    reference_price = Num(split.ReferencePrice), split_type = split.Type.ToString() });
            else if (item is Dividend dividend)
                eventRows.Add(new { kind = "dividend", date = Day(dividend.Time), distribution = Num(dividend.Distribution),
                    reference_price = Num(dividend.ReferencePrice),
                    units = "native cash distribution per raw share at event; no holdings multiplication" });
            else throw new Exception("unexpected native event type");
        }
        var observations = new List<Dictionary<string, object>>();
        using (var zip = ZipFile.OpenRead("/data/equity/usa/daily/aapl.zip"))
        {
            if (zip.Entries.Count != 1) throw new Exception("unexpected daily zip schema");
            using var reader = new StreamReader(zip.Entries[0].Open());
            string line;
            while ((line = reader.ReadLine()) != null)
            {
                var cells = line.Split(',');
                if (cells.Length != 6) throw new Exception("unexpected bar schema");
                var date = DateTime.ParseExact(cells[0], "yyyyMMdd HH:mm", Inv).Date;
                if (date < start || date > end) continue;
                var close = decimal.Parse(cells[4], Inv) / 10000m;
                if (close <= 0 || date < map.FirstDate || date > map.DelistingDate) throw new Exception("unsupported bar or mapping date");
                var mapped = map.GetMappedSymbol(date);
                if (mapped != "AAPL") throw new Exception("unexpected mapped symbol");
                var scaling = provider.GetScalingFactors(date);
                var adjusted = provider.GetPriceFactor(date, DataNormalizationMode.Adjusted);
                var split = provider.GetPriceFactor(date, DataNormalizationMode.SplitAdjusted);
                var endScale = ScaleAtDecision(provider, date, end);
                var row = new Dictionary<string, object> {
                    ["date"] = Day(date), ["mapped_symbol"] = mapped, ["raw_close"] = Num(close),
                    ["raw_factor_sentinel"] = Num(provider.GetPriceFactor(date, DataNormalizationMode.Raw)),
                    ["factor_row_date"] = Day(scaling.Date), ["factor_reference_price"] = Num(scaling.ReferencePrice),
                    ["price_factor"] = Num(scaling.PriceFactor), ["split_factor"] = Num(split),
                    ["split_adjusted_close"] = Num(close * split), ["adjusted_factor"] = Num(adjusted),
                    ["adjusted_close"] = Num(close * adjusted),
                    ["total_return_factor"] = Num(provider.GetPriceFactor(date, DataNormalizationMode.TotalReturn)),
                    ["end_basis"] = Day(end), ["end_basis_scale"] = Num(endScale), ["end_basis_scaled_close"] = Num(close * endScale)
                };
                if (date <= pre)
                {
                    var preScale = ScaleAtDecision(provider, date, pre);
                    row["pre_basis"] = Day(pre); row["pre_basis_scale"] = Num(preScale);
                    row["pre_basis_scaled_close"] = Num(close * preScale);
                }
                if (provider.HasDividendEventOnNextTradingDay(date, out var ratio, out var dividendRef))
                {
                    row["next_session_dividend_ratio"] = Num(ratio);
                    row["next_session_dividend_reference_price"] = Num(dividendRef);
                }
                if (provider.HasSplitEventOnNextTradingDay(date, out var splitRatio, out var splitRef))
                {
                    row["next_session_split_factor"] = Num(splitRatio);
                    row["next_session_split_reference_price"] = Num(splitRef);
                }
                observations.Add(row);
            }
        }
        if (observations.Count != 25 || observations.Select(r => r["date"]).Distinct().Count() != 25)
            throw new Exception("session coverage mismatch");
        bool implicitBasisRejected = false, futureBarRejected = false;
        try { provider.GetPriceScale(pre, DataNormalizationMode.ScaledRaw); }
        catch (ArgumentException) { implicitBasisRejected = true; }
        try { ScaleAtDecision(provider, end, pre); }
        catch (ArgumentException) { futureBarRejected = true; }
        if (!implicitBasisRejected || !futureBarRejected) throw new Exception("causal guard did not reject");
        var output = new {
            symbol = "AAPL", start = Day(start), end = Day(end), observations, events = eventRows,
            minimum_factor_date = minimum.HasValue ? Day(minimum.Value) : null,
            map_first_date = Day(map.FirstDate), map_last_date = Day(map.DelistingDate),
            map_last_date_is_source_sentinel_not_accepted_actual_delisting = true,
            guards = new { implicit_scaled_raw_basis_rejected = implicitBasisRejected, future_bar_for_decision_rejected = futureBarRejected },
            total_return_series_computed = false, orders_submitted = false, original_observation_time = "unknown"
        };
        using var stream = new FileStream(args[0], FileMode.CreateNew);
        JsonSerializer.Serialize(stream, output, new JsonSerializerOptions { WriteIndented = true });
        Console.WriteLine($"AAPL sessions={observations.Count}, native events={events.Count}, expected guard rejections=2");
    }
}
