- A resize/state-sync fix needs three tests: the forward repro, the reverse direction, and the boundary that invalidates the shared index (list shrinks below the selected position). A mock that only echoes a prop proves the fix only if the real child's contract for that prop is independently verified, not assumed.
- A fix framed as intermittent / cache-warmth-dependent needs a deterministic unit test — a live browser proof only demonstrates whatever cache state happened to be present, not the race the fix targets.

- When a boolean gate lists two enum values (op === A || op === B), tests exercising only ONE leave the shared branch unverified for the other — use it.each([A, B]) like sibling tests in the same file.
- When a test asserts a size/threshold guard, recompute the fixture's actual bytes — synthetic "bloated" fixtures are frequently an order of magnitude short of the limit they claim to test, making the assertion a test-that-cant-fail.
