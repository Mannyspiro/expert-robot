# Exact Integer CGA Reference

This small C++ reference checks the notebook's conformal distance identity
without promoting the notebook's other claims. It uses the null-basis
convention `e_o . e_inf = -1` and `e_o^2 = e_inf^2 = 0`.

For an integer point `p`, the stored components represent
`2X(p) = 2e_o + 2p + |p|^2 e_inf`. The conformal inner product therefore
satisfies `(2X(p)) . (2X(q)) = -2|p-q|^2`. For example, the points
`(1,0,0)` and `(0,1,0)` have inner product `-4` and squared
distance `2`.

Coordinates are restricted to [-1000000, 1000000]. This bound keeps the
largest possible squared distance at 12 trillion and its doubled value at
24 trillion, below the 64-bit signed limit. Values outside the domain throw
instead of silently overflowing. The reference test checks all 15625 pairs
in a small integer cube, nullness, and the domain extremes.

Passing these tests is computational evidence for this one identity, not a
Lean proof or a qualified general CGA kernel. A formal theorem and axiom
audit are required before adding it to the verified theorem registry.
