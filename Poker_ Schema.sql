-- Chunk 1: Players

create table if not exists players (
  player_id bigserial primary key,
  display_name text not null,
  avatar_url text, -- can be null
  created_at timestamptz not null default now()
 );
create unique index if not exists uq_players_display_name_ci
  on players (lower(display_name));


-- Chunk 2: Venues (where games happen)

create table if not exists venues (
  venue_id bigserial primary key,         -- EN: auto id
  venue_name text not null,               -- EN: name like "Gino's"
  address text,                           -- EN: optional
  city text default 'Atlanta',            -- EN: default city
  state text default 'GA',                -- EN: default state
  created_at timestamptz not null default now() -- EN: auto timestamp
);

-- EN: prevent "Gino's" and "gino's" duplicates
create unique index if not exists uq_venues_name_ci
  on venues (lower(venue_name));


-- Chunk 3: Games (each tournament instance)

create table if not exists games (
  game_id bigserial primary key,                 -- EN: unique game id
  venue_id bigint not null references venues(venue_id),
  game_title text,                               -- EN: optional display title
  start_time timestamptz not null,               -- EN: when the tournament starts
  status text not null default 'completed',      -- EN: completed | active | scheduled
  created_at timestamptz not null default now()
);

-- EN: fast lookup for "recent games"
create index if not exists idx_games_start_time
  on games (start_time desc);

-- EN: fast lookup by venue
create index if not exists idx_games_venue
  on games (venue_id);
  
-- Make (venue_id, start_time) a stable unique identifier for a game
alter table games
  add constraint uq_games_venue_start_time unique (venue_id, start_time);


-- Chunk 4: Results (one row = one player's outcome in one game)
-- Stores rank, points, KOs, and who eliminated whom

create table if not exists results (
  result_id bigserial primary key,

  game_id bigint not null
    references games(game_id)
    on delete cascade,

  player_id bigint not null
    references players(player_id)
    on delete restrict,

  finish_rank int not null check (finish_rank >= 1),
  points int not null check (points >= 0),
  kos int not null default 0 check (kos >= 0),

  eliminated_by_player_id bigint
    references players(player_id)
    on delete set null,

  created_at timestamptz not null default now(),

  -- each player appears once per game
  constraint uq_results_game_player unique (game_id, player_id),

  -- prevent self-elimination
  constraint chk_not_self_eliminate
    check (
      eliminated_by_player_id is null
      or eliminated_by_player_id <> player_id
    )
);

-- speed up game detail page (ordered by rank)
create index if not exists idx_results_game_rank
  on results (game_id, finish_rank asc);

-- speed up player history / rankings
create index if not exists idx_results_player
  on results (player_id);

-- speed up elimination lookups
create index if not exists idx_results_eliminated_by
  on results (eliminated_by_player_id);