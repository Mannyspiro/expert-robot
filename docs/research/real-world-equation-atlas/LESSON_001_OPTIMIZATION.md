# Math Kung Fu — Lesson 001: Optimization as Shape

## Goal
Recognize optimization as choosing the best shape or state while obeying a constraint.

## The puzzle
A rectangular garden must enclose exactly 12 square metres. You want to use as little fencing as possible.

Let its side lengths be x and y.
- Area constraint: xy = 12.
- Fencing objective: P = 2x + 2y.

The constraint tells us which rectangles are allowed. The objective tells us which allowed rectangle is best.

Since y = 12/x:
[
P(x)=2x+rac{24}{x},quad x>0.
]

Compare:
- 3 m by 4 m: P = 14 m.
- 2 m by 6 m: P = 16 m.
- A square with side \(\sqrt{12}\approx3.464\) m: P \(\approx13.856\) m.

The square uses the least fencing among rectangles with fixed area.

## Geometric intuition
If one side becomes very long, the other must become very short to keep the same area. The long side then dominates the perimeter. If one side becomes very short, the other becomes very long. The balanced shape wins.

## The general pattern
[
\text{best allowed state} = \arg\min_x \text{cost}(x)
\quad\text{subject to}\quad \text{constraint}(x).
]

## Structural analogies
- A delivery route: minimize travel cost while visiting required stops.
- A robot arm: minimize movement or energy while reaching a target.
- A circuit: minimize power loss while meeting output constraints.
- A production line: minimize cost while meeting demand and capacity limits.

The same *optimization structure* appears in each case; the variables, cost, and constraints are different.

## Recall check
Without calculating: why does making the rectangle more and more narrow eventually increase the amount of fencing?

## Extension
Find the rectangle with fixed area A and minimum perimeter. Use the same reasoning, then explain why the result is independent of the particular positive value of A.
