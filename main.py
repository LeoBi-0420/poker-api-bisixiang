# main.py
import os
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from datetime import datetime
from typing import List
from db import get_conn


app = FastAPI(
    docs_url="/api-docs",
    swagger_ui_oauth2_redirect_url="/api-docs/oauth2-redirect",
)

frontend_origins_env = os.getenv("FRONTEND_ORIGINS", "")
frontend_origins = [
    origin.strip()
    for origin in frontend_origins_env.split(",")
    if origin.strip()
]
if not frontend_origins:
    frontend_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GameCreate(BaseModel):
    game_title: str
    start_time: datetime
    venue_id: int

class ResultCreate(BaseModel):
    finish_rank: int
    player_id: int
    points: int
    kos: int
    eliminated_by_player_id: int | None = None

class PlayerCreate(BaseModel):
    display_name: str
    avatar_url: str | None = None


class VenueCreate(BaseModel):
    venue_name: str
    address: str | None = None
    city: str = "Atlanta"
    state: str = "GA"

@app.get("/")
def root():
    return {"message": "Poker backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/docs", include_in_schema=False)
def docs_redirect():
    return RedirectResponse(url="/api-docs")


@app.get("/games")
def list_games(
    limit: int = Query(20, ge=1, le=200),
    venue: str | None = Query(None),
):
    """
    EN: Returns recent games. Optional filter: venue (case-insensitive, partial match)
    CN: 返回最近的比赛列表。可选筛选：venue（大小写不敏感，支持模糊匹配）
    """

    base_sql = """
        SELECT
            g.game_id,
            g.game_title,
            g.start_time,
            g.status,
            v.venue_name
        FROM games g
        JOIN venues v ON v.venue_id = g.venue_id
    """

    params = {}

    # ✅ Only add WHERE when venue is provided
    if venue:
        base_sql += """
        WHERE lower(v.venue_name) LIKE lower(%(venue_like)s)
        """
        params["venue_like"] = f"%{venue}%"

    base_sql += """
        ORDER BY g.start_time DESC
        LIMIT %(limit)s;
    """
    params["limit"] = limit

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(base_sql, params)
            rows = cur.fetchall()

    out = []
    for (game_id, game_title, start_time, status, venue_name) in rows:
        out.append(
            {
                "game_id": game_id,
                "game_title": game_title,
                "start_time": start_time.isoformat() if start_time else None,
                "status": status,
                "venue_name": venue_name,
            }
        )

    return out


## GET /games/{game_id}
@app.get("/games/{game_id}")
def get_game(game_id: int):
    """
    EN: Get a single game with venue + results.
    CN: 获取单场比赛详情（包含 venue + results 榜单）。
    """

    # 1) Query game + venue
    game_sql = """
        select
            g.game_id,
            g.game_title,
            g.start_time,
            g.status,
            v.venue_id,
            v.venue_name
        from games g
        join venues v on v.venue_id = g.venue_id
        where g.game_id = %(game_id)s;
    """

    # 2) Query results (leaderboard)
    results_sql = """
        select
            r.finish_rank,
            p.display_name as player,
            r.points,
            r.kos,
            eb.display_name as eliminated_by
        from results r
        join players p on p.player_id = r.player_id
        left join players eb on eb.player_id = r.eliminated_by_player_id
        where r.game_id = %(game_id)s
        order by r.finish_rank asc;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            # game row
            cur.execute(game_sql, {"game_id": game_id})
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

            (gid, title, start_time, status, venue_id, venue_name) = row

            # results rows
            cur.execute(results_sql, {"game_id": game_id})
            results_rows = cur.fetchall()

    results = []
    for (finish_rank, player, points, kos, eliminated_by) in results_rows:
        results.append(
            {
                "finish_rank": finish_rank,
                "player": player,
                "points": points,
                "kos": kos,
                "eliminated_by": eliminated_by,
            }
        )

    return {
        "game_id": gid,
        "game_title": title,
        "start_time": start_time.isoformat() if start_time else None,
        "status": status,
        "venue": {
            "venue_id": venue_id,
            "venue_name": venue_name,
        },
        "results": results,
    }



## GET /games/{game_id}/results
@app.get("/games/{game_id}/results")
def game_results(game_id: int):
    """
    EN: Get results for a game (ordered by finish_rank)
    CN: 获取某场比赛的结果（按名次排序）
    """
    sql = """
        select
            r.finish_rank,
            p.display_name as player,
            r.points,
            r.kos,
            eb.display_name as eliminated_by
        from results r
        join players p on p.player_id = r.player_id
        left join players eb on eb.player_id = r.eliminated_by_player_id
        where r.game_id = %(game_id)s
        order by r.finish_rank asc;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"game_id": game_id})
            rows = cur.fetchall()

    # ✅ no results => return empty list (not 500)
    out = []
    for finish_rank, player, points, kos, eliminated_by in rows:
        out.append(
            {
                "finish_rank": finish_rank,
                "player": player,
                "points": points,
                "kos": kos,
                "eliminated_by": eliminated_by,
            }
        )
    return out


## Write API (create new games)
@app.post("/games")
def create_game(game: GameCreate):
    """
    EN: Create a new game using an existing venue_id.
    CN: 用已存在的 venue_id 创建一场比赛。
    """
    # 1) check venue exists
    sql_check_venue = "select venue_id, venue_name from venues where venue_id = %(venue_id)s;"
    sql_insert_game = """
        insert into games (game_title, start_time, status, venue_id)
        values (%(game_title)s, %(start_time)s, %(status)s, %(venue_id)s)
        returning game_id, game_title, start_time, status, venue_id;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            # check venue
            cur.execute(sql_check_venue, {"venue_id": game.venue_id})
            v = cur.fetchone()
            if not v:
                raise HTTPException(status_code=400, detail=f"venue_id {game.venue_id} does not exist")

            venue_id, venue_name = v

            # insert game
            cur.execute(
                sql_insert_game,
                {
                    "game_title": game.game_title,
                    "start_time": game.start_time,
                    "status": "scheduled",
                    "venue_id": venue_id,
                },
            )
            row = cur.fetchone()

    game_id, game_title, start_time, status, venue_id = row

    return {
        "game_id": game_id,
        "game_title": game_title,
        "start_time": start_time.isoformat() if start_time else None,
        "status": status,
        "venue": {
            "venue_id": venue_id,
            "venue_name": venue_name,
        },
    }

## Post Results
@app.post("/games/{game_id}/results")
def add_results(game_id: int, results: List[ResultCreate]):
    """
    EN: Add results for a game
    CN: 为指定比赛添加结果（批量）
    """

    with get_conn() as conn:
        with conn.cursor() as cur:

            # 1. Check game exists
            cur.execute(
                "select 1 from games where game_id = %s",
                (game_id,),
            )
            if cur.fetchone() is None:
                return {"error": f"Game {game_id} not found"}

            # 2. Insert results
            for r in results:
               cur.execute(
    """
    insert into results
      (game_id, finish_rank, player_id, points, kos, eliminated_by_player_id)
    values
      (%s, %s, %s, %s, %s, %s)
    on conflict (game_id, player_id)
    do update set
      finish_rank = excluded.finish_rank,
      points = excluded.points,
      kos = excluded.kos,
      eliminated_by_player_id = excluded.eliminated_by_player_id
    """,
    (
        game_id,
        r.finish_rank,
        r.player_id,
        r.points,
        r.kos,
        r.eliminated_by_player_id,
    ),
)


    return {
        "game_id": game_id,
        "inserted_results": len(results),
    }


## Create players
@app.get("/players")
def list_players(
    limit: int = Query(50, ge=1, le=500),
    q: str | None = Query(None),
):
    """
    EN: List players. Optional search by display_name (case-insensitive, partial).
    CN: 玩家列表。可选按 display_name 模糊搜索（大小写不敏感）。
    """
    sql = """
        select player_id, display_name, avatar_url, created_at
        from players
    """
    params = {"limit": limit}

    if q:
        sql += " where lower(display_name) like lower(%(q)s) "
        params["q"] = f"%{q}%"

    sql += " order by created_at desc limit %(limit)s; "

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    out = []
    for (player_id, display_name, avatar_url, created_at) in rows:
        out.append(
            {
                "player_id": player_id,
                "display_name": display_name,
                "avatar_url": avatar_url,
                "created_at": created_at.isoformat() if created_at else None,
            }
        )
    return out


@app.post("/players")
def create_player(player: PlayerCreate):
    """
    EN: Create a player (case-insensitive unique by display_name).
    CN: 创建玩家（display_name 大小写不敏感唯一）。
    """
    # 1) check duplicate (case-insensitive)
    sql_check = """
        select player_id, display_name, avatar_url, created_at
        from players
        where lower(display_name) = lower(%(name)s)
        limit 1;
    """
    sql_insert = """
        insert into players (display_name, avatar_url)
        values (%(name)s, %(avatar_url)s)
        returning player_id, display_name, avatar_url, created_at;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_check, {"name": player.display_name})
            existing = cur.fetchone()
            if existing:
                # 用 409 更符合 REST（你也可以改成直接返回 existing）
                raise HTTPException(
                    status_code=409,
                    detail=f"player '{player.display_name}' already exists",
                )

            cur.execute(
                sql_insert,
                {"name": player.display_name, "avatar_url": player.avatar_url},
            )
            row = cur.fetchone()

    (player_id, display_name, avatar_url, created_at) = row
    return {
        "player_id": player_id,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "created_at": created_at.isoformat() if created_at else None,
    }


## Create venues
@app.get("/venues")
def list_venues(
    limit: int = Query(50, ge=1, le=500),
    q: str | None = Query(None),
):
    """
    EN: List venues. Optional search by venue_name (case-insensitive, partial).
    CN: 场地列表。可选按 venue_name 模糊搜索（大小写不敏感）。
    """
    sql = """
        select venue_id, venue_name, address, city, state, created_at
        from venues
    """
    params = {"limit": limit}

    if q:
        sql += " where lower(venue_name) like lower(%(q)s) "
        params["q"] = f"%{q}%"

    sql += " order by created_at desc limit %(limit)s; "

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    out = []
    for (venue_id, venue_name, address, city, state, created_at) in rows:
        out.append(
            {
                "venue_id": venue_id,
                "venue_name": venue_name,
                "address": address,
                "city": city,
                "state": state,
                "created_at": created_at.isoformat() if created_at else None,
            }
        )
    return out


@app.post("/venues")
def create_venue(venue: VenueCreate):
    """
    EN: Create a venue (case-insensitive unique by venue_name).
    CN: 创建场地（venue_name 大小写不敏感唯一）。
    """
    sql_check = """
        select venue_id, venue_name, address, city, state, created_at
        from venues
        where lower(venue_name) = lower(%(name)s)
        limit 1;
    """
    sql_insert = """
        insert into venues (venue_name, address, city, state)
        values (%(name)s, %(address)s, %(city)s, %(state)s)
        returning venue_id, venue_name, address, city, state, created_at;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_check, {"name": venue.venue_name})
            existing = cur.fetchone()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"venue '{venue.venue_name}' already exists",
                )

            cur.execute(
                sql_insert,
                {
                    "name": venue.venue_name,
                    "address": venue.address,
                    "city": venue.city,
                    "state": venue.state,
                },
            )
            row = cur.fetchone()

    (venue_id, venue_name, address, city, state, created_at) = row
    return {
        "venue_id": venue_id,
        "venue_name": venue_name,
        "address": address,
        "city": city,
        "state": state,
        "created_at": created_at.isoformat() if created_at else None,
    }
