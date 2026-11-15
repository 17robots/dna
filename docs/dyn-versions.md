# Dyn version policy

DNA is written in Dyn, which is still in preview. Between November 3 and
November 14, 2026, Dyn shipped previews 32 to 38. DNA followed each one, and
every DNA commit in that period was a port. This policy keeps DNA from
spending its time on SDK churn.

## Rules

1. **One pin per DNA release.** `mise.toml` pins exactly one Dyn preview with
   verified checksums. A DNA release names that preview in
   `RELEASE_NOTES.md`.
2. **Port in batches.** Do not port to every Dyn preview. Port when one of
   these is true:
   - DNA needs a fix or feature that only a newer preview has.
   - The pinned preview is three or more previews behind the latest.
   - A DNA release is being prepared and the latest preview is at least a
     few days old with no follow-up fix.
3. **A port is its own change.** Keep the port separate from feature and
   usability work: pin, port sources, run `just smoke`, and land it before
   other work continues on top.
4. **Feature work does not wait.** Between ports, work against the pinned
   preview. Dyn changes that DNA does not need yet are not a reason to stop.
5. **Report breakage upstream.** When a port needs DNA-side workarounds for a
   compiler or SDK problem, file it against Dyn and note the workaround in the
   port's commit message so it can be removed later.

## Porting checklist

- Update the version and every platform checksum in `mise.toml` together.
- Read the Dyn changelog and any migration guide for every preview skipped.
- Run `mise exec -- just fmt` (it visits every module directory), then
  `mise exec -- just smoke`.
- Build the module profiles too (`scripts/profile.py minimal release` and
  `terminal release`); they compile a reduced file set and catch missing
  definitions the full build hides.
- Restart language servers: the Dyn server comes from the pinned compiler
  when the project's `mise.toml` lists dyn.

## When to revisit

Revisit this policy when Dyn declares its language frozen. After that,
following each Dyn release should cost little, and DNA can track the latest
release directly.
