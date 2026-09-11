CREATE SEQUENCE IF NOT EXISTS seq_source START 1;
CREATE TABLE IF NOT EXISTS sources (
    source_id BIGINT PRIMARY KEY DEFAULT nextval('seq_source'),
    source_name VARCHAR NOT NULL,
    source_type VARCHAR NOT NULL,
    source_url VARCHAR,
    retrieved_at TIMESTAMP,
    citation_text VARCHAR,
    raw_reference VARCHAR
);

CREATE SEQUENCE IF NOT EXISTS seq_artist START 1;
CREATE TABLE IF NOT EXISTS artists (
    artist_id BIGINT PRIMARY KEY DEFAULT nextval('seq_artist'),
    slug VARCHAR UNIQUE NOT NULL,
    name VARCHAR NOT NULL,
    sort_name VARCHAR,
    birth_date DATE,
    death_date DATE,
    birth_place VARCHAR,
    musicbrainz_id VARCHAR,
    wikidata_id VARCHAR,
    discogs_id VARCHAR,
    spotify_id VARCHAR
);

CREATE SEQUENCE IF NOT EXISTS seq_person START 1;
CREATE TABLE IF NOT EXISTS people (
    person_id BIGINT PRIMARY KEY DEFAULT nextval('seq_person'),
    name VARCHAR NOT NULL,
    musicbrainz_id VARCHAR,
    wikidata_id VARCHAR,
    discogs_id VARCHAR,
    spotify_id VARCHAR
);

CREATE SEQUENCE IF NOT EXISTS seq_album START 1;
CREATE TABLE IF NOT EXISTS albums (
    album_id BIGINT PRIMARY KEY DEFAULT nextval('seq_album'),
    slug VARCHAR UNIQUE,
    title VARCHAR NOT NULL,
    artist_id BIGINT,
    original_release_date DATE,
    album_type VARCHAR,
    musicbrainz_release_group_id VARCHAR,
    discogs_master_id VARCHAR,
    spotify_album_id VARCHAR,
    spotify_url VARCHAR,
    spotify_uri VARCHAR,
    is_focus_album BOOLEAN DEFAULT FALSE
);

CREATE SEQUENCE IF NOT EXISTS seq_release START 1;
CREATE TABLE IF NOT EXISTS releases (
    release_id BIGINT PRIMARY KEY DEFAULT nextval('seq_release'),
    album_id BIGINT,
    title VARCHAR,
    country VARCHAR,
    release_date DATE,
    label VARCHAR,
    catalog_number VARCHAR,
    musicbrainz_release_id VARCHAR,
    discogs_release_id VARCHAR
);

CREATE SEQUENCE IF NOT EXISTS seq_work START 1;
CREATE TABLE IF NOT EXISTS works (
    work_id BIGINT PRIMARY KEY DEFAULT nextval('seq_work'),
    title VARCHAR NOT NULL,
    musicbrainz_work_id VARCHAR,
    iswc VARCHAR
);

CREATE SEQUENCE IF NOT EXISTS seq_recording START 1;
CREATE TABLE IF NOT EXISTS recordings (
    recording_id BIGINT PRIMARY KEY DEFAULT nextval('seq_recording'),
    title VARCHAR NOT NULL,
    primary_artist_name VARCHAR,
    release_year INTEGER,
    duration_ms INTEGER,
    musicbrainz_recording_id VARCHAR,
    isrc VARCHAR,
    spotify_track_id VARCHAR,
    spotify_uri VARCHAR,
    spotify_url VARCHAR,
    spotify_match_method VARCHAR,
    spotify_match_score DOUBLE,
    spotify_verified BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS album_tracks (
    album_id BIGINT,
    recording_id BIGINT,
    work_id BIGINT,
    disc_number INTEGER,
    track_number INTEGER,
    track_title VARCHAR,
    sample_url VARCHAR,
    sample_page VARCHAR,
    PRIMARY KEY (album_id, disc_number, track_number)
);

CREATE SEQUENCE IF NOT EXISTS seq_credit START 1;
CREATE TABLE IF NOT EXISTS credits (
    credit_id BIGINT PRIMARY KEY DEFAULT nextval('seq_credit'),
    person_id BIGINT,
    artist_id BIGINT,
    entity_type VARCHAR NOT NULL,
    entity_id BIGINT NOT NULL,
    role VARCHAR NOT NULL,
    instrument VARCHAR,
    credited_as VARCHAR,
    source_id BIGINT
);

CREATE SEQUENCE IF NOT EXISTS seq_relationship START 1;
CREATE TABLE IF NOT EXISTS relationships (
    relationship_id BIGINT PRIMARY KEY DEFAULT nextval('seq_relationship'),
    subject_type VARCHAR NOT NULL,
    subject_id BIGINT NOT NULL,
    predicate VARCHAR NOT NULL,
    object_type VARCHAR NOT NULL,
    object_id BIGINT NOT NULL,
    start_date DATE,
    end_date DATE,
    source_id BIGINT
);

CREATE SEQUENCE IF NOT EXISTS seq_event START 1;
CREATE TABLE IF NOT EXISTS life_events (
    event_id BIGINT PRIMARY KEY DEFAULT nextval('seq_event'),
    artist_id BIGINT NOT NULL,
    date_start DATE,
    date_end DATE,
    event_type VARCHAR,
    title VARCHAR NOT NULL,
    description VARCHAR,
    place VARCHAR,
    confidence DOUBLE,
    source_id BIGINT
);

CREATE SEQUENCE IF NOT EXISTS seq_claim START 1;
CREATE TABLE IF NOT EXISTS claims (
    claim_id BIGINT PRIMARY KEY DEFAULT nextval('seq_claim'),
    subject_type VARCHAR NOT NULL,
    subject_id BIGINT NOT NULL,
    predicate VARCHAR NOT NULL,
    value VARCHAR NOT NULL,
    date_start DATE,
    date_end DATE,
    source_id BIGINT,
    source_excerpt VARCHAR,
    confidence DOUBLE,
    extraction_method VARCHAR,
    review_status VARCHAR DEFAULT 'candidate'
);

CREATE SEQUENCE IF NOT EXISTS seq_theme START 1;
CREATE TABLE IF NOT EXISTS themes (
    theme_id BIGINT PRIMARY KEY DEFAULT nextval('seq_theme'),
    name VARCHAR UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS theme_links (
    theme_id BIGINT,
    entity_type VARCHAR,
    entity_id BIGINT,
    relationship VARCHAR,
    confidence DOUBLE,
    source_id BIGINT
);

CREATE SEQUENCE IF NOT EXISTS seq_chart START 1;
CREATE TABLE IF NOT EXISTS charts (
    chart_id BIGINT PRIMARY KEY DEFAULT nextval('seq_chart'),
    name VARCHAR NOT NULL,
    publisher VARCHAR,
    territory VARCHAR,
    chart_type VARCHAR,
    frequency VARCHAR
);

CREATE TABLE IF NOT EXISTS chart_entries (
    chart_id BIGINT NOT NULL,
    chart_date DATE NOT NULL,
    position INTEGER NOT NULL,
    artist_name VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    previous_position INTEGER,
    peak_to_date INTEGER,
    weeks_on_chart INTEGER,
    recording_id BIGINT,
    album_id BIGINT,
    source_id BIGINT,
    PRIMARY KEY (chart_id, chart_date, position)
);

CREATE TABLE IF NOT EXISTS research_targets (
    target_id VARCHAR PRIMARY KEY,
    entity_type VARCHAR NOT NULL,
    entity_slug VARCHAR NOT NULL,
    priority INTEGER,
    status VARCHAR,
    notes VARCHAR
);

-- Artist context: tags, places and a timeline, loaded from album bundles.
CREATE TABLE IF NOT EXISTS artist_tags (
    artist_id BIGINT NOT NULL,
    kind VARCHAR NOT NULL,              -- genre / instrument / occupation
    qid VARCHAR NOT NULL,
    label_is VARCHAR,
    label_en VARCHAR,
    source_id BIGINT,
    PRIMARY KEY (artist_id, kind, qid)
);

CREATE TABLE IF NOT EXISTS artist_places (
    artist_id BIGINT NOT NULL,
    role VARCHAR NOT NULL,              -- birth / death / residence / mentioned
    qid VARCHAR,
    title VARCHAR NOT NULL,
    label_is VARCHAR,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    context VARCHAR,
    source_id BIGINT,
    PRIMARY KEY (artist_id, role, title)
);

CREATE TABLE IF NOT EXISTS timeline_events (
    artist_id BIGINT NOT NULL,
    event_date DATE NOT NULL,
    date_precision INTEGER,             -- 9 year, 10 month, 11 day
    kind VARCHAR NOT NULL,              -- birth / death / career_start / career_end / album / cover / event
    label VARCHAR NOT NULL,
    detail VARCHAR,
    url VARCHAR,
    source_id BIGINT,
    PRIMARY KEY (artist_id, kind, event_date, label)
);

CREATE OR REPLACE VIEW focus_albums AS
SELECT * FROM albums WHERE is_focus_album = TRUE;


-- Film/TV identity and music-use layer.
CREATE SEQUENCE IF NOT EXISTS seq_screen START 1;
CREATE TABLE IF NOT EXISTS screen_titles (
    screen_id BIGINT PRIMARY KEY DEFAULT nextval('seq_screen'),
    title VARCHAR NOT NULL,
    original_title VARCHAR,
    screen_type VARCHAR NOT NULL,       -- movie / tv_series / episode
    release_date DATE,
    parent_screen_id BIGINT,            -- episode -> series
    season_number INTEGER,
    episode_number INTEGER,
    tmdb_id VARCHAR,
    imdb_id VARCHAR
);

CREATE SEQUENCE IF NOT EXISTS seq_screen_appearance START 1;
CREATE TABLE IF NOT EXISTS screen_appearances (
    appearance_id BIGINT PRIMARY KEY DEFAULT nextval('seq_screen_appearance'),
    recording_id BIGINT,
    work_id BIGINT,
    screen_id BIGINT NOT NULL,
    usage_type VARCHAR,                 -- soundtrack / performed / background / credits / unknown
    context VARCHAR,
    source_id BIGINT,
    confidence DOUBLE,
    verified BOOLEAN DEFAULT FALSE
);

CREATE OR REPLACE VIEW screen_usage_summary AS
SELECT
    r.recording_id,
    r.title AS recording_title,
    count(DISTINCT sa.appearance_id) AS appearances,
    count(DISTINCT CASE WHEN st.screen_type = 'movie' THEN st.screen_id END) AS movies,
    count(DISTINCT CASE WHEN st.screen_type = 'episode' THEN st.screen_id END) AS tv_episodes,
    min(st.release_date) AS earliest_screen_date,
    max(st.release_date) AS latest_screen_date
FROM recordings r
LEFT JOIN screen_appearances sa USING (recording_id)
LEFT JOIN screen_titles st USING (screen_id)
GROUP BY r.recording_id, r.title;
