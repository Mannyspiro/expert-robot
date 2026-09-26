#pragma once

#include <cstdint>
#include <stdexcept>

namespace expert_robot::geometry {

struct IntegerPoint3 {
  std::int64_t x;
  std::int64_t y;
  std::int64_t z;
};

// Bounding the input keeps every intermediate product within int64_t.
inline constexpr std::int64_t kCoordinateLimit = 1000000;

inline void require_bounded(const IntegerPoint3& point) {
  const auto within = [](std::int64_t value) {
    return value >= -kCoordinateLimit && value <= kCoordinateLimit;
  };
  if (!within(point.x) || !within(point.y) || !within(point.z)) {
    throw std::out_of_range("conformal point exceeds exact integer range");
  }
}

class ConformalPoint3 {
 public:
  std::int64_t origin() const { return origin_; }
  std::int64_t x() const { return x_; }
  std::int64_t y() const { return y_; }
  std::int64_t z() const { return z_; }
  std::int64_t infinity() const { return infinity_; }

 private:
  friend ConformalPoint3 embed(const IntegerPoint3& point);
  friend std::int64_t inner_product(const ConformalPoint3& a,
                                    const ConformalPoint3& b);

  ConformalPoint3(std::int64_t origin, std::int64_t x, std::int64_t y,
                  std::int64_t z, std::int64_t infinity)
      : origin_(origin), x_(x), y_(y), z_(z), infinity_(infinity) {}

  std::int64_t origin_;
  std::int64_t x_;
  std::int64_t y_;
  std::int64_t z_;
  std::int64_t infinity_;
};

// Represents 2X(p) = 2e_o + 2p + |p|^2 e_inf, with e_o . e_inf = -1.
inline ConformalPoint3 embed(const IntegerPoint3& point) {
  require_bounded(point);
  const auto norm_squared = point.x * point.x + point.y * point.y +
                            point.z * point.z;
  return {2, 2 * point.x, 2 * point.y, 2 * point.z, norm_squared};
}

inline std::int64_t inner_product(const ConformalPoint3& a,
                                  const ConformalPoint3& b) {
  return a.x_ * b.x_ + a.y_ * b.y_ + a.z_ * b.z_ -
         a.origin_ * b.infinity_ - a.infinity_ * b.origin_;
}

inline std::int64_t squared_distance(const IntegerPoint3& a,
                                     const IntegerPoint3& b) {
  require_bounded(a);
  require_bounded(b);
  const auto dx = a.x - b.x;
  const auto dy = a.y - b.y;
  const auto dz = a.z - b.z;
  return dx * dx + dy * dy + dz * dz;
}

}  // namespace expert_robot::geometry
