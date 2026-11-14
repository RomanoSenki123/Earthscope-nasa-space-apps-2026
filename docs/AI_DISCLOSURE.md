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

- Chose the challenge and defined the scope, data source, method and scientific framing in the specification.

> **Team lead: before submitting, add what you personally reviewed and tested**
> (for example: ran the app, checked the results, read the code, recorded the demo).
> Do not claim review that did not happen.

Synthetic values exist only in `tests/` as clearly labelled fixtures and are never
displayed by the app.
