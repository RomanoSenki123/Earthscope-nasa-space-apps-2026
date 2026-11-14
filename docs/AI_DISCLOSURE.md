# AI assistance disclosure

**Tool used:** Claude Code (Anthropic).

**What the AI did**

- Wrote the application code (`app.py`, the `earthscope/` package) from the team's written specification.
- Wrote the unit tests and ran them.
- Ran the app against the live NASA POWER API to check that it works.
- Drafted the README, the documents in `docs/` and the drafts in `submission/`.

**What the AI did not do**

- It did not generate, estimate or alter any climate data. Every number the app shows is computed at run time from records returned by the NASA POWER API.
- It did not produce images, logos, video or audio.
- It did not submit anything to NASA, publish the repository or deploy the app.

**What the team did**

- Chose the challenge and set the project's scope and Caribbean focus.
- Supplied the written specification that the implementation followed.
- Ran the app locally and inspected the results on screen.
- Ran an automated code review with CodeRabbit (an AI code-review tool) and directed the fixes for its eight findings.
- Checked the challenge's resource list against the data source used.
- Committed and published the code, and prepared the submission.


Synthetic values exist only in `tests/` as clearly labelled fixtures and are never
displayed by the app.
