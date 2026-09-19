using System;
using QuantConnect;
using QuantConnect.Algorithm;
using QuantConnect.Data;
using QuantConnect.Orders.Fees;
using QuantConnect.Orders.Fills;
using QuantConnect.Orders.Slippage;

// Local acceptance fixture using upstream LEAN APIs, not an investment strategy.
public class ExecutionSensitivityAlgorithm : QCAlgorithm
{
    private Symbol _spy;
    private bool _entered;
    private bool _exited;

    public override void Initialize()
    {
        if (LiveMode) throw new InvalidOperationException("Backtesting fixture only.");
        SetStartDate(2013, 10, 7);
        SetEndDate(2013, 10, 11);
        SetCash(100000);
        var security = AddEquity("SPY", Resolution.Minute,
            dataNormalizationMode: DataNormalizationMode.Raw);
        _spy = security.Symbol;
        security.SetFeeModel(new ConstantFeeModel(GetParameter("fee-usd", 0m)));
        security.SetSlippageModel(new ConstantSlippageModel(GetParameter("slippage", 0m)));
        security.SetFillModel(new EquityFillModel());
    }

    public override void OnData(Slice data)
    {
        if (!data.Bars.ContainsKey(_spy)) return;
        if (!_entered && Time.Date == new DateTime(2013, 10, 7) && Time.Hour == 10)
        {
            _entered = true;
            MarketOrder(_spy, 100, tag: "fixed-entry");
        }
        if (!_exited && Time.Date == new DateTime(2013, 10, 11) && Time.Hour == 15)
        {
            _exited = true;
            MarketOrder(_spy, -100, tag: "fixed-exit");
        }
    }

    public override void OnEndOfAlgorithm()
    {
        if (!_entered || !_exited || Portfolio.Invested)
            throw new InvalidOperationException("Fixture did not complete its fixed round trip.");
    }
}
