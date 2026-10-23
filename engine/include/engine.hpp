#pragma once

#include "json.hpp"

namespace finance {
using json = nlohmann::json;

// Every operation is a pure request -> result calculation. The CLI wraps errors.
json execute(const json& request);
}
