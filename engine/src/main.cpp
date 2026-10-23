#include "engine.hpp"

#include <exception>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>

int main() {
    using finance::json;
    try {
        const std::string input{std::istreambuf_iterator<char>(std::cin), {}};
        if (input.size() > 32 * 1024 * 1024) {
            throw std::invalid_argument("Request exceeds 32 MiB limit");
        }
        const auto result = finance::execute(json::parse(input));
        std::cout << json{{"ok", true}, {"schema_version", 1}, {"result", result}}.dump() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cout << json{{"ok", false}, {"error", error.what()}}.dump() << '\n';
        return 1;
    }
}
