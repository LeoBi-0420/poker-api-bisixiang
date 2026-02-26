----- Example: 
-- Players
insert into players (display_name)
values
  ('The Don'),
  ('Lee Nash'),
  ('Paul Marsala'),
  ('Anthony Glaser'),
  ('Jamar Graham'),
  ('Brendan Rester')
on conflict do nothing;

-- Venues
insert into venues (venue_name)
values
  ('Urban Pie'),
  ('Gino''s')
on conflict do nothing;

-- Games
insert into games (venue_id, game_title, start_time)
select
  v.venue_id,
  'Urban Pie Sundays',
  '2026-01-11 19:00:00-05'
from venues v
where v.venue_name = 'Urban Pie'
on conflict (venue_id, start_time) do nothing;

-- Results
insert into results (
  game_id,
  player_id,
  finish_rank,
  points,
  kos,
  eliminated_by_player_id
)
select
  g.game_id,
  p.player_id,
  r.finish_rank,
  r.points,
  r.kos,
  eb.player_id
from games g
join (
  values
    ('The Don',        1, 10, 6, null),
    ('Lee Nash',       2,  7, 2, 'The Don'),
    ('Paul Marsala',   3,  6, 0, 'The Don'),
    ('Anthony Glaser', 4,  5, 3, 'The Don'),
    ('Jamar Graham',   5,  4, 2, 'The Don'),
    ('Brendan Rester', 6,  3, 3, 'Anthony Glaser')
) as r(name, finish_rank, points, kos, eliminated_by)
  on true
join players p
  on p.display_name = r.name
left join players eb
  on eb.display_name = r.eliminated_by
where g.start_time = '2026-01-11 19:00:00-05'
  and g.venue_id = (
    select venue_id
    from venues
    where venue_name = 'Urban Pie'
  )
on conflict (game_id, player_id) do update
set
  finish_rank = excluded.finish_rank,
  points = excluded.points,
  kos = excluded.kos,
  eliminated_by_player_id = excluded.eliminated_by_player_id;
