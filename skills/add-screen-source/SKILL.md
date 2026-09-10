# Skill: Add a film/TV music source

## Goal

Add evidence that a musical work or recording appeared in a movie or TV episode while keeping film/TV identity separate from soundtrack evidence.

## Model

`screen_titles` identifies movies, series and episodes.

`screen_appearances` links a `recording_id` and/or `work_id` to a screen title.

TMDB/IMDb IDs identify the screen work. They do **not** by themselves prove a song was used.

## Procedure

1. Resolve the movie/series/episode to a stable TMDB ID where possible.
2. Store its IMDb ID as a cross-reference when available.
3. For television, resolve the exact episode whenever the evidence supports it.
4. Resolve the music reference:
   - exact recording when possible;
   - otherwise the underlying work;
   - do not guess a particular recording.
5. Add one `screen_appearances` observation per supported use.
6. Record `usage_type` only when supported:
   - soundtrack
   - performed
   - background
   - credits
   - unknown
7. Store optional scene/context text only when sourced.
8. Retain `source_id`, confidence and verification state.
9. Deduplicate observations without deleting independent supporting sources.
10. Validate and render Quarto.

## Source separation

Use TMDB primarily for screen metadata and identity. A separate soundtrack,
music database, liner/source page, publication or curated dataset may provide
the actual music-use evidence.

Do not treat ordinary movie cast/crew credits as a complete soundtrack list.

## Matching rule

A title match alone is insufficient. Prefer:
1. stable recording identifier / ISRC / MusicBrainz mapping;
2. explicit artist + recording;
3. explicit work/song with unknown recording;
4. unresolved candidate for manual review.

## Checklist

- [ ] Movie/series/episode identity resolved
- [ ] Exact episode used where possible
- [ ] Recording vs work distinction preserved
- [ ] Source proves or supports the appearance
- [ ] Usage context not invented
- [ ] Provenance retained
- [ ] Confidence/review state set
