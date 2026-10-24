#pragma once

// Small, testable accounting helpers. No broker/network dependencies.
#include "json.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

namespace finance::accounting {
using json = nlohmann::json;

inline void check(bool ok, const std::string& message) {
    if (!ok) throw std::invalid_argument(message);
}

inline bool valid_date(const std::string& date) {
    if (date.size() != 10 || date[4] != '-' || date[7] != '-') return false;
    for (std::size_t i = 0; i < date.size(); ++i)
        if (i != 4 && i != 7 && (date[i] < '0' || date[i] > '9')) return false;
    const int year = std::stoi(date.substr(0, 4)), month = std::stoi(date.substr(5, 2)), day = std::stoi(date.substr(8, 2));
    if (year < 1900 || month < 1 || month > 12) return false;
    int days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
    if (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)) days[1] = 29;
    return day > 0 && day <= days[month - 1];
}

inline double bounded(const json& values, const std::string& key, double fallback, double maximum) {
    if (!values.contains(key)) return fallback;
    check(values[key].is_number() && !values[key].is_boolean(), key + " must be numeric");
    const double value = values[key].get<double>();
    check(std::isfinite(value) && value >= 0 && value <= maximum, "Invalid " + key);
    return value;
}

struct Action {
    std::string type, ex_date, pay_date, source;
    double multiplier = 1, amount = 0;
};

struct ActionPlan {
    std::vector<double> price_scale, share_scale;
    std::vector<std::vector<Action>> on_bar;
    std::size_t count = 0;
};

template<class Bar>
ActionPlan prepare_actions(const std::vector<Bar>& bars, const json& options) {
    const json actions = options.value("corporate_actions", json::array());
    check(actions.is_array() && actions.size() <= 256, "Provide at most 256 corporate actions");
    const std::string basis = options.value("price_basis", std::string("unverified"));
    check(basis == "raw" || basis == "adjusted" || basis == "unverified", "Invalid price_basis");
    check(actions.empty() || basis == "raw", "Corporate actions require raw prices; do not double-adjust adjusted history");
    ActionPlan plan{std::vector<double>(bars.size(), 1), std::vector<double>(bars.size(), 1),
                    std::vector<std::vector<Action>>(bars.size()), actions.size()};
    for (const auto& item : actions) {
        check(item.is_object(), "Corporate action must be an object");
        Action action;
        action.type = item.value("type", std::string());
        action.ex_date = item.value("ex_date", std::string());
        action.source = item.value("source", std::string());
        const std::string announced = item.value("announced_date", std::string());
        check(valid_date(action.ex_date) && valid_date(announced) && announced < action.ex_date,
              "Action needs valid ex_date and an earlier announced_date");
        check(!action.source.empty(), "Corporate action source is required");
        auto found = std::find_if(bars.begin(), bars.end(), [&](const Bar& bar) {
            return bar.timestamp.substr(0, 10) == action.ex_date;
        });
        check(found != bars.end() && found != bars.begin(), "Action ex-date must match a bar with a preceding observation");
        const auto index = static_cast<std::size_t>(found - bars.begin());
        check(std::count_if(bars.begin(), bars.end(), [&](const Bar& bar) {
            return bar.timestamp.substr(0, 10) == action.ex_date;
        }) == 1, "Corporate action accounting requires one bar per ex-date");
        if (action.type == "split" || action.type == "bonus") {
            action.multiplier = bounded(item, "share_multiplier", 0, 1000);
            check(action.multiplier > 0 && action.multiplier != 1, "Supply new shares per old share, e.g. 2 for a 2-for-1 split/1:1 bonus");
        } else if (action.type == "cash_dividend") {
            action.amount = bounded(item, "cash_per_share", 0, 1e12);
            action.pay_date = item.value("pay_date", std::string());
            check(action.amount > 0 && valid_date(action.pay_date) && action.pay_date >= action.ex_date,
                  "Cash dividend needs positive cash_per_share and pay_date on/after ex_date");
        } else {
            throw std::invalid_argument("Only split, bonus and cash_dividend are supported; rights/mergers need separate accounting");
        }
        auto& bucket = plan.on_bar[index];
        for (const auto& other : bucket)
            check((other.type == "cash_dividend") != (action.type == "cash_dividend"),
                  "At most one share action and one cash dividend are supported per ex-date");
        bucket.push_back(action);
    }
    double price_scale = 1, share_scale = 1;
    for (std::size_t i = 0; i < bars.size(); ++i) {
        auto& actions_today = plan.on_bar[i];
        std::sort(actions_today.begin(), actions_today.end(), [](const Action& a, const Action& b) {
            return a.type != "cash_dividend" && b.type == "cash_dividend";
        });
        double split = 1;
        for (const auto& action : actions_today) {
            if (action.type != "cash_dividend") {
                split = action.multiplier;
                price_scale *= split;
                share_scale *= split;
            } else {
                const double previous = bars[i - 1].close / split;
                check(action.amount < previous, "Dividend must be below the prior split-adjusted close; liquidation is unsupported");
                price_scale *= previous / (previous - action.amount);
            }
        }
        check(std::isfinite(price_scale) && std::isfinite(share_scale) && price_scale > 0 && share_scale > 0,
              "Corporate action factors exceed numerical limits");
        plan.price_scale[i] = price_scale;
        plan.share_scale[i] = share_scale;
    }
    return plan;
}

struct Costs {
    double total = 0;
    json parts;
};

class CostModel {
    json schedule_;
    double commission_, multiplier_;
public:
    explicit CostModel(const json& options) : schedule_(options.value("cost_schedule", json::array())),
        commission_(bounded(options, "commission_bps", 10, 1000) / 10000),
        multiplier_(bounded(options, "cost_multiplier", 1, 5)) {
        check(schedule_.is_array() && schedule_.size() <= 50, "Invalid cost schedule");
        std::string previous_end;
        for (const auto& rate : schedule_) {
            check(rate.is_object(), "Cost schedule rows must be objects");
            const auto from = rate.value("from", std::string()), through = rate.value("through", std::string());
            check(valid_date(from) && valid_date(through) && from <= through && from > previous_end,
                  "Cost schedule dates must be valid, sorted and non-overlapping");
            check(!rate.value("id", std::string()).empty() && !rate.value("source", std::string()).empty(), "Cost rate ID/source required");
            for (const std::string key : {"brokerage_bps", "stt_buy_bps", "stt_sell_bps", "exchange_bps", "ipft_bps", "sebi_bps", "stamp_buy_bps"})
                bounded(rate, key, 0, 1000);
            bounded(rate, "brokerage_cap", 0, 1e6);
            bounded(rate, "dp_sell", 0, 1e6);
            bounded(rate, "gst_pct", 0, 100);
            previous_end = through;
        }
    }
    bool dated() const { return !schedule_.empty(); }
    Costs fee(const std::string& timestamp, double turnover, bool sell) const {
        if (!dated()) return {turnover * commission_ * multiplier_, {{"commission", turnover * commission_ * multiplier_}}};
        const std::string date = timestamp.substr(0, 10);
        for (const auto& row : schedule_) {
            if (date < row.at("from").get<std::string>() || date > row.at("through").get<std::string>()) continue;
            const auto amount = [&](const std::string& key) { return turnover * bounded(row, key, 0, 1000) / 10000; };
            double brokerage = amount("brokerage_bps");
            const double cap = bounded(row, "brokerage_cap", 0, 1e6);
            if (cap > 0) brokerage = std::min(brokerage, cap);
            const double exchange = amount("exchange_bps"), ipft = amount("ipft_bps"), sebi = amount("sebi_bps");
            const double dp = sell ? bounded(row, "dp_sell", 0, 1e6) : 0;
            json parts = {{"brokerage", brokerage}, {"stt", amount(sell ? "stt_sell_bps" : "stt_buy_bps")},
                          {"exchange", exchange}, {"ipft", ipft}, {"sebi", sebi},
                          {"stamp", sell ? 0 : amount("stamp_buy_bps")}, {"dp", dp},
                          {"gst", (brokerage + exchange + ipft + sebi + dp) * bounded(row, "gst_pct", 0, 100) / 100}};
            double total = 0;
            for (auto& value : parts.items()) { value.value() = value.value().get<double>() * multiplier_; total += value.value().get<double>(); }
            parts["rate_id"] = row.at("id");
            return {total, parts};
        }
        throw std::invalid_argument("No verified cost rate covers trade date " + date + "; supply a dated schedule or use hypothetical bps");
    }
};
} // namespace finance::accounting
