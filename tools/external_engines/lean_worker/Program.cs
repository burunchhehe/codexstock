using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using QuantConnect.Indicators;

internal static class Program
{
    private const string EngineCommit = "046fb456f8282c1749e42fcf7f8fa45fa4595d74";
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private static int Main(string[] args)
    {
        if (args.Contains("--probe", StringComparer.Ordinal))
        {
            WriteJson(new
            {
                ok = true,
                engine_name = "QuantConnect Lean",
                adapter_mode = "lean_indicator_cross_validation_v1",
                engine_commit = EngineCommit,
                live_order_allowed = false,
            });
            return 0;
        }

        try
        {
            using var document = JsonDocument.Parse(Console.In.ReadToEnd());
            if (ContainsForbiddenKey(document.RootElement))
            {
                throw new InvalidOperationException("forbidden_input_field");
            }
            var request = document.RootElement.Deserialize<WorkerRequest>(JsonOptions)
                ?? throw new InvalidOperationException("request_required");
            var result = Run(request);
            WriteJson(result);
            return result.Ok ? 0 : 1;
        }
        catch (Exception exception)
        {
            WriteJson(new
            {
                ok = false,
                schema = "codexstock_lean_crosscheck_result_v1",
                engine_name = "QuantConnect Lean",
                error = exception.Message.Length > 600 ? exception.Message[..600] : exception.Message,
                decision = "BLOCKED",
                live_order_allowed = false,
            });
            return 1;
        }
    }

    private static WorkerResult Run(WorkerRequest request)
    {
        var started = System.Diagnostics.Stopwatch.StartNew();
        if (!string.Equals(request.Action, "run_external_backtest", StringComparison.Ordinal))
        {
            throw new InvalidOperationException("unsupported_action");
        }
        if (request.LiveOrderAllowed)
        {
            throw new InvalidOperationException("live_order_allowed_must_be_false");
        }
        if (request.Snapshot?.DatasetRows is not { Count: > 0 } rows)
        {
            throw new InvalidOperationException("dataset_rows_required");
        }

        var fastWindow = Math.Clamp(request.FastWindow <= 0 ? 10 : request.FastWindow, 2, 60);
        var slowWindow = Math.Clamp(request.SlowWindow <= 0 ? 60 : request.SlowWindow, fastWindow + 1, 200);
        var feeRate = Math.Clamp(request.FeeRate <= 0 ? 0.0015m : request.FeeRate, 0m, 0.02m);
        var slippageRate = Math.Clamp(request.SlippageRate <= 0 ? 0.001m : request.SlippageRate, 0m, 0.02m);
        var initialCash = request.InitialCash < 10_000m ? 10_000_000m : request.InitialCash;

        var symbolResults = rows
            .Where(row => !string.IsNullOrWhiteSpace(row.Symbol))
            .GroupBy(row => row.Symbol, StringComparer.Ordinal)
            .OrderBy(group => group.Key, StringComparer.Ordinal)
            .Take(5)
            .Select(group => CrossCheckSymbol(
                group.Key,
                group.OrderBy(row => row.Date, StringComparer.Ordinal).ToList(),
                fastWindow,
                slowWindow,
                feeRate,
                slippageRate,
                initialCash))
            .ToList();
        var reconciliationOk = symbolResults.Count > 0 && symbolResults.All(row => row.Ok && row.Reconciliation.Ok);
        var resultMaterial = JsonSerializer.Serialize(new
        {
            request.SnapshotId,
            request.DatasetHash,
            engine_commit = EngineCommit,
            symbol_results = symbolResults,
        }, JsonOptions);
        var resultHash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(resultMaterial))).ToLowerInvariant();
        started.Stop();
        return new WorkerResult
        {
            Ok = reconciliationOk,
            Schema = "codexstock_lean_crosscheck_result_v1",
            Action = request.Action,
            EngineName = "QuantConnect Lean",
            EngineCommit = EngineCommit,
            AdapterMode = "lean_indicator_cross_validation_v1",
            RuntimeMode = "spawn_on_demand_only",
            SnapshotId = request.SnapshotId,
            DatasetHash = request.DatasetHash,
            FastWindow = fastWindow,
            SlowWindow = slowWindow,
            SymbolCount = symbolResults.Count,
            SuccessfulSymbolCount = symbolResults.Count(row => row.Ok),
            SymbolResults = symbolResults,
            ReconciliationOk = reconciliationOk,
            ResultHash = resultHash,
            ExecutionTimeMs = Math.Round(started.Elapsed.TotalMilliseconds, 3),
            Decision = "VERIFY_ONLY",
            LiveOrderAllowed = false,
        };
    }

    private static SymbolResult CrossCheckSymbol(
        string symbol,
        List<DatasetRow> rows,
        int fastWindow,
        int slowWindow,
        decimal feeRate,
        decimal slippageRate,
        decimal initialCash)
    {
        var errors = new List<string>();
        var currency = rows.LastOrDefault()?.Currency?.ToUpperInvariant() ?? "";
        var priceUnit = rows.LastOrDefault()?.PriceUnit ?? "";
        if (currency is not ("KRW" or "USD")) errors.Add("unsupported_currency");
        if (rows.Count < slowWindow + 2) errors.Add("insufficient_rows");
        if (rows.Any(row => row.Close <= 0m)) errors.Add("non_positive_close_price");
        if (rows.Any(row => !string.Equals(row.Currency, currency, StringComparison.OrdinalIgnoreCase)))
            errors.Add("currency_mismatch");
        if (rows.Any(row => !string.Equals(row.PriceUnit, priceUnit, StringComparison.Ordinal)))
            errors.Add("price_unit_mismatch");
        if (errors.Count > 0)
        {
            return new SymbolResult
            {
                Symbol = symbol,
                Ok = false,
                Currency = currency,
                PriceUnit = priceUnit,
                RowCount = rows.Count,
                Reconciliation = new Reconciliation { Ok = false, Errors = errors },
            };
        }

        var fast = new SimpleMovingAverage(fastWindow);
        var slow = new SimpleMovingAverage(slowWindow);
        var cash = initialCash;
        var holding = false;
        var orderId = 0;
        var fills = new List<FillRecord>();
        foreach (var row in rows)
        {
            var timestamp = DateTime.Parse(row.Date, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);
            fast.Update(timestamp, row.Close);
            slow.Update(timestamp, row.Close);
            if (!slow.IsReady) continue;
            if (!holding && fast.Current.Value > slow.Current.Value)
            {
                var fillPrice = row.Close * (1m + slippageRate);
                var fee = fillPrice * feeRate;
                cash -= fillPrice + fee;
                holding = true;
                fills.Add(new FillRecord(++orderId, row.Date, "BUY", fillPrice, fee, "ma_cross_up", currency));
            }
            else if (holding && fast.Current.Value < slow.Current.Value)
            {
                var fillPrice = row.Close * (1m - slippageRate);
                var fee = fillPrice * feeRate;
                cash += fillPrice - fee;
                holding = false;
                fills.Add(new FillRecord(++orderId, row.Date, "SELL", fillPrice, fee, "ma_cross_down", currency));
            }
        }
        if (holding)
        {
            var row = rows[^1];
            var fillPrice = row.Close * (1m - slippageRate);
            var fee = fillPrice * feeRate;
            cash += fillPrice - fee;
            holding = false;
            fills.Add(new FillRecord(++orderId, row.Date, "SELL", fillPrice, fee, "final_bar_flatten", currency));
        }

        var buys = fills.Where(fill => fill.Side == "BUY").ToList();
        var sells = fills.Where(fill => fill.Side == "SELL").ToList();
        if (buys.Count != sells.Count) errors.Add("entry_exit_count_mismatch");
        if (holding) errors.Add("open_position_remains");
        if (fills.Any(fill => fill.FillPrice <= 0m)) errors.Add("non_positive_fill_price");
        if (fills.Any(fill => string.IsNullOrWhiteSpace(fill.Reason))) errors.Add("fill_reason_missing");
        var entry = buys.FirstOrDefault();
        var exit = sells.LastOrDefault();
        var grossReturn = entry is not null && exit is not null && entry.FillPrice > 0m
            ? (exit.FillPrice / entry.FillPrice - 1m) * 100m
            : 0m;
        var netReturn = (cash / initialCash - 1m) * 100m;
        return new SymbolResult
        {
            Symbol = symbol,
            Ok = errors.Count == 0,
            Currency = currency,
            PriceUnit = priceUnit,
            RowCount = rows.Count,
            OrderCount = fills.Count,
            FillCount = fills.Count,
            EntryPrice = entry?.FillPrice ?? 0m,
            ExitPrice = exit?.FillPrice ?? 0m,
            ExitReason = exit?.Reason ?? "no_exit_fill",
            GrossReturnPct = Math.Round(grossReturn, 6),
            NetPortfolioReturnPct = Math.Round(netReturn, 6),
            InitialCash = initialCash,
            FinalCash = Math.Round(cash, 4),
            Fills = fills,
            Reconciliation = new Reconciliation
            {
                Ok = errors.Count == 0,
                Errors = errors,
                OrdersEqualFills = true,
                EntryExitCountsMatch = buys.Count == sells.Count,
                AllCurrenciesMatch = fills.All(fill => fill.Currency == currency),
                AllFillPricesPositive = fills.All(fill => fill.FillPrice > 0m),
                PositionClosed = !holding,
            },
        };
    }

    private static bool ContainsForbiddenKey(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            foreach (var property in element.EnumerateObject())
            {
                var key = property.Name.ToLowerInvariant();
                if (key.Contains("account_number") || key.Contains("approval") || key.Contains("broker_token")
                    || key.Contains("kis_") || key.Contains("order_token") || key.Contains("password") || key.Contains("secret"))
                    return true;
                if (ContainsForbiddenKey(property.Value)) return true;
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (var child in element.EnumerateArray())
                if (ContainsForbiddenKey(child)) return true;
        }
        return false;
    }

    private static void WriteJson(object value) => Console.Write(JsonSerializer.Serialize(value, JsonOptions));
}

internal sealed class WorkerRequest
{
    public string Action { get; set; } = "";
    public string SnapshotId { get; set; } = "";
    public string DatasetHash { get; set; } = "";
    public DatasetSnapshot? Snapshot { get; set; }
    public int FastWindow { get; set; }
    public int SlowWindow { get; set; }
    public decimal InitialCash { get; set; }
    public decimal FeeRate { get; set; }
    public decimal SlippageRate { get; set; }
    public bool LiveOrderAllowed { get; set; }
}

internal sealed class DatasetSnapshot
{
    public List<DatasetRow> DatasetRows { get; set; } = [];
}

internal sealed class DatasetRow
{
    public string Symbol { get; set; } = "";
    public string Date { get; set; } = "";
    public decimal Close { get; set; }
    public string Currency { get; set; } = "";
    public string PriceUnit { get; set; } = "";
}

internal sealed class WorkerResult
{
    public bool Ok { get; set; }
    public string Schema { get; set; } = "";
    public string Action { get; set; } = "";
    public string EngineName { get; set; } = "";
    public string EngineCommit { get; set; } = "";
    public string AdapterMode { get; set; } = "";
    public string RuntimeMode { get; set; } = "";
    public string SnapshotId { get; set; } = "";
    public string DatasetHash { get; set; } = "";
    public int FastWindow { get; set; }
    public int SlowWindow { get; set; }
    public int SymbolCount { get; set; }
    public int SuccessfulSymbolCount { get; set; }
    public List<SymbolResult> SymbolResults { get; set; } = [];
    public bool ReconciliationOk { get; set; }
    public string ResultHash { get; set; } = "";
    public double ExecutionTimeMs { get; set; }
    public string Decision { get; set; } = "";
    public bool LiveOrderAllowed { get; set; }
}

internal sealed class SymbolResult
{
    public string Symbol { get; set; } = "";
    public bool Ok { get; set; }
    public string Currency { get; set; } = "";
    public string PriceUnit { get; set; } = "";
    public int RowCount { get; set; }
    public int OrderCount { get; set; }
    public int FillCount { get; set; }
    public decimal EntryPrice { get; set; }
    public decimal ExitPrice { get; set; }
    public string ExitReason { get; set; } = "";
    public decimal GrossReturnPct { get; set; }
    public decimal NetPortfolioReturnPct { get; set; }
    public decimal InitialCash { get; set; }
    public decimal FinalCash { get; set; }
    public List<FillRecord> Fills { get; set; } = [];
    public Reconciliation Reconciliation { get; set; } = new();
}

internal sealed record FillRecord(
    int OrderId,
    string Date,
    string Side,
    decimal FillPrice,
    decimal Fee,
    string Reason,
    string Currency);

internal sealed class Reconciliation
{
    public bool Ok { get; set; }
    public List<string> Errors { get; set; } = [];
    public bool OrdersEqualFills { get; set; }
    public bool EntryExitCountsMatch { get; set; }
    public bool AllCurrenciesMatch { get; set; }
    public bool AllFillPricesPositive { get; set; }
    public bool PositionClosed { get; set; }
}
