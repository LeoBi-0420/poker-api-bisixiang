select
  g.game_title,
  g.start_time,
  v.venue_name,
  r.finish_rank,
  p.display_name as player,
  r.points,
  r.kos,
  eb.display_name as eliminated_by
from results r
join games g on g.game_id = r.game_id
join venues v on v.venue_id = g.venue_id
join players p on p.player_id = r.player_id
left join players eb on eb.player_id = r.eliminated_by_player_id
order by g.start_time desc, r.finish_rank;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public';
