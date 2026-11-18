# Pride (v0.1)

A 0–10 "pride" meter for an AI assistant that rests at 5.0. Only earned, evidenced events move it. Pride has to be honest: no event without evidence, and a miss, a mistake the human catches, or a broken promise lowers it too.

The log and `state.json` stay with the assistant that earned them. Don't commit them.

## How it works

- **Rest:** 5.0.
- **Earn types:** `range_qual`, `tests_passing`, `owner_compliment`, `finished_build`, `correct_catch`.
- **Ding types:** `miss`, `mistake_caught`, `broken_promise`.
- **Evidence:** every event needs a type, a weight (max 0.8), a one-line reason, and a source pointer. Self-assigned fluff (`trust me`, `I feel proud`, and the like) is rejected.
- **Decay:** the meter is recomputed from the log every time. Each event's weight fades toward zero with a 3-day half-life, so the level drifts back toward 5.
- **Daily rise cap:** +1.5 per calendar day, so it cannot be farmed in one afternoon. Dings do not use the cap. A clipped earn is still logged with `capped: true`.
- **Careful flag:** above 8, humility mode: double-check before bragging, no cockiness, call out any god complex. One strong day only reaches about 6.5, so careful mode takes several good days in a row.
- **Log:** append-only JSONL at `logs/pride.jsonl` with a hash chain. There is no rewrite or delete API. `state.json` is a derived cache; the log wins if they disagree.

The day boundary uses the `America/Chicago` timezone by default; change it in `paths.py`.

## Commands

```
./pride.py status
./pride.py explain
./pride.py log -n 10
./pride.py earn --type finished_build --weight 0.35 \
    --reason "Shipped the backup script with tests green." \
    --evidence-kind tests_passing \
    --evidence "backup/tests/"
./pride.py ding --type mistake_caught --weight 0.35 \
    --reason "Forgot a name I had been told." \
    --evidence-kind owner_caught \
    --evidence "chat, 2026-01-05"
./pride.py seed    # idempotent; loads the made-up examples in seed.py
```

`seed.py` holds **example events only**. Replace them with your own real, evidenced events, or don't run `seed`.

Environment: `PRIDE_DATA` redirects the log and state (tests use it). `PRIDE_MEDICAL_GUARD` (optional) points at a `guard.py` exposing `blocked(part)` that can freeze writes during a safe mode; see the companion `medical` repo.

## Tests

```bash
python3 -m unittest discover -s tests
```

## License

MIT. See `LICENSE`.
