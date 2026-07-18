using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using NodaTime;
using QuantConnect;
using QuantConnect.Brokerages;
using QuantConnect.Data.Market;
using QuantConnect.Orders;
using QuantConnect.Securities;

namespace CodexStock.LeanAdvancedWorker;

internal static class Program
{
    private static readonly string[] ForbiddenKeyParts =
    {
        "account_number", "approval", "broker_token", "kis_", "order_token", "password", "secret",
    };

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = false,
    };

    public static int Main(string[] args)
    {
        if (args.Contains("--probe", StringComparer.OrdinalIgnoreCase))
        {
            Write(new Dictionary<string, object?>
            {
                ["ok"] = true,
                ["schema"] = "codexstock_lean_advanced_probe_v1",
                ["engine_name"] = "QuantConnect Lean",
                ["adapter_mode"] = "lean_market_lifecycle_validation_v1",
                ["live_order_allowed"] = false,
            });
            return 0;
        }

        try
        {
            using var document = JsonDocument.Parse(Console.In.ReadToEnd());
            var result = Run(document.RootElement);
            Write(result);
            return result.TryGetValue("ok", out var ok) && ok is true ? 0 : 1;
        }
        catch (Exception exception)
        {
            Write(new Dictionary<string, object?>
            {
                ["ok"] = false,
                ["schema"] = "codexstock_lean_market_lifecycle_v1",
                ["engine_name"] = "QuantConnect Lean",
                ["error"] = exception.Message[..Math.Min(exception.Message.Length, 600)],
                ["decision"] = "BLOCKED",
                ["live_order_allowed"] = false,
            });
            return 1;
        }
    }

    private static Dictionary<string, object?> Run(JsonElement root)
    {
        AssertResearchOnly(root, "request");
        if (GetString(root, "action") != "validate_market_lifecycle")
        {
            throw new InvalidOperationException("unsupported_action");
        }
        if (!root.TryGetProperty("live_order_allowed", out var liveOrder) || liveOrder.ValueKind != JsonValueKind.False)
        {
            throw new InvalidOperationException("live_order_allowed_must_be_false");
        }

        var started = DateTime.UtcNow;
        var snapshot = RequiredObject(root, "snapshot");
        var rows = RequiredArray(snapshot, "dataset_rows");
        if (rows.GetArrayLength() == 0)
        {
            throw new InvalidOperationException("dataset_rows_required");
        }
        var market = GetString(root, "market");
        if (string.IsNullOrWhiteSpace(market)) market = "KR";
        var marketCode = market.Equals("US", StringComparison.OrdinalIgnoreCase) ? Market.USA : "krx";
        if (marketCode == "krx") Market.Add(marketCode, 900);
        var currency = market.Equals("US", StringComparison.OrdinalIgnoreCase) ? "USD" : "KRW";
        var tickSize = currency == "KRW" ? 1m : 0.01m;
        var symbols = rows.EnumerateArray()
            .Select(row => GetString(row, "symbol"))
            .Where(symbol => !string.IsNullOrWhiteSpace(symbol))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(symbol => symbol, StringComparer.Ordinal)
            .ToList();
        if (symbols.Count == 0)
        {
            throw new InvalidOperationException("snapshot_symbols_required");
        }

        var holidays = ParseDateArray(root, "holidays");
        var exchangeHours = BuildExchangeHours(market, holidays);
        var intervals = ParseUniverseIntervals(root, marketCode);
        var intervalViolations = new List<Dictionary<string, object?>>();
        var exchangeViolations = new List<Dictionary<string, object?>>();
        var referencePrices = new Dictionary<string, decimal>(StringComparer.OrdinalIgnoreCase);
        var checkedRows = 0;
        foreach (var row in rows.EnumerateArray())
        {
            var symbolText = GetString(row, "symbol");
            var date = ParseDate(GetString(row, "date"));
            var close = GetDecimal(row, "close");
            if (string.IsNullOrWhiteSpace(symbolText) || date == default || close <= 0m)
            {
                exchangeViolations.Add(new Dictionary<string, object?>
                {
                    ["symbol"] = symbolText,
                    ["date"] = date == default ? "" : date.ToString("yyyy-MM-dd"),
                    ["reason"] = "invalid_snapshot_row",
                });
                continue;
            }
            checkedRows++;
            referencePrices.TryAdd(symbolText, close);
            var localNoon = date.Date.AddHours(12);
            if (!exchangeHours.IsDateOpen(date.Date, false) || !exchangeHours.IsOpen(localNoon, false))
            {
                exchangeViolations.Add(new Dictionary<string, object?>
                {
                    ["symbol"] = symbolText,
                    ["date"] = date.ToString("yyyy-MM-dd"),
                    ["reason"] = "row_outside_lean_exchange_calendar",
                });
            }
            var matchingInterval = intervals.FirstOrDefault(interval =>
                interval.Symbol.Value.Equals(symbolText, StringComparison.OrdinalIgnoreCase)
                && date.Date >= interval.Start.Date
                && (interval.End is null || date.Date <= interval.End.Value.Date));
            if (matchingInterval is null)
            {
                intervalViolations.Add(new Dictionary<string, object?>
                {
                    ["symbol"] = symbolText,
                    ["date"] = date.ToString("yyyy-MM-dd"),
                    ["reason"] = "outside_point_in_time_universe",
                });
            }
        }

        var corporateActionEvidence = ValidateCorporateActions(root, marketCode, referencePrices);
        var delistingEvidence = ValidateDelistings(intervals, referencePrices);
        var brokerageEvidence = ValidateBrokerage(
            symbols,
            marketCode,
            currency,
            tickSize,
            exchangeHours,
            referencePrices);

        var universePassed = intervals.Count > 0 && intervalViolations.Count == 0;
        var exchangePassed = checkedRows > 0 && exchangeViolations.Count == 0;
        var corporateHistoryChecked = root.TryGetProperty("corporate_action_history_checked", out var historyChecked)
                                      && historyChecked.ValueKind == JsonValueKind.True;
        var corporatePassed = corporateHistoryChecked && (bool)corporateActionEvidence["passed"]!;
        var delistingPassed = (bool)delistingEvidence["passed"]!;
        var brokeragePassed = (bool)brokerageEvidence["passed"]!;
        var blockers = new List<string>();
        if (!universePassed) blockers.Add("point_in_time_universe_validation_failed");
        if (!exchangePassed) blockers.Add("lean_exchange_calendar_validation_failed");
        if (!corporatePassed) blockers.Add("corporate_action_history_validation_failed");
        if (!delistingPassed) blockers.Add("delisting_validation_failed");
        if (!brokeragePassed) blockers.Add("lean_brokerage_order_contract_failed");
        var qualityPassed = blockers.Count == 0;

        var resultMaterial = new Dictionary<string, object?>
        {
            ["snapshot_id"] = GetString(root, "snapshot_id"),
            ["dataset_hash"] = GetString(root, "dataset_hash"),
            ["interval_violations"] = intervalViolations,
            ["exchange_violations"] = exchangeViolations,
            ["corporate_actions"] = corporateActionEvidence,
            ["delistings"] = delistingEvidence,
            ["brokerage"] = brokerageEvidence,
        };
        var resultHash = Sha256(JsonSerializer.Serialize(resultMaterial, JsonOptions));
        return new Dictionary<string, object?>
        {
            ["ok"] = true,
            ["schema"] = "codexstock_lean_market_lifecycle_v1",
            ["action"] = "validate_market_lifecycle",
            ["engine_name"] = "QuantConnect Lean",
            ["adapter_mode"] = "lean_market_lifecycle_validation_v1",
            ["engine_commit"] = GetString(root, "engine_commit"),
            ["runtime_mode"] = "spawn_on_demand_only",
            ["snapshot_id"] = GetString(root, "snapshot_id"),
            ["dataset_hash"] = GetString(root, "dataset_hash"),
            ["market"] = market,
            ["symbol_count"] = symbols.Count,
            ["checked_row_count"] = checkedRows,
            ["universe_interval_count"] = intervals.Count,
            ["point_in_time_universe_evidence"] = new Dictionary<string, object?>
            {
                ["passed"] = universePassed,
                ["violation_count"] = intervalViolations.Count,
                ["violations"] = intervalViolations.Take(50).ToList(),
            },
            ["exchange_calendar_evidence"] = new Dictionary<string, object?>
            {
                ["passed"] = exchangePassed,
                ["timezone"] = market.Equals("US", StringComparison.OrdinalIgnoreCase) ? "America/New_York" : "Asia/Seoul",
                ["holiday_count"] = holidays.Count,
                ["violation_count"] = exchangeViolations.Count,
                ["violations"] = exchangeViolations.Take(50).ToList(),
            },
            ["corporate_action_evidence"] = corporateActionEvidence,
            ["delisting_evidence"] = delistingEvidence,
            ["brokerage_evidence"] = brokerageEvidence,
            ["quality_gate"] = new Dictionary<string, object?>
            {
                ["passed"] = qualityPassed,
                ["point_in_time_universe_passed"] = universePassed,
                ["exchange_calendar_passed"] = exchangePassed,
                ["corporate_actions_passed"] = corporatePassed,
                ["delistings_passed"] = delistingPassed,
                ["brokerage_contract_passed"] = brokeragePassed,
                ["blockers"] = blockers,
            },
            ["research_verdict"] = qualityPassed ? "MARKET_LIFECYCLE_VERIFIED" : "REPAIR_DATA_OR_RULES",
            ["capability_evidence"] = new List<Dictionary<string, object?>>
            {
                new() { ["capability"] = "lean_point_in_time_universe", ["passed"] = universePassed },
                new() { ["capability"] = "lean_exchange_hours", ["passed"] = exchangePassed },
                new() { ["capability"] = "lean_corporate_actions", ["passed"] = corporatePassed },
                new() { ["capability"] = "lean_delisting_events", ["passed"] = delistingPassed },
                new() { ["capability"] = "lean_brokerage_model", ["passed"] = brokeragePassed },
                new() { ["capability"] = "live_order_boundary", ["passed"] = true, ["live_order_allowed"] = false },
            },
            ["result_hash"] = resultHash,
            ["execution_time_ms"] = Math.Round((DateTime.UtcNow - started).TotalMilliseconds, 3),
            ["promotion_allowed"] = false,
            ["network_access_allowed"] = false,
            ["decision"] = "RESEARCH_ONLY",
            ["live_order_allowed"] = false,
        };
    }

    private static SecurityExchangeHours BuildExchangeHours(string market, List<DateTime> holidays)
    {
        var timezone = DateTimeZoneProviders.Tzdb[
            market.Equals("US", StringComparison.OrdinalIgnoreCase) ? "America/New_York" : "Asia/Seoul"];
        var open = market.Equals("US", StringComparison.OrdinalIgnoreCase)
            ? new TimeSpan(9, 30, 0)
            : new TimeSpan(9, 0, 0);
        var close = market.Equals("US", StringComparison.OrdinalIgnoreCase)
            ? new TimeSpan(16, 0, 0)
            : new TimeSpan(15, 30, 0);
        var weekly = new Dictionary<DayOfWeek, LocalMarketHours>();
        foreach (var day in Enum.GetValues<DayOfWeek>())
        {
            weekly[day] = day is DayOfWeek.Saturday or DayOfWeek.Sunday
                ? new LocalMarketHours(day, Array.Empty<MarketHoursSegment>())
                : new LocalMarketHours(day, open, close);
        }
        return new SecurityExchangeHours(
            timezone,
            holidays.Select(date => date.Date),
            weekly,
            new Dictionary<DateTime, TimeSpan>(),
            new Dictionary<DateTime, TimeSpan>(),
            Array.Empty<DateTime>());
    }

    private static List<UniverseInterval> ParseUniverseIntervals(JsonElement root, string marketCode)
    {
        var result = new List<UniverseInterval>();
        if (!root.TryGetProperty("universe_intervals", out var intervals) || intervals.ValueKind != JsonValueKind.Array)
        {
            return result;
        }
        foreach (var row in intervals.EnumerateArray())
        {
            var ticker = GetString(row, "symbol");
            var startText = GetString(row, "start_date");
            if (string.IsNullOrWhiteSpace(startText)) startText = GetString(row, "listing_date");
            var start = ParseDate(startText);
            var endText = GetString(row, "end_date");
            if (string.IsNullOrWhiteSpace(endText)) endText = GetString(row, "delisting_date");
            DateTime? end = string.IsNullOrWhiteSpace(endText) ? null : ParseDate(endText);
            var delisted = GetBool(row, "delisted")
                           || GetString(row, "status").Contains("delist", StringComparison.OrdinalIgnoreCase);
            if (string.IsNullOrWhiteSpace(ticker) || start == default) continue;
            result.Add(new UniverseInterval(CreateEquitySymbol(ticker, marketCode), start, end, delisted));
        }
        return result;
    }

    private static Dictionary<string, object?> ValidateCorporateActions(
        JsonElement root,
        string marketCode,
        Dictionary<string, decimal> referencePrices)
    {
        var records = new List<Dictionary<string, object?>>();
        var errors = new List<string>();
        if (root.TryGetProperty("corporate_actions", out var actions) && actions.ValueKind == JsonValueKind.Array)
        {
            foreach (var row in actions.EnumerateArray())
            {
                var ticker = GetString(row, "symbol");
                var date = ParseDate(GetString(row, "date"));
                var dividend = GetDecimal(row, "dividend");
                var splitRatio = GetDecimal(row, "split_ratio");
                if (string.IsNullOrWhiteSpace(ticker) || date == default)
                {
                    errors.Add("invalid_corporate_action_identity");
                    continue;
                }
                var symbol = CreateEquitySymbol(ticker, marketCode);
                var referencePrice = referencePrices.GetValueOrDefault(ticker, 1m);
                if (dividend > 0m)
                {
                    _ = new Dividend(symbol, date, dividend, referencePrice);
                    records.Add(new Dictionary<string, object?>
                    {
                        ["symbol"] = ticker, ["date"] = date.ToString("yyyy-MM-dd"),
                        ["type"] = "dividend", ["distribution"] = dividend,
                    });
                }
                if (splitRatio > 0m && splitRatio != 1m)
                {
                    var leanSplitFactor = 1m / splitRatio;
                    _ = new Split(symbol, date, referencePrice, leanSplitFactor, SplitType.SplitOccurred);
                    records.Add(new Dictionary<string, object?>
                    {
                        ["symbol"] = ticker, ["date"] = date.ToString("yyyy-MM-dd"),
                        ["type"] = "split", ["source_split_ratio"] = splitRatio,
                        ["lean_split_factor"] = leanSplitFactor,
                    });
                }
            }
        }
        return new Dictionary<string, object?>
        {
            ["passed"] = errors.Count == 0,
            ["event_count"] = records.Count,
            ["events"] = records.Take(100).ToList(),
            ["errors"] = errors,
            ["constructor_contract"] = "QuantConnect.Data.Market.Dividend/Split",
        };
    }

    private static Dictionary<string, object?> ValidateDelistings(
        List<UniverseInterval> intervals,
        Dictionary<string, decimal> referencePrices)
    {
        var records = new List<Dictionary<string, object?>>();
        var errors = new List<string>();
        foreach (var interval in intervals.Where(interval => interval.Delisted))
        {
            if (interval.End is null)
            {
                errors.Add($"delisted_interval_without_end:{interval.Symbol.Value}");
                continue;
            }
            var price = referencePrices.GetValueOrDefault(interval.Symbol.Value, 1m);
            _ = new Delisting(interval.Symbol, interval.End.Value, price, DelistingType.Delisted);
            records.Add(new Dictionary<string, object?>
            {
                ["symbol"] = interval.Symbol.Value,
                ["date"] = interval.End.Value.ToString("yyyy-MM-dd"),
                ["type"] = "delisted",
            });
        }
        return new Dictionary<string, object?>
        {
            ["passed"] = errors.Count == 0,
            ["event_count"] = records.Count,
            ["events"] = records,
            ["errors"] = errors,
            ["constructor_contract"] = "QuantConnect.Data.Market.Delisting",
        };
    }

    private static Dictionary<string, object?> ValidateBrokerage(
        List<string> symbols,
        string marketCode,
        string currency,
        decimal tickSize,
        SecurityExchangeHours exchangeHours,
        Dictionary<string, decimal> referencePrices)
    {
        var brokerage = new DefaultBrokerageModel(AccountType.Cash);
        var records = new List<Dictionary<string, object?>>();
        foreach (var ticker in symbols)
        {
            var symbol = CreateEquitySymbol(ticker, marketCode);
            var properties = new SymbolProperties(
                ticker, currency, 1m, tickSize, 1m, ticker, 1m, 1m, 1m);
            var security = new Security(
                symbol,
                exchangeHours,
                new Cash(currency, 100_000_000m, 1m),
                properties,
                new IdentityCurrencyConverter(currency),
                new RegisteredSecurityDataTypesProvider(),
                new SecurityCache());
            var now = DateTime.UtcNow;
            var orderProperties = new OrderProperties();
            var marketOrder = new MarketOrder(symbol, 1m, now, "research-validation", orderProperties);
            var limitPrice = referencePrices.GetValueOrDefault(ticker, tickSize);
            var limitOrder = new LimitOrder(symbol, 1m, limitPrice, now, "research-validation", orderProperties);
            var marketSubmit = brokerage.CanSubmitOrder(security, marketOrder, out var marketMessage);
            var limitSubmit = brokerage.CanSubmitOrder(security, limitOrder, out var limitMessage);
            var sizeValid = DefaultBrokerageModel.IsValidOrderSize(security, 1m, out var sizeMessage);
            var buyingPowerModel = brokerage.GetBuyingPowerModel(security);
            records.Add(new Dictionary<string, object?>
            {
                ["symbol"] = ticker,
                ["market_order_can_submit"] = marketSubmit,
                ["limit_order_can_submit"] = limitSubmit,
                ["one_share_size_valid"] = sizeValid,
                ["buying_power_model"] = buyingPowerModel.GetType().Name,
                ["market_message"] = marketMessage?.Message ?? "",
                ["limit_message"] = limitMessage?.Message ?? "",
                ["size_message"] = sizeMessage?.Message ?? "",
            });
        }
        return new Dictionary<string, object?>
        {
            ["passed"] = records.Count > 0 && records.All(row =>
                row["market_order_can_submit"] is true
                && row["limit_order_can_submit"] is true
                && row["one_share_size_valid"] is true),
            ["brokerage_model"] = nameof(DefaultBrokerageModel),
            ["account_type"] = AccountType.Cash.ToString(),
            ["checked_symbol_count"] = records.Count,
            ["checks"] = records,
            ["orders_transmitted"] = 0,
        };
    }

    private static void AssertResearchOnly(JsonElement value, string path)
    {
        if (value.ValueKind == JsonValueKind.Object)
        {
            foreach (var property in value.EnumerateObject())
            {
                if (ForbiddenKeyParts.Any(part => property.Name.Contains(part, StringComparison.OrdinalIgnoreCase)))
                {
                    throw new InvalidOperationException($"forbidden_input_field:{path}.{property.Name}");
                }
                AssertResearchOnly(property.Value, $"{path}.{property.Name}");
            }
        }
        else if (value.ValueKind == JsonValueKind.Array)
        {
            var index = 0;
            foreach (var child in value.EnumerateArray())
            {
                AssertResearchOnly(child, $"{path}[{index++}]");
            }
        }
    }

    private static JsonElement RequiredObject(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Object)
            throw new InvalidOperationException($"{name}_required");
        return value;
    }

    private static JsonElement RequiredArray(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Array)
            throw new InvalidOperationException($"{name}_required");
        return value;
    }

    private static string GetString(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out var value)) return string.Empty;
        return value.ValueKind == JsonValueKind.String ? value.GetString() ?? string.Empty : value.ToString();
    }

    private static decimal GetDecimal(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out var value)) return 0m;
        if (value.ValueKind == JsonValueKind.Number && value.TryGetDecimal(out var number)) return number;
        return decimal.TryParse(value.ToString(), NumberStyles.Any, CultureInfo.InvariantCulture, out number) ? number : 0m;
    }

    private static bool GetBool(JsonElement parent, string name)
    {
        return parent.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.True;
    }

    private static DateTime ParseDate(string value)
    {
        return DateTime.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var parsed)
            ? DateTime.SpecifyKind(parsed.Date, DateTimeKind.Unspecified)
            : default;
    }

    private static List<DateTime> ParseDateArray(JsonElement parent, string name)
    {
        var result = new List<DateTime>();
        if (!parent.TryGetProperty(name, out var values) || values.ValueKind != JsonValueKind.Array) return result;
        foreach (var value in values.EnumerateArray())
        {
            var parsed = ParseDate(value.ToString());
            if (parsed != default) result.Add(parsed);
        }
        return result;
    }

    private static string Sha256(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    }

    private static Symbol CreateEquitySymbol(string ticker, string marketCode)
    {
        return new Symbol(SecurityIdentifier.GenerateEquity(ticker, marketCode, mapSymbol: false), ticker);
    }

    private static void Write(Dictionary<string, object?> payload)
    {
        Console.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
    }

    private sealed record UniverseInterval(Symbol Symbol, DateTime Start, DateTime? End, bool Delisted);
}
