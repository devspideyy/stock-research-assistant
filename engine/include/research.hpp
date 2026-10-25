#pragma once

#include "engine.hpp"
#include <algorithm>
#include <cmath>
#include <numeric>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace finance::research {
inline void check(bool condition, const std::string& message) {
    if (!condition) throw std::invalid_argument(message);
}
inline double numeric(const json& value) {
    check(value.is_number() && !value.is_boolean(), "Curve values and weights must be numeric");
    const double number = value.get<double>();
    check(std::isfinite(number), "Curve values and weights must be finite");
    return number;
}
struct Curve {
    std::string symbol;
    std::vector<std::string> dates;
    std::vector<double> values;
    double weight;
};
inline std::vector<Curve> curves(const json& request) {
    const auto& input = request.at("curves");
    check(input.is_array() && !input.empty() && input.size() <= 20, "Supply 1 to 20 aligned curves");
    std::vector<Curve> result;
    std::set<std::string> symbols;
    for (const auto& item : input) {
        Curve curve{item.at("symbol").get<std::string>(), {}, {}, numeric(item.value("weight", json(0.0)))};
        check(symbols.insert(curve.symbol).second, "Duplicate curve symbol");
        const auto& rows = item.at("equity");
        check(rows.is_array() && rows.size() >= 3 && rows.size() <= 100000, "Each curve needs 3 to 100000 daily observations");
        for (const auto& row : rows) {
            const auto date = row.at("timestamp").get<std::string>();
            check(date.size() >= 10 && (curve.dates.empty() || date > curve.dates.back()), "Curve dates must increase without duplicates");
            const double value = numeric(row.at("equity"));
            check(value > 0, "Curve equity must be positive");
            curve.dates.push_back(date);
            curve.values.push_back(value);
        }
        check(result.empty() || curve.dates == result.front().dates, "Curves require exactly matching daily dates; no gap filling");
        result.push_back(std::move(curve));
    }
    return result;
}
inline std::vector<double> returns(const std::vector<double>& values) {
    std::vector<double> result;
    for (std::size_t i = 1; i < values.size(); ++i) result.push_back(values[i] / values[i-1] - 1);
    return result;
}
inline double mean(const std::vector<double>& values) {
    return std::accumulate(values.begin(), values.end(), 0.0) / values.size();
}
inline double covariance(const std::vector<double>& a, const std::vector<double>& b) {
    const double x = mean(a), y = mean(b);
    double result = 0;
    for (std::size_t i = 0; i < a.size(); ++i) result += (a[i] - x) * (b[i] - y);
    return result / (a.size() - 1);
}
inline json correlation(const std::vector<double>& a, const std::vector<double>& b) {
    const double va = covariance(a,a), vb = covariance(b,b);
    return va > 1e-18 && vb > 1e-18 ? json(std::clamp(covariance(a,b) / std::sqrt(va*vb), -1.0, 1.0)) : json(nullptr);
}
inline json metrics(const std::vector<double>& values) {
    const auto r = returns(values);
    const double vol = std::sqrt(std::max(0.0, covariance(r,r)));
    double peak = values.front(), drawdown = 0;
    for (double value : values) { peak = std::max(peak,value); drawdown = std::max(drawdown,1-value/peak); }
    const double cagr = std::pow(values.back()/values.front(),252.0/(values.size()-1))-1;
    return {{"total_return", values.back()/values.front()-1}, {"annualized_volatility",vol*std::sqrt(252.0)},
            {"max_drawdown",drawdown},{"cagr",cagr},{"sharpe",vol > 1e-12 ? json(mean(r)/vol*std::sqrt(252.0)) : json(nullptr)}};
}
inline json diagnostics(const json& request) {
    const auto input = curves(request);
    check(input.size() == 2, "Benchmark diagnostics require strategy and benchmark curves");
    const auto strategy = returns(input[0].values), benchmark = returns(input[1].values);
    std::vector<double> active;
    for (std::size_t i = 0; i < strategy.size(); ++i) active.push_back(strategy[i] - benchmark[i]);
    const double variance = covariance(benchmark,benchmark), tracking = std::sqrt(std::max(0.0,covariance(active,active)));
    return {{"observations",strategy.size()}, {"beta", variance > 1e-18 ? json(covariance(strategy,benchmark)/variance) : json(nullptr)},
        {"correlation",correlation(strategy,benchmark)}, {"tracking_error",tracking*std::sqrt(252.0)},
        {"information_ratio",tracking > 1e-12 ? json(mean(active)/tracking*std::sqrt(252.0)) : json(nullptr)},
        {"excess_return",input[0].values.back()/input[0].values.front()-input[1].values.back()/input[1].values.front()},
        {"assumptions", "Aligned net daily equity returns; 252 observations/year; beta and correlation use the supplied benchmark, not a market index unless one was supplied."}};
}
inline json portfolio(const json& request) {
    const auto input = curves(request);
    const auto options = request.value("options",json::object());
    const double capital = numeric(options.value("initial_capital",json(100000.0)));
    const double cap = numeric(options.value("weight_cap",json(0.6)));
    check(capital > 0 && capital <= 1e12 && cap > 0 && cap <= 1, "Invalid capital or initial weight cap");
    double invested = 0;
    for (const auto& curve : input) {
        check(curve.weight >= 0 && curve.weight <= cap + 1e-12, "An initial position weight exceeds the cap");
        invested += curve.weight;
    }
    check(invested <= 1 + 1e-12, "Initial weights exceed 100%; leverage is not supported");
    const double cash = std::max(0.0,1-invested);
    std::vector<double> values;
    json equity = json::array(), correlations = json::array(), weights = json::array();
    double peak = capital;
    for (std::size_t i = 0; i < input.front().dates.size(); ++i) {
        double value = cash;
        for (const auto& curve : input) value += curve.weight * curve.values[i]/curve.values.front();
        value *= capital; peak = std::max(peak,value); values.push_back(value);
        equity.push_back({{"timestamp",input.front().dates[i]},{"equity",value},{"drawdown",1-value/peak}});
    }
    for (const auto& a : input) {
        json row = json::array();
        for (const auto& b : input) row.push_back(correlation(returns(a.values),returns(b.values)));
        correlations.push_back(row);
        weights.push_back({{"symbol",a.symbol},{"initial_weight",a.weight},{"ending_weight",capital*a.weight*a.values.back()/a.values.front()/values.back()}});
    }
    return {{"metrics",metrics(values)}, {"equity",equity}, {"weights",weights},{"cash_weight",cash},{"correlations",correlations},
        {"assumptions", "Fixed initial long-only allocations to supplied net strategy curves, with uninvested cash earning zero. No rebalancing. The cap applies at entry; weights drift. Existing sleeve costs are retained proportionally, not repriced as new broker fills. Daily observations and 252/year; no leverage or optimiser."}};
}
inline json paper_fill(const json& request) {
    const auto& state = request.at("state");
    const double cash = numeric(state.at("cash")), held = numeric(state.at("held"));
    const double quantity = numeric(state.at("quantity")), price = numeric(state.at("last_price"));
    const double commission = numeric(state.value("commission_bps",json(10.0)));
    const double slippage = numeric(state.value("slippage_bps",json(5.0)));
    const std::string side = state.at("side");
    check(cash >= 0 && held >= 0 && quantity > 0 && quantity <= 1e9 && std::floor(quantity) == quantity,
          "Paper fills require nonnegative cash and whole positive share quantities");
    check(price > 0 && price <= 1e12 && commission >= 0 && commission <= 500 && slippage >= 0 && slippage <= 500,
          "Invalid paper price or cost assumptions");
    check(side == "BUY" || side == "SELL", "Paper side must be BUY or SELL");
    const double fill = price * (1 + (side == "BUY" ? 1 : -1) * slippage / 10000);
    const double notional = fill * quantity, fee = notional * commission / 10000;
    check(side != "BUY" || notional + fee <= cash + 1e-8, "Insufficient simulated cash");
    check(side != "SELL" || quantity <= held, "Cannot sell more simulated shares than held");
    return {{"cash",side == "BUY" ? std::max(0.0,cash-notional-fee) : cash+notional-fee},
            {"held",side == "BUY" ? held+quantity : held-quantity}, {"fill_price",fill},{"fee",fee},
            {"notional",notional},{"side",side},{"quantity",quantity}};
}
} // namespace finance::research
