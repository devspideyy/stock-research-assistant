#include "engine.hpp"
#include "accounting.hpp"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <cstdint>
#include <limits>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace finance {
namespace {
constexpr double trading_days = 252.0;

struct Candle {
    std::string timestamp;
    double open, high, low, close, volume;
};

void require(bool condition, const std::string& message) {
    if (!condition) throw std::invalid_argument(message);
}

double number(const json& value, const std::string& name) {
    require(value.is_number() && !value.is_boolean(), name + " must be numeric");
    const double result = value.get<double>();
    require(std::isfinite(result), name + " must be finite");
    return result;
}

double option(const json& options, const std::string& key, double fallback,
              double low, double high) {
    const double value = options.contains(key) ? number(options.at(key), key) : fallback;
    require(value >= low && value <= high, key + " is outside the permitted range");
    return value;
}

int integer_option(const json& options, const std::string& key, int fallback,
                   int low, int high) {
    const double value = option(options, key, fallback, low, high);
    require(std::floor(value) == value, key + " must be an integer");
    return static_cast<int>(value);
}

bool valid_timestamp(const std::string& text) {
    // Uniform ISO dates or second-precision UTC/naive timestamps sort chronologically.
    if (text.size() != 10 && text.size() != 19 && text.size() != 20) return false;
    if (text[4] != '-' || text[7] != '-') return false;
    for (std::size_t i = 0; i < 10; ++i) {
        if (i != 4 && i != 7 && !std::isdigit(static_cast<unsigned char>(text[i]))) return false;
    }
    const int year = std::stoi(text.substr(0, 4));
    const int month = std::stoi(text.substr(5, 2));
    const int day = std::stoi(text.substr(8, 2));
    if (year < 1900 || month < 1 || month > 12 || day < 1) return false;
    int month_days[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)) month_days[1] = 29;
    if (day > month_days[month - 1]) return false;
    if (text.size() > 10) {
        if (text[10] != 'T' || text[13] != ':' || text[16] != ':') return false;
        for (std::size_t i = 11; i < 19; ++i) {
            if (i != 13 && i != 16 && !std::isdigit(static_cast<unsigned char>(text[i]))) return false;
        }
        if (text.size() == 20 && text[19] != 'Z') return false;
        if (std::stoi(text.substr(11, 2)) > 23 || std::stoi(text.substr(14, 2)) > 59 ||
            std::stoi(text.substr(17, 2)) > 59) return false;
    }
    return true;
}

std::vector<Candle> candles_from(const json& request) {
    require(request.contains("candles") && request.at("candles").is_array(), "candles must be an array");
    const auto& rows = request.at("candles");
    require(rows.size() >= 2 && rows.size() <= 100000, "Provide between 2 and 100000 candles");
    std::vector<Candle> candles;
    candles.reserve(rows.size());
    for (const auto& row : rows) {
        require(row.is_object(), "Each candle must be an object");
        require(row.contains("timestamp") && row.at("timestamp").is_string(), "Candle timestamp is required");
        const auto timestamp = row.at("timestamp").get<std::string>();
        require(valid_timestamp(timestamp), "Timestamp must be YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS[Z]");
        if (!candles.empty()) {
            require(timestamp.size() == candles.front().timestamp.size(), "Timestamp formats must be uniform");
            require(timestamp > candles.back().timestamp, "Candles must be strictly chronological, without duplicates");
        }
        for (const std::string key : {"open", "high", "low", "close", "volume"}) {
            require(row.contains(key), "Candle missing " + key);
        }
        Candle c{timestamp, number(row.at("open"), "open"), number(row.at("high"), "high"),
                 number(row.at("low"), "low"), number(row.at("close"), "close"), number(row.at("volume"), "volume")};
        require(c.open > 0 && c.high > 0 && c.low > 0 && c.close > 0, "Prices must be positive");
        require(c.high >= std::max(c.open, c.close) && c.low <= std::min(c.open, c.close), "Invalid OHLC price bounds");
        require(c.volume >= 0, "Volume must be nonnegative");
        require(c.high <= 1e12 && c.volume <= 1e15 && c.low >= 1e-9, "Candle values exceed supported numerical range");
        candles.push_back(c);
    }
    return candles;
}

struct Features {
    std::vector<double> sma, ema, rsi, atr, relative_volume, prior_high, prior_low, return20, structure;
};

std::vector<Candle> signal_candles(const std::vector<Candle>& raw, const accounting::ActionPlan& plan) {
    auto adjusted = raw;
    for (std::size_t i = 0; i < raw.size(); ++i) {
        adjusted[i].open *= plan.price_scale[i];
        adjusted[i].high *= plan.price_scale[i];
        adjusted[i].low *= plan.price_scale[i];
        adjusted[i].close *= plan.price_scale[i];
        adjusted[i].volume /= plan.share_scale[i];
        require(std::isfinite(adjusted[i].high), "Adjusted signal prices exceed numerical range");
    }
    return adjusted;
}

void use_current_share_units(Features& f, const accounting::ActionPlan& plan) {
    for (std::size_t i = 0; i < plan.price_scale.size(); ++i)
        for (auto* series : {&f.sma, &f.ema, &f.atr, &f.prior_high, &f.prior_low})
            (*series)[i] /= plan.price_scale[i];
}

Features calculate(const std::vector<Candle>& candles, int lookback = 20) {
    const auto n = candles.size();
    const double missing = std::numeric_limits<double>::quiet_NaN();
    Features f{std::vector<double>(n, missing), std::vector<double>(n, missing),
               std::vector<double>(n, missing), std::vector<double>(n, missing),
               std::vector<double>(n, missing), std::vector<double>(n, missing),
               std::vector<double>(n, missing), std::vector<double>(n, missing),
               std::vector<double>(n, missing)};
    double close_sum = 0, ema = candles.front().close, gains = 0, losses = 0, atr = 0;
    for (std::size_t i = 0; i < n; ++i) {
        close_sum += candles[i].close;
        if (i >= 20) close_sum -= candles[i - 20].close;
        if (i >= 19) f.sma[i] = close_sum / 20.0;
        if (i > 0) ema += (2.0 / 21.0) * (candles[i].close - ema);
        if (i >= 19) f.ema[i] = ema;

        if (i > 0) {
            const double change = candles[i].close - candles[i - 1].close;
            const double gain = std::max(change, 0.0), loss = std::max(-change, 0.0);
            if (i <= 14) { gains += gain; losses += loss; }
            if (i == 14) { gains /= 14.0; losses /= 14.0; }
            if (i > 14) { gains = (gains * 13 + gain) / 14; losses = (losses * 13 + loss) / 14; }
            if (i >= 14) {
                f.rsi[i] = losses == 0 ? (gains == 0 ? 50.0 : 100.0) : 100.0 - 100.0 / (1 + gains / losses);
            }
        }
        const double true_range = i == 0 ? candles[i].high - candles[i].low :
            std::max({candles[i].high - candles[i].low, std::abs(candles[i].high - candles[i - 1].close),
                      std::abs(candles[i].low - candles[i - 1].close)});
        if (i < 14) atr += true_range;
        if (i == 13) atr /= 14.0;
        if (i > 13) atr = (atr * 13 + true_range) / 14;
        if (i >= 13) f.atr[i] = atr;
        if (i >= 20) {
            f.return20[i] = candles[i].close / candles[i - 20].close - 1;
            // Compare two prior ten-bar ranges; the current candle is excluded.
            double old_high = 0, new_high = 0;
            double old_low = candles[i - 20].low, new_low = candles[i - 10].low;
            for (std::size_t j = i - 20; j < i; ++j) {
                if (j < i - 10) {
                    old_high = std::max(old_high, candles[j].high);
                    old_low = std::min(old_low, candles[j].low);
                } else {
                    new_high = std::max(new_high, candles[j].high);
                    new_low = std::min(new_low, candles[j].low);
                }
            }
            f.structure[i] = new_high > old_high && new_low > old_low ? 1 :
                             new_high < old_high && new_low < old_low ? -1 : 0;
        }

        if (i > 0) {
            const auto start = i > static_cast<std::size_t>(lookback) ? i - lookback : 0;
            double volume = 0;
            f.prior_high[i] = candles[start].high;
            f.prior_low[i] = candles[start].low;
            for (std::size_t j = start; j < i; ++j) {
                volume += candles[j].volume;
                f.prior_high[i] = std::max(f.prior_high[i], candles[j].high);
                f.prior_low[i] = std::min(f.prior_low[i], candles[j].low);
            }
            const double average = volume / static_cast<double>(i - start);
            if (average > 0) f.relative_volume[i] = candles[i].volume / average;
        }
    }
    return f;
}

json nullable(double value) { return std::isfinite(value) ? json(value) : json(nullptr); }

json analyze(const std::vector<Candle>& candles, const json& options) {
    const auto plan = accounting::prepare_actions(candles, options);
    const auto adjusted = signal_candles(candles, plan);
    auto f = calculate(adjusted);
    use_current_share_units(f, plan);
    const auto i = candles.size() - 1;
    const std::string breakout = candles[i].close > f.prior_high[i] ? "up" :
                                 candles[i].close < f.prior_low[i] ? "down" : "none";
    json rows = json::array();
    for (std::size_t k = 0; k < candles.size(); ++k) {
        const auto& c = candles[k];
        rows.push_back({{"timestamp", c.timestamp}, {"open", c.open}, {"high", c.high}, {"low", c.low},
                        {"close", c.close}, {"volume", c.volume}, {"sma20", nullable(f.sma[k])},
                        {"ema20", nullable(f.ema[k])}, {"rsi14", nullable(f.rsi[k])}, {"atr14", nullable(f.atr[k])},
                        {"relative_volume", nullable(f.relative_volume[k])},
                        {"prior_high", nullable(f.prior_high[k])}, {"prior_low", nullable(f.prior_low[k])}});
    }
    return {{"summary", {{"last_close", candles[i].close}, {"return_1d", adjusted[i].close / adjusted[i - 1].close - 1},
                         {"relative_volume", nullable(f.relative_volume[i])}, {"prior_high", f.prior_high[i]},
                         {"prior_low", f.prior_low[i]}, {"breakout", breakout}, {"sma20", nullable(f.sma[i])},
                         {"ema20", nullable(f.ema[i])}, {"rsi14", nullable(f.rsi[i])}, {"atr14", nullable(f.atr[i])},
                         {"return_20d", nullable(f.return20[i])}, {"structure_direction", nullable(f.structure[i])},
                         {"atr_pct", nullable(f.atr[i] / candles[i].close)}}},
            {"series", rows}, {"assumptions", {"Indicators are supporting context, not investment forecasts.",
            "Prior levels and relative volume exclude the current candle; up to 20 prior candles are used.",
            "RSI and ATR use Wilder smoothing; EMA seeds from the first close, with 20-bar display warmup."}}};
}

json backtest(const std::vector<Candle>& candles, const json& options) {
    const std::string strategy = options.value("strategy", std::string("price_volume"));
    require(strategy == "price_volume" || strategy == "buy_hold" || strategy == "indicator" ||
            strategy == "trend_pullback" || strategy == "range_reversion", "Unknown backtest strategy");
    const int lookback = integer_option(options, "lookback", 20, 2, 1000);
    const double initial = option(options, "initial_capital", 100000, 1, 1e12);
    const double max_exposure = option(options, "max_exposure", 1, 0, 1);
    const accounting::CostModel costs(options);
    const double slippage = option(options, "slippage_bps", 5, 0, 1000) / 10000;
    const double stop_loss = option(options, "stop_loss_pct", .08, 0, .99);
    const double volume_threshold = option(options, "volume_threshold", 1.2, 0, 100);
    const int evaluation_start = integer_option(options, "evaluation_start", 0, 0, static_cast<int>(candles.size()) - 2);
    const auto plan = accounting::prepare_actions(candles, options);
    const auto adjusted = signal_candles(candles, plan);
    auto features = calculate(adjusted, lookback);
    use_current_share_units(features, plan);
    double cash = initial, position = 0, entry_price = 0, peak = initial, previous_equity = initial;
    double max_drawdown = 0, traded_notional = 0, sum_exposure = 0;
    int pending = 0;
    double entry_fee = 0, fees_paid = 0, gross_profit = 0, gross_loss = 0, realised_pnl = 0;
    int closed_trades = 0, wins = 0;
    double receivable = 0, dividend_income = 0, dividend_paid = 0, lot_dividends = 0, stop_reference = 0;
    struct Payment { std::string date; double amount; };
    std::vector<Payment> payments;
    json action_ledger = json::array(), fee_totals = json::object();
    const auto record_costs = [&](const accounting::Costs& fee) {
        for (const auto& part : fee.parts.items()) if (part.value().is_number())
            fee_totals[part.key()] = fee_totals.value(part.key(), 0.0) + part.value().get<double>();
    };
    std::vector<double> returns;
    json equity_curve = json::array(), trades = json::array();

    for (std::size_t i = static_cast<std::size_t>(evaluation_start); i < candles.size(); ++i) {
        const auto& c = candles[i];
        const std::string day = c.timestamp.substr(0, 10);
        for (auto it = payments.begin(); it != payments.end();) {
            if (it->date <= day) {
                cash += it->amount; receivable -= it->amount; dividend_paid += it->amount;
                if (std::abs(receivable) < 1e-8) receivable = 0;
                action_ledger.push_back({{"date", day}, {"type", "dividend_payment"}, {"cash", it->amount}});
                it = payments.erase(it);
            } else ++it;
        }
        for (const auto& action : plan.on_bar[i]) {
            if (action.type != "cash_dividend") {
                const double changed = position * action.multiplier;
                require(std::abs(changed - std::round(changed)) < 1e-7,
                        "Fractional share entitlement is unsupported; provide a separate verified cash-in-lieu model");
                action_ledger.push_back({{"date", day}, {"type", action.type}, {"before", position}, {"after", std::round(changed)}, {"source", action.source}});
                position = std::round(changed);
                entry_price /= action.multiplier;
                stop_reference /= action.multiplier;
            } else {
                const double entitlement = position * action.amount;
                dividend_income += entitlement; lot_dividends += entitlement;
                stop_reference = std::max(0.0, stop_reference - action.amount);
                if (action.pay_date <= day) { cash += entitlement; dividend_paid += entitlement; }
                else { receivable += entitlement; payments.push_back({action.pay_date, entitlement}); }
                action_ledger.push_back({{"date", day}, {"type", "dividend_entitlement"}, {"cash", entitlement}, {"pay_date", action.pay_date}, {"source", action.source}});
            }
        }
        // Pending signals were created at the previous close. Current OHLC/volume
        // cannot influence an execution at this candle's open.
        if (i > 0 && pending == -1 && position > 0) {
            const double fill = c.open * (1 - slippage);
            const double notional = position * fill;
            const auto detail = costs.fee(c.timestamp, notional, true);
            const double fee = detail.total;
            require(cash + notional >= fee, "Sale proceeds and cash cannot cover exit charges; bankruptcy is unsupported");
            record_costs(detail);
            cash += notional - fee;
            const double pnl = position * (fill - entry_price) - entry_fee - fee + lot_dividends;
            realised_pnl += pnl;
            gross_profit += std::max(pnl, 0.0);
            gross_loss += std::max(-pnl, 0.0);
            ++closed_trades;
            if (pnl > 0) ++wins;
            fees_paid += fee;
            trades.push_back({{"timestamp", c.timestamp}, {"side", "SELL"}, {"quantity", position}, {"price", fill}, {"fee", fee}, {"net_pnl", pnl}});
            if (costs.dated()) trades.back()["fee_components"] = detail.parts;
            traded_notional += notional;
            position = 0;
        } else if (i > 0 && pending == 1 && position == 0) {
            const double fill = c.open * (1 + slippage);
            const double budget = std::min(cash, (cash + position * c.open) * max_exposure);
            const double maximum = std::floor(budget / fill);
            require(maximum <= 9007199254740991.0, "Share quantity exceeds exact integer range");
            std::int64_t lo = 0, hi = static_cast<std::int64_t>(maximum);
            while (lo < hi) {
                const auto mid = lo + (hi - lo + 1) / 2;
                if (mid * fill + costs.fee(c.timestamp, mid * fill, false).total <= budget) lo = mid;
                else hi = mid - 1;
            }
            const double quantity = static_cast<double>(lo);
            if (quantity > 0) {
                const double notional = quantity * fill;
                const auto detail = costs.fee(c.timestamp, notional, false);
                const double fee = detail.total;
                record_costs(detail);
                cash -= notional + fee;
                if (cash < 0 && cash > -1e-7) cash = 0;
                require(cash >= 0, "Internal accounting error: negative cash");
                position = quantity;
                entry_price = fill;
                stop_reference = fill;
                lot_dividends = 0;
                entry_fee = fee;
                fees_paid += fee;
                traded_notional += notional;
                trades.push_back({{"timestamp", c.timestamp}, {"side", "BUY"}, {"quantity", position}, {"price", fill}, {"fee", fee}});
                if (costs.dated()) trades.back()["fee_components"] = detail.parts;
            }
        }

        const double equity = cash + position * c.close + receivable;
        require(std::isfinite(equity) && equity > 0, "Portfolio value exceeds supported numerical range");
        peak = std::max(peak, equity);
        const double drawdown = 1 - equity / peak;
        max_drawdown = std::max(max_drawdown, drawdown);
        if (i > static_cast<std::size_t>(evaluation_start)) {
            returns.push_back(equity / previous_equity - 1);
            sum_exposure += position > 0 ? 1.0 : 0.0;
        }
        previous_equity = equity;
        equity_curve.push_back({{"timestamp", c.timestamp}, {"equity", equity}, {"drawdown", drawdown},
                                {"cash", cash}, {"position", position}, {"close", c.close}, {"dividend_receivable", receivable}});
        pending = 0;
        if (strategy == "buy_hold") {
            if (position == 0) pending = 1;
            continue;
        }
        if (position > 0) {
            const bool stopped = stop_loss > 0 && stop_reference > 0 && c.close <= stop_reference * (1 - stop_loss);
            const bool strategy_exit = strategy == "indicator" ?
                (std::isfinite(features.sma[i]) && c.close < features.sma[i]) :
                strategy == "range_reversion" ?
                (c.close >= (features.prior_high[i] + features.prior_low[i]) / 2 || c.close < features.prior_low[i]) :
                c.close < features.prior_low[i];
            if (stopped || strategy_exit) pending = -1;
        } else if (strategy == "price_volume") {
            if (i >= static_cast<std::size_t>(lookback) && c.close > features.prior_high[i] &&
                std::isfinite(features.relative_volume[i]) && features.relative_volume[i] >= volume_threshold) pending = 1;
        } else if (strategy == "trend_pullback") {
            if (i >= 20 && features.structure[i] > 0 && features.return20[i] > 0 &&
                adjusted[i].close > adjusted[i - 1].close && c.close <= features.prior_high[i] &&
                c.close >= features.prior_high[i] - 1.5 * features.atr[i] &&
                std::isfinite(features.relative_volume[i]) && features.relative_volume[i] >= 0.8) pending = 1;
        } else if (strategy == "range_reversion") {
            const double width = features.prior_high[i] - features.prior_low[i];
            if (i >= 20 && features.structure[i] == 0 && width > 0 &&
                std::abs(features.return20[i]) <= 2 * features.atr[i] / c.close &&
                c.close >= features.prior_low[i] && c.close <= features.prior_low[i] + 0.2 * width &&
                adjusted[i].close > adjusted[i - 1].close) pending = 1;
        } else if (strategy == "indicator" && std::isfinite(features.sma[i]) && c.close > features.sma[i]) {
            pending = 1;
        }
    }
    const double mean = std::accumulate(returns.begin(), returns.end(), 0.0) / static_cast<double>(returns.size());
    double squared = 0;
    for (double value : returns) squared += (value - mean) * (value - mean);
    const double volatility = returns.size() > 1 ? std::sqrt(squared / (returns.size() - 1)) : 0;
    const json sharpe = volatility > 1e-15 ? json(mean / volatility * std::sqrt(trading_days)) : json(nullptr);
    const double periods = static_cast<double>(candles.size() - evaluation_start - 1);
    return {{"strategy", strategy}, {"metrics", {{"total_return", previous_equity / initial - 1},
            {"max_drawdown", max_drawdown}, {"annualized_volatility", volatility * std::sqrt(trading_days)},
            {"sharpe", sharpe}, {"trade_count", trades.size()}, {"turnover", traded_notional / initial},
            {"exposure", sum_exposure / periods}, {"closed_trades", closed_trades},
            {"win_rate", closed_trades ? json(static_cast<double>(wins) / closed_trades) : json(nullptr)},
            {"profit_factor", gross_loss > 0 ? json(gross_profit / gross_loss) : json(nullptr)},
            {"realised_pnl", realised_pnl}, {"fees_paid", fees_paid},
            {"dividend_income", dividend_income}, {"dividend_paid", dividend_paid}, {"dividend_receivable", receivable},
            {"cagr", nullable(std::pow(previous_equity / initial, trading_days / periods) - 1)}}},
            {"evaluation", {{"start_index", evaluation_start}, {"start", candles[evaluation_start].timestamp},
                            {"end", candles.back().timestamp}, {"bars", candles.size() - evaluation_start}}},
            {"equity", equity_curve}, {"trades", trades}, {"action_ledger", action_ledger}, {"fee_breakdown", fee_totals}, {"assumptions", {
            "Long-only cash account; whole shares; no leverage. Signals at close execute at next observed open.",
            "max_exposure caps allocation including entry costs when buying; later price movements may change portfolio exposure.",
            "Dated cost schedules itemise charges when supplied; otherwise hypothetical commission bps apply. Rounding, tax residency and broker invoice differences remain unmodelled.",
            "Stops are close-based signals executed next open; gaps can exceed the configured stop loss.",
            "Final holdings are marked to final close, with no artificial liquidation; trade_count counts fills.",
            "Closed-trade win rate and profit factor deduct entry and exit commissions; profit factor is null when there are no losing trades.",
            "evaluation_start begins in cash; prior bars warm up causal features only. It does not tune or optimise strategy parameters.",
            "Sharpe uses zero risk-free rate; annualized volatility and Sharpe assume DAILY bars and 252 sessions/year.",
            "Declared raw-price splits/bonuses adjust shares and basis on ex-date; credit latency is not modelled. Fractional entitlements, rights and mergers are rejected.",
            "Gross dividends accrue to prior holders at ex-date; receivables count in equity but only become spending cash on/after supplied pay_date. Withholding/income tax is excluded.",
            "Signals use causal forward-normalised price/share units; current-date outputs use current raw units. Unknown actions remain a source-quality risk; adjusted input must not also receive events.",
            "Single-stock strategy test: no claims of portfolio diversification or survivorship-bias control."}}};
}

double quantile(std::vector<double> values, double probability) {
    std::sort(values.begin(), values.end());
    const double at = probability * static_cast<double>(values.size() - 1);
    const auto lo = static_cast<std::size_t>(std::floor(at)), hi = static_cast<std::size_t>(std::ceil(at));
    return values[lo] + (values[hi] - values[lo]) * (at - lo);
}

json simulate(const std::vector<Candle>& candles, const json& options) {
    const auto action_plan = accounting::prepare_actions(candles, options);
    const auto adjusted = signal_candles(candles, action_plan);
    const std::string method = options.value("method", std::string("bootstrap"));
    require(method == "bootstrap" || method == "gbm", "Simulation method must be bootstrap or gbm");
    const int paths = integer_option(options, "paths", 1000, 10, 20000);
    const int horizon = integer_option(options, "horizon", 60, 1, 2520);
    require(static_cast<std::int64_t>(paths) * (horizon + 1) <= 5000000, "Simulation exceeds five million path steps");
    const int seed = integer_option(options, "seed", 42, 0, 2147483647);
    const int block_size = integer_option(options, "block_size", 5, 1, 2520);
    const double capital = option(options, "capital", 100000, 1, 1e12);
    const double volatility_multiplier = option(options, "volatility_multiplier", 1, 0, 5);
    const double annual_drift_shift = option(options, "annual_drift_shift", 0, -2, 2);
    const double initial_shock = option(options, "initial_shock_pct", 0, -.95, 1);
    const double execution_spread_bps = option(options, "execution_spread_bps", 0, 0, 1000);
    std::vector<double> log_returns;
    for (std::size_t i = 1; i < candles.size(); ++i) log_returns.push_back(std::log(adjusted[i].close / adjusted[i - 1].close));
    const double mean = std::accumulate(log_returns.begin(), log_returns.end(), 0.0) / log_returns.size();
    double squared = 0;
    for (double r : log_returns) squared += (r - mean) * (r - mean);
    const double sigma = log_returns.size() > 1 ? std::sqrt(squared / (log_returns.size() - 1)) : 0;
    std::mt19937 generator(static_cast<unsigned>(seed));
    std::normal_distribution<double> normal(0, 1);
    std::uniform_int_distribution<std::size_t> start(0, log_returns.size() - 1);
    std::vector<std::vector<double>> step_values(horizon + 1);
    for (auto& step : step_values) step.reserve(paths);
    std::vector<double> terminal, drawdowns;
    json samples = json::array();
    int loss_count = 0;
    for (int path = 0; path < paths; ++path) {
        // A one-off entry spread and shock affect step 1, preserving step 0 = capital.
        double log_wealth = std::log(capital), peak = capital, path_drawdown = 0;
        std::size_t block_start = 0;
        std::vector<double> sample{capital};
        step_values[0].push_back(capital);
        for (int step = 1; step <= horizon; ++step) {
            double increment;
            if (method == "bootstrap") {
                if ((step - 1) % block_size == 0) block_start = start(generator);
                const auto index = (block_start + static_cast<std::size_t>((step - 1) % block_size)) % log_returns.size();
                increment = mean + volatility_multiplier * (log_returns[index] - mean);
            } else {
                // Estimate GBM arithmetic drift as mean(log returns) + sigma^2/2.
                // Volatility stress changes sigma but preserves the original fitted arithmetic drift.
                const double stressed_sigma = sigma * volatility_multiplier;
                const double arithmetic_drift = mean + .5 * sigma * sigma;
                increment = arithmetic_drift - .5 * stressed_sigma * stressed_sigma + stressed_sigma * normal(generator);
            }
            increment += annual_drift_shift / trading_days;
            if (step == 1) increment += std::log1p(initial_shock) + std::log1p(-execution_spread_bps / 10000);
            log_wealth += increment;
            require(log_wealth > -700 && log_wealth < 700, "Simulation wealth exceeds supported numerical range");
            const double wealth = std::exp(log_wealth);
            peak = std::max(peak, wealth);
            path_drawdown = std::max(path_drawdown, 1 - wealth / peak);
            step_values[step].push_back(wealth);
            if (path < 30) sample.push_back(wealth);
        }
        const double last = step_values[horizon].back();
        terminal.push_back(last);
        drawdowns.push_back(path_drawdown);
        if (last < capital - 1e-8) ++loss_count;
        if (path < 30) samples.push_back(sample);
    }
    const double p05 = quantile(terminal, .05), p50 = quantile(terminal, .5), p95 = quantile(terminal, .95);
    std::sort(terminal.begin(), terminal.end());
    // Fractional weighting makes the expected shortfall exactly the worst 5% mass.
    const double tail_mass = paths * .05;
    const auto full_count = static_cast<std::size_t>(std::floor(tail_mass));
    double tail_sum = std::accumulate(terminal.begin(), terminal.begin() + full_count, 0.0);
    if (full_count < terminal.size()) tail_sum += (tail_mass - full_count) * terminal[full_count];
    const double tail_mean = tail_sum / tail_mass;
    json percentiles = json::array();
    for (int step = 0; step <= horizon; ++step) {
        percentiles.push_back({{"step", step}, {"p05", quantile(step_values[step], .05)},
                               {"p50", quantile(step_values[step], .5)}, {"p95", quantile(step_values[step], .95)}});
    }
    json histogram = json::array();
    const double minimum = terminal.front(), maximum = terminal.back();
    if (maximum == minimum) {
        histogram.push_back({{"low", minimum}, {"high", maximum}, {"count", paths}});
    } else {
        const double width = (maximum - minimum) / 20;
        std::vector<int> bins(20, 0);
        for (double value : terminal) {
            const int bin = std::min(19, static_cast<int>((value - minimum) / width));
            ++bins[bin];
        }
        for (int i = 0; i < 20; ++i) histogram.push_back({{"low", minimum + i * width},
            {"high", minimum + (i + 1) * width}, {"count", bins[i]}});
    }
    return {{"method", method}, {"seed", seed}, {"summary", {{"p05", p05}, {"p50", p50}, {"p95", p95},
            {"probability_loss", static_cast<double>(loss_count) / paths}, {"var95", std::max(0.0, capital - p05)},
            {"expected_shortfall95", std::max(0.0, capital - tail_mean)},
            {"max_drawdown_p50", quantile(drawdowns, .5)}, {"max_drawdown_p95", quantile(drawdowns, .95)}}},
            {"percentiles", percentiles}, {"sample_paths", samples}, {"terminal_histogram", histogram},
            {"calibration", {{"daily_log_mean", mean}, {"daily_log_volatility", sigma}, {"observations", log_returns.size()},
            {"volatility_multiplier", volatility_multiplier}, {"annual_drift_shift", annual_drift_shift},
            {"initial_shock_pct", initial_shock}, {"execution_spread_bps", execution_spread_bps}}},
            {"assumptions", {"Conditional scenarios, not price predictions or confidence intervals for true future prices.",
            "Daily closes and 252 sessions/year are assumed. Input history must be adjusted consistently for corporate actions.",
            "Bootstrap samples circular contiguous blocks of log returns; blocks may wrap across history ends.",
            "GBM fits daily log mean and sample log volatility; arithmetic drift = log mean + 0.5 * variance.",
            "Historical drift is noisy. Declared dividends normalise historical returns; future dividends, payment timing, structural breaks, liquidity crises and trading taxes are not simulated.",
            "VaR/expected shortfall are nonnegative currency losses relative to starting capital. ES averages worst 5% probability mass.",
            "Stress adds an annual log-drift shift, scales volatility, and applies one initial shock and entry spread charge.",
            "A fixed seed reproduces paths for this engine build; standard-library normal generators can differ across compilers."}}};
}

json depth(const json& request) {
    require(request.contains("bids") && request.contains("asks"), "Depth requires bids and asks");
    auto parse_side = [](const json& levels, bool is_bid) {
        require(levels.is_array() && !levels.empty() && levels.size() <= 1000, "Depth sides require 1 to 1000 levels");
        std::vector<std::pair<double, double>> result;
        for (const auto& level : levels) {
            require(level.is_object() && level.contains("price") && level.contains("quantity"), "Depth level requires price and quantity");
            const double price = number(level.at("price"), "depth price"), quantity = number(level.at("quantity"), "depth quantity");
            require(price > 0 && price <= 1e12 && quantity >= 0 && quantity <= 1e15, "Invalid depth price or quantity");
            result.emplace_back(price, quantity);
        }
        std::sort(result.begin(), result.end(), [is_bid](const auto& a, const auto& b) { return is_bid ? a.first > b.first : a.first < b.first; });
        for (std::size_t i = 1; i < result.size(); ++i) require(result[i].first != result[i - 1].first, "Duplicate depth price level");
        return result;
    };
    const auto bids = parse_side(request.at("bids"), true), asks = parse_side(request.at("asks"), false);
    require(bids.front().first < asks.front().first, "Crossed or locked order book is not supported");
    const double midpoint = (bids.front().first + asks.front().first) / 2;
    const double spread = asks.front().first - bids.front().first;
    const double bid_total = std::accumulate(bids.begin(), bids.end(), 0.0, [](double v, const auto& l) { return v + l.second; });
    const double ask_total = std::accumulate(asks.begin(), asks.end(), 0.0, [](double v, const auto& l) { return v + l.second; });
    const auto imbalance = [](double bid, double ask) { return bid + ask > 0 ? json((bid - ask) / (bid + ask)) : json(nullptr); };
    json bid_rows = json::array(), ask_rows = json::array();
    for (const auto& [price, quantity] : bids) bid_rows.push_back({{"price", price}, {"quantity", quantity}});
    for (const auto& [price, quantity] : asks) ask_rows.push_back({{"price", price}, {"quantity", quantity}});
    return {{"spread", spread}, {"spread_bps", spread / midpoint * 10000}, {"midpoint", midpoint},
            {"top_imbalance", imbalance(bids.front().second, asks.front().second)}, {"depth_imbalance", imbalance(bid_total, ask_total)},
            {"bid_quantity", bid_total}, {"ask_quantity", ask_total}, {"levels", {{"bids", bid_rows}, {"asks", ask_rows}}},
            {"assumptions", {"Displayed resting liquidity snapshot only; not executed trade flow.",
            "No CVD, aggressor classification or order cancellations are inferred from this snapshot.",
            "Depth imbalance compares the supplied levels; use equal depth and contemporaneous snapshots for comparisons.",
            "Spoofing, hidden liquidity and feed sampling can distort apparent imbalance."}}};
}
} // namespace

json execute(const json& request) {
    require(request.is_object(), "Request must be an object");
    require(request.contains("command") && request.at("command").is_string(), "command is required");
    const std::string command = request.at("command");
    const json options = request.value("options", json::object());
    require(options.is_object(), "options must be an object");
    json result;
    if (command == "depth") {
        result = depth(request);
    } else {
        require(command == "analyze" || command == "backtest" || command == "simulate", "Unknown command");
        const auto candles = candles_from(request);
        if (command == "analyze") result = analyze(candles, options);
        else if (command == "backtest") result = backtest(candles, options);
        else result = simulate(candles, options);
    }
    result["supported_features"] = {"OHLCV context", "cash long-only next-open backtests", "conditional Monte Carlo", "displayed depth snapshots"};
    result["accounting"] = {{"price_basis", options.value("price_basis", std::string("unverified"))},
                             {"declared_actions", options.value("corporate_actions", json::array()).size()},
                             {"signal_units", "causal forward-normalised; displayed levels in current raw units"}};
    result["limitations"] = {{"corporate_actions_processed", options.contains("corporate_actions") && !options["corporate_actions"].empty()}, {"executed_order_flow_inferred", false},
                             {"live_execution_supported", false}, {"daily_bar_annualization", true}};
    return result;
}
} // namespace finance
