// Native probability kernel for s02 weather strategy.
//
// Build:
//   clang++ -O3 -march=native -std=c++17 -o native/s02_weather_signal_engine native/s02_weather_signal_engine.cpp
//
// Protocol (line-based over stdin/stdout):
//   TEMP|<threshold_f>|<above:0|1>|<csv temps>
//   PRECIP|<csv precipitation-percent values>
//   QUIT
//
// Response:
//   <probability> <confidence>

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

constexpr double kMinProb = 1e-6;
constexpr double kMaxProb = 1.0 - 1e-6;

static inline double clamp(double x, double lo, double hi) {
  if (x < lo) return lo;
  if (x > hi) return hi;
  return x;
}

std::vector<std::string> split(const std::string& line, char delim) {
  std::vector<std::string> out;
  std::string cur;
  std::istringstream ss(line);
  while (std::getline(ss, cur, delim)) {
    out.push_back(cur);
  }
  return out;
}

std::vector<double> parse_csv_doubles(const std::string& csv) {
  std::vector<double> out;
  std::string token;
  std::istringstream ss(csv);
  while (std::getline(ss, token, ',')) {
    if (token.empty()) {
      continue;
    }
    try {
      out.push_back(std::stod(token));
    } catch (...) {
      // Ignore malformed token.
    }
  }
  return out;
}

std::pair<double, double> temp_probability(const std::vector<double>& temps, double threshold_f, bool above) {
  if (temps.empty()) {
    return {0.5, 0.20};
  }

  size_t hits = 0;
  double signed_margin_sum = 0.0;

  for (double temp : temps) {
    if (above) {
      if (temp > threshold_f) ++hits;
      signed_margin_sum += (temp - threshold_f);
    } else {
      if (temp < threshold_f) ++hits;
      signed_margin_sum += (threshold_f - temp);
    }
  }

  const double n = static_cast<double>(temps.size());
  const double probability = clamp(static_cast<double>(hits) / n, 0.0, 1.0);

  // Confidence grows when the forecast margin is further from the threshold.
  const double avg_margin = signed_margin_sum / n;
  const double margin_score = std::tanh(std::abs(avg_margin) / 6.0);
  const double sample_score = std::min(1.0, std::sqrt(n / 24.0));
  const double confidence = clamp(0.40 + 0.35 * margin_score + 0.20 * sample_score, 0.35, 0.95);

  return {probability, confidence};
}

std::pair<double, double> precip_probability(const std::vector<double>& pops_pct) {
  if (pops_pct.empty()) {
    return {0.0, 0.20};
  }

  double total = 0.0;
  double sq_total = 0.0;
  for (double pop : pops_pct) {
    const double p = clamp(pop / 100.0, 0.0, 1.0);
    total += p;
    sq_total += p * p;
  }

  const double n = static_cast<double>(pops_pct.size());
  const double mean = clamp(total / n, 0.0, 1.0);

  const double variance = std::max(0.0, (sq_total / n) - (mean * mean));
  const double norm_var = clamp(variance / 0.25, 0.0, 1.0);
  const double sample_score = std::min(1.0, std::sqrt(n / 24.0));
  const double confidence = clamp(0.45 + 0.30 * (1.0 - norm_var) + 0.20 * sample_score, 0.35, 0.95);

  return {mean, confidence};
}

void emit(double probability, double confidence) {
  std::cout << std::fixed << std::setprecision(8) << clamp(probability, 0.0, 1.0) << " "
            << clamp(confidence, 0.0, 1.0) << "\n";
  std::cout.flush();
}

}  // namespace

int main() {
  std::ios::sync_with_stdio(false);
  std::cin.tie(nullptr);

  std::string line;
  while (std::getline(std::cin, line)) {
    if (line.empty()) {
      emit(0.5, 0.2);
      continue;
    }
    if (line == "QUIT") {
      break;
    }

    const auto parts = split(line, '|');
    if (parts.empty()) {
      emit(0.5, 0.2);
      continue;
    }

    if (parts[0] == "TEMP" && parts.size() >= 4) {
      try {
        const double threshold_f = std::stod(parts[1]);
        const bool above = (parts[2] == "1");
        const auto temps = parse_csv_doubles(parts[3]);
        const auto res = temp_probability(temps, threshold_f, above);
        emit(res.first, res.second);
      } catch (...) {
        emit(0.5, 0.2);
      }
      continue;
    }

    if (parts[0] == "PRECIP" && parts.size() >= 2) {
      const auto pops = parse_csv_doubles(parts[1]);
      const auto res = precip_probability(pops);
      emit(res.first, res.second);
      continue;
    }

    emit(0.5, 0.2);
  }

  return 0;
}
