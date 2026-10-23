#include "engine.hpp"

#include <cmath>
#include <functional>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

using finance::json;

namespace {
void check(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

void near(double actual, double expected, double tolerance = 1e-8) {
    check(std::abs(actual - expected) < tolerance, "Expected " + std::to_string(expected) + ", got " + std::to_string(actual));
}

std::string date(int index) {
    std::ostringstream text;
    text << "2025-" << std::setfill('0') << std::setw(2) << 1 + index / 28 << '-'
         << std::setw(2) << 1 + index % 28;
    return text.str();
}

json candle(int index, double close, double volume = 100) {
    return {{"timestamp", date(index)}, {"open", close}, {"high", close + 1},
            {"low", close - 1}, {"close", close}, {"volume", volume}};
}

json history(int count, double close = 100) {
    json rows = json::array();
    for (int i = 0; i < count; ++i) rows.push_back(candle(i, close));
    return rows;
}

void rejects(const std::function<void()>& action) {
    bool rejected = false;
    try { action(); } catch (const std::exception&) { rejected = true; }
    check(rejected, "Invalid input was accepted");
}

void indicators_exclude_current_bar() {
    auto rows = history(22);
    rows.back() = {{"timestamp", date(21)}, {"open", 100}, {"high", 120}, {"low", 99}, {"close", 119}, {"volume", 300}};
    const auto result = finance::execute({{"command", "analyze"}, {"candles", rows}});
    const auto& summary = result.at("summary");
    near(summary.at("prior_high"), 101);
    near(summary.at("prior_low"), 99);
    near(summary.at("relative_volume"), 3);
    check(summary.at("breakout") == "up", "Breakout should compare prior bars only");
    near(summary.at("rsi14"), 100);
    check(result.at("series").at(0).at("sma20").is_null(), "SMA should have warmup");
    near(result.at("series").at(19).at("sma20"), 100);
    near(result.at("series").at(19).at("rsi14"), 50);
    near(result.at("series").at(19).at("atr14"), 2);
}

void insufficient_indicator_history_is_nullable() {
    const auto result = finance::execute({{"command", "analyze"}, {"candles", history(2)}});
    check(result.at("summary").at("rsi14").is_null(), "Unwarmed RSI should be null");
    check(result.at("summary").at("ema20").is_null(), "Unwarmed EMA should be null");
    auto rows = history(2);
    rows[0]["volume"] = 0;
    const auto no_volume = finance::execute({{"command", "analyze"}, {"candles", rows}});
    check(no_volume.at("summary").at("relative_volume").is_null(), "Zero prior volume should be unavailable");
}

void invalid_data_is_rejected() {
    auto rows = history(2);
    rows[1]["timestamp"] = rows[0]["timestamp"];
    rejects([&] { finance::execute({{"command", "analyze"}, {"candles", rows}}); });
    rows = history(2);
    rows[0]["low"] = 120;
    rejects([&] { finance::execute({{"command", "analyze"}, {"candles", rows}}); });
    rows = history(2);
    rows[0]["timestamp"] = "2025-02-30";
    rejects([&] { finance::execute({{"command", "analyze"}, {"candles", rows}}); });
    rows = history(2);
    rows[0]["close"] = -1;
    rejects([&] { finance::execute({{"command", "simulate"}, {"candles", rows}}); });
}

void next_open_execution_and_gap_stop() {
    auto rows = history(6);
    rows[2] = {{"timestamp", date(2)}, {"open", 100}, {"high", 111}, {"low", 99}, {"close", 110}, {"volume", 200}};
    rows[3] = {{"timestamp", date(3)}, {"open", 120}, {"high", 125}, {"low", 119}, {"close", 124}, {"volume", 100}};
    rows[4] = {{"timestamp", date(4)}, {"open", 124}, {"high", 125}, {"low", 99}, {"close", 100}, {"volume", 100}};
    rows[5] = {{"timestamp", date(5)}, {"open", 90}, {"high", 95}, {"low", 89}, {"close", 92}, {"volume", 100}};
    const auto result = finance::execute({{"command", "backtest"}, {"candles", rows}, {"options", {
        {"lookback", 2}, {"initial_capital", 1000}, {"commission_bps", 0}, {"slippage_bps", 0}}}});
    check(result.at("trades").size() == 2, "Expected entry and stop exit");
    check(result.at("trades").at(0).at("timestamp") == date(3), "Entry must execute next open");
    near(result.at("trades").at(0).at("price"), 120);
    near(result.at("trades").at(0).at("quantity"), 8);
    near(result.at("trades").at(1).at("price"), 90);
    near(result.at("equity").back().at("cash"), 760);
    near(result.at("metrics").at("total_return"), -.24);
    // Changing future prices cannot change an earlier signal or fill.
    rows[5]["high"] = 1000;
    rows[5]["close"] = 999;
    const auto changed = finance::execute({{"command", "backtest"}, {"candles", rows}, {"options", {
        {"lookback", 2}, {"initial_capital", 1000}, {"commission_bps", 0}, {"slippage_bps", 0}}}});
    check(changed.at("trades").at(0) == result.at("trades").at(0), "Future prices altered previous fill");
}

void whole_shares_costs_and_cash_constraints() {
    const auto result = finance::execute({{"command", "backtest"}, {"candles", history(3)}, {"options", {
        {"strategy", "buy_hold"}, {"initial_capital", 1000}, {"commission_bps", 100}, {"slippage_bps", 100}}}});
    const auto& trade = result.at("trades").at(0);
    near(trade.at("price"), 101);
    near(trade.at("quantity"), 9);
    near(trade.at("fee"), 9.09);
    near(result.at("equity").back().at("cash"), 81.91);
    near(result.at("equity").back().at("equity"), 981.91);
    check(result.at("trades").size() == 1, "Final position must not be forcibly liquidated");
    const auto capped = finance::execute({{"command", "backtest"}, {"candles", history(3)}, {"options", {
        {"strategy", "buy_hold"}, {"initial_capital", 1000}, {"max_exposure", .5}, {"commission_bps", 0}, {"slippage_bps", 0}}}});
    near(capped.at("trades").at(0).at("quantity"), 5);
    const auto cost_capped = finance::execute({{"command", "backtest"}, {"candles", history(3)}, {"options", {
        {"strategy", "buy_hold"}, {"initial_capital", 1000}, {"max_exposure", .5}, {"commission_bps", 100}, {"slippage_bps", 100}}}});
    const auto& capped_trade = cost_capped.at("trades").at(0);
    check(capped_trade.at("quantity").get<double>() * capped_trade.at("price").get<double>() + capped_trade.at("fee").get<double>() <= 500,
          "Exposure cap must include entry costs");
    const auto disabled = finance::execute({{"command", "backtest"}, {"candles", history(3)}, {"options", {{"max_exposure", 0}}}});
    check(disabled.at("trades").empty(), "Zero exposure must prevent trading");
    rejects([] { finance::execute({{"command", "backtest"}, {"candles", history(3)}, {"options", {{"max_exposure", 2}}}}); });
}

void final_close_cannot_create_a_fill() {
    auto rows = history(3);
    rows[2] = {{"timestamp", date(2)}, {"open", 100}, {"high", 120}, {"low", 99}, {"close", 119}, {"volume", 500}};
    const auto result = finance::execute({{"command", "backtest"}, {"candles", rows}, {"options", {{"lookback", 2}}}});
    check(result.at("trades").empty(), "Final-close signal must wait for a future open that does not exist");
    near(result.at("equity").back().at("cash"), 100000);
}

void simulation_seed_and_risk_measures() {
    auto rows = history(25);
    for (int i = 0; i < 25; ++i) rows[i] = candle(i, 100 + i + (i % 2 ? 3 : -3));
    json request{{"command", "simulate"}, {"candles", rows}, {"options", {{"paths", 100}, {"horizon", 15}, {"seed", 12}}}};
    const auto first = finance::execute(request), second = finance::execute(request);
    check(first == second, "Fixed seed should reproduce simulation");
    check(first.at("percentiles").size() == 16, "Simulation must include starting value");
    check(first.at("sample_paths").size() == 30, "Sample paths must be capped");
    near(first.at("percentiles").at(0).at("p05"), 100000);
    for (const auto& p : first.at("percentiles")) {
        check(p.at("p05").get<double>() <= p.at("p50").get<double>() &&
              p.at("p50").get<double>() <= p.at("p95").get<double>(), "Percentiles must be ordered");
    }
    check(first.at("summary").at("expected_shortfall95").get<double>() >= first.at("summary").at("var95").get<double>(), "ES should exceed VaR");
    request["options"]["seed"] = 13;
    check(finance::execute(request).at("sample_paths") != first.at("sample_paths"), "Different seed should change paths");
    request["options"]["method"] = "gbm";
    check(finance::execute(request).at("method") == "gbm", "GBM should run");
}

void flat_prices_and_stress_scenarios() {
    json request{{"command", "simulate"}, {"candles", history(20)}, {"options", {
        {"paths", 100}, {"horizon", 10}, {"capital", 1000}}}};
    const auto flat = finance::execute(request);
    near(flat.at("summary").at("p50"), 1000);
    near(flat.at("summary").at("probability_loss"), 0);
    near(flat.at("summary").at("var95"), 0);
    request["options"]["initial_shock_pct"] = -.2;
    request["options"]["execution_spread_bps"] = 100;
    const auto stressed = finance::execute(request);
    near(stressed.at("summary").at("p50"), 792);
    near(stressed.at("summary").at("var95"), 208);
    near(stressed.at("summary").at("probability_loss"), 1);
    request["options"]["paths"] = 20000;
    request["options"]["horizon"] = 2520;
    rejects([&] { finance::execute(request); });
}

void depth_is_sorted_and_not_trade_flow() {
    json request{{"command", "depth"},
        {"bids", {{{"price", 99}, {"quantity", 100}}, {{"price", 100}, {"quantity", 300}}}},
        {"asks", {{{"price", 102}, {"quantity", 100}}, {{"price", 101}, {"quantity", 100}}}}};
    const auto result = finance::execute(request);
    near(result.at("midpoint"), 100.5);
    near(result.at("spread"), 1);
    near(result.at("top_imbalance"), .5);
    near(result.at("depth_imbalance"), 1.0 / 3.0);
    near(result.at("levels").at("bids").at(0).at("price"), 100);
    check(!result.contains("cvd"), "Depth must not invent executed flow");
    request["asks"][0]["price"] = 99;
    rejects([&] { finance::execute(request); });
}
} // namespace

int main() {
    const std::pair<const char*, std::function<void()>> cases[] = {
        {"indicators exclude current bar", indicators_exclude_current_bar},
        {"indicator warmup and zero volume", insufficient_indicator_history_is_nullable},
        {"invalid input rejected", invalid_data_is_rejected},
        {"next-open timing and gap stop", next_open_execution_and_gap_stop},
        {"whole shares, costs and cash", whole_shares_costs_and_cash_constraints},
        {"final signal has no future fill", final_close_cannot_create_a_fill},
        {"simulation reproducibility and risk", simulation_seed_and_risk_measures},
        {"flat-price and stress scenarios", flat_prices_and_stress_scenarios},
        {"depth snapshot calculations", depth_is_sorted_and_not_trade_flow},
    };
    int failures = 0;
    for (const auto& [name, action] : cases) {
        try { action(); std::cout << "PASS: " << name << '\n'; }
        catch (const std::exception& error) { ++failures; std::cerr << "FAIL: " << name << ": " << error.what() << '\n'; }
    }
    return failures == 0 ? 0 : 1;
}
