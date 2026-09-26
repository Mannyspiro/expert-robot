#include "expert_robot/conformal_point.hpp"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

using expert_robot::geometry::ConformalPoint3;
using expert_robot::geometry::IntegerPoint3;
using expert_robot::geometry::embed;
using expert_robot::geometry::inner_product;
using expert_robot::geometry::kCoordinateLimit;

namespace {

void require(bool condition, const char* message) {
  if (!condition) {
    throw std::runtime_error(message);
  }
}

std::int64_t reference_distance(const IntegerPoint3& a,
                                const IntegerPoint3& b) {
  const auto dx = a.x - b.x;
  const auto dy = a.y - b.y;
  const auto dz = a.z - b.z;
  return dx * dx + dy * dy + dz * dz;
}

}  // namespace

int main() {
  try {
    std::vector<IntegerPoint3> points;
    for (std::int64_t x = -2; x <= 2; ++x) {
      for (std::int64_t y = -2; y <= 2; ++y) {
        for (std::int64_t z = -2; z <= 2; ++z) {
          points.push_back({x, y, z});
        }
      }
    }

    for (const auto& a : points) {
      const ConformalPoint3 embedded_a = embed(a);
      require(embedded_a.origin() == 2, "wrong origin normalization");
      require(inner_product(embedded_a, embedded_a) == 0,
              "conformal point must be null");
      for (const auto& b : points) {
        const auto embedded_b = embed(b);
        require(inner_product(embedded_a, embedded_b) ==
                    -2 * reference_distance(a, b),
                "CGA inner product disagrees with Euclidean distance");
      }
    }

    const IntegerPoint3 large{kCoordinateLimit, -kCoordinateLimit,
                              kCoordinateLimit};
    const IntegerPoint3 opposite{-kCoordinateLimit, kCoordinateLimit,
                                 -kCoordinateLimit};
    require(inner_product(embed(large), embed(opposite)) ==
                -2 * reference_distance(large, opposite),
            "the bounded edge case must remain exact");

    bool rejected = false;
    try {
      (void)embed({kCoordinateLimit + 1, 0, 0});
    } catch (const std::out_of_range&) {
      rejected = true;
    }
    require(rejected, "out-of-range coordinates must be rejected");
    std::cout << "conformal integer identity: PASS (15625 point pairs)\n";
  } catch (const std::exception& error) {
    std::cerr << "conformal integer identity: FAIL: " << error.what() << '\n';
    return 1;
  }
}
