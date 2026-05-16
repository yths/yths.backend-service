# Issues

## Miscellaneous

- [ ] Add representative screenshots / dashboard examples to `README.md`
- [ ] Document a minimal "consumer recipe" for clients other than qtile

## Monitor

- [ ] Make stream cap (`STREAM_MAXLEN`) configurable per stream rather than a single global constant
- [ ] Surface per-job last-success timestamps in a `health` stream so clients can detect a stalled job

## Pacman Hook

- [ ] Parameterize the hardcoded UID range (`1000..59999`) in `_primary_user` for non-Arch distros that use different conventions

## Bugs

- [x] Subprocess calls could hang the scheduler
    - (2026-05-16) replaced ad-hoc invocations with `subprocess_safe.py` wrapper
- [x] OBS auth failure leaked exceptions to the scheduler
    - (2026-05-16) made the OBS connection lazy and per-tick recoverable
