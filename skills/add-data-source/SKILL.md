# Skill: Add a data source

## Before coding

Document owner, purpose, access method, licensing/usage constraints, credentials, rate limits, cache strategy, stable IDs, target fields, provenance and known gaps.

## Adapter contract

Create an adapter under `src/music_life/sources/`.

It must:
1. cache raw data before normalization when permitted;
2. be idempotent;
3. contain no dashboard formatting;
4. retain source-native IDs;
5. map into reusable normalized tables;
6. write provenance;
7. preserve conflicts unless an explicit resolution rule exists;
8. be testable without live network calls.

## Chart-source rule

Prefer complete weekly snapshots. Preserve chart name, territory, chart date, rank, source artist/title strings, previous rank, peak-to-date, weeks on chart and source reference. Canonical entity resolution happens afterwards.

## Checklist

- [ ] Cache strategy documented
- [ ] Secrets gitignored
- [ ] Native IDs retained
- [ ] Provenance retained
- [ ] Idempotent
- [ ] Limitations documented
