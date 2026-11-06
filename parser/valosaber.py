#!/usr/bin/env python3
"""Valosaber: sabermetric-style metrics from a parsed Valorant replay export."""
import json, re, sys
from functools import lru_cache
from pathlib import Path
import numpy as np, pandas as pd

exp, casts_csv, lookup_json, out = map(Path, sys.argv[1:5])
f = pd.read_parquet(exp/"fields.parquet")
ev = pd.read_parquet(exp/"events.parquet")
act = pd.read_parquet(exp/"actors.parquet")
fx = pd.read_csv(casts_csv)
look = json.load(open(lookup_json))["agents"]
MAN = json.load(open(exp/"manifest.json"))
BUILD = MAN["replay_build"]; DURATION_S = MAN["duration_ms"] / 1000.0
MODE = "Swiftplay" if act.class_path.astype(str).str.contains("Swiftplay").any() else "Standard"

# ---------- roster ----------
ps = f[f.group_path.astype(str).str.endswith("PlayerState_C") & (f.field_name.astype(str)=="Subject")]
subj = ps[["actor_net_guid","value_str"]].drop_duplicates().rename(columns={"actor_net_guid":"ps","value_str":"uuid"})
g = np.sort(subj.ps.unique()); cut = g[int(np.argmax(np.diff(g)))+1]
subj["team"] = np.where(subj.ps < cut, "A", "B")
casts_raw = pd.read_parquet(exp.parent/"out"/"casts_raw.parquet")
u2code = casts_raw.dropna(subset=["agent"]).drop_duplicates("caster").set_index("caster")["agent"].to_dict()
subj["code"] = subj.uuid.map(u2code)
def disp(code):
    e = look.get(code, {}); return e.get("name") or code
subj["agent"] = subj.code.map(disp)
u2agent = subj.set_index("uuid").agent.to_dict(); u2team = subj.set_index("uuid").team.to_dict()
code2uuid = subj.set_index("code").uuid.to_dict()
assert subj.code.notna().all(), subj

# combat-report component actors (OwnerExclusivePlayerInfo): identity map for now; resolved to players below
cr = f[f.group_path.astype(str).str.contains("CombatReport")].copy()
cr["field_name"] = cr.field_name.astype(str)
owners = {a: a for a in cr.actor_net_guid.unique()}

# ---------- reconstruct interactions (delta replication: last value per key) ----------
rx = re.compile(r"^Rounds\[(\d+)\]\.Reports\[(\d+)\]\.Interactions\[(\d+)\]\.(\w+)$")
rp = re.compile(r"^Rounds\[(\d+)\]\.Reports\[(\d+)\]\.(bDied|DeathLocation)$")
inter, died = {}, {}
for r in cr.sort_values("time_ms").itertuples(index=False):
    own = owners.get(r.actor_net_guid)
    if own is None: continue
    val = r.value_str if pd.notna(r.value_str) else (r.value_bool if pd.notna(r.value_bool) else (r.value_f64 if pd.notna(r.value_f64) else r.value_i64))
    m = rx.match(r.field_name)
    if m:
        k = (own, int(m[1]), int(m[2]), int(m[3])); d = inter.setdefault(k, {})
        d[m[4]] = val
        if m[4] == "bDidKill" and val is True or (m[4]=="bDidKill" and bool(val) and "kill_t" not in d): d.setdefault("kill_t", r.time_ms)
        continue
    m = rp.match(r.field_name)
    if m:
        k = (own, int(m[1]), int(m[2])); d = died.setdefault(k, {})
        if m[3] == "bDied" and bool(val): d.setdefault("t", r.time_ms)
        if m[3] == "DeathLocation" and isinstance(val, str) and val != "(0,0,0)":
            d["loc"] = [float(x) for x in val.strip("()").split(",")]

starts = ev[ev.group=="roundStarted"].sort_values("time1").time1.tolist()
R = len(starts)

# ---------- per-pair damage & kills ----------
rows = []
for (own, r, rep, i), d in inter.items():
    vic = d.get("ParticipantSubject")
    if not isinstance(vic, str): continue
    rows.append(dict(owner=own, rnd=r, rep=rep, other=vic,
        dealt=float(d.get("DamageDealt") or 0), recv=float(d.get("DamageRecieved") or 0),
        hits_d=float(d.get("HitsDealt") or 0), hits_r=float(d.get("HitsRecieved") or 0),
        did_kill=bool(d.get("bDidKill")), kill_t=d.get("kill_t")))
pr = pd.DataFrame(rows)
# ---- resolve owner actor -> player. DIRECT first: pawn.Controller == OwnerExclusivePlayerInfo.Owner and pawn.PlayerState gives the player.
# Reciprocity (my damage dealt == their damage received) is kept as a cross-check and as the fallback; it never aborts the run by itself.
from itertools import permutations
owners = {g: g for g in sorted(pr.owner.unique())}
fnS = f.field_name.astype(str)
def _last(actor, name):
    x = f[(f.actor_net_guid == actor) & (fnS == name) & f.value_i64.notna() & (f.value_i64 > 0)]
    return None if x.empty else int(x.sort_values(["time_ms", "packet_id"]).value_i64.iloc[-1])
ctrl2subject = {}
for p_ in MAN.get("players", []):
    for ch_ in p_.get("character_net_guids", []):
        c_ = _last(int(ch_), "Controller")
        if c_ is not None:
            ctrl2subject[c_] = p_["subject"]
direct = {}
for g_ in owners:
    c_ = _last(int(g_), "Owner") or _last(int(g_), "AresController")
    if c_ in ctrl2subject:
        direct[g_] = ctrl2subject[c_]
pair = {g: {} for g in owners}
for r_ in pr.itertuples(): pair[r_.owner][(r_.rnd, r_.other)] = (r_.dealt, r_.recv)
def cost(asg):
    inv = {u: g for g, u in asg.items()}; c = 0.0
    for g, u in asg.items():
        for (rn, other), (dl, rc) in pair[g].items():
            g2 = inv.get(other)
            if g2 is None: c += abs(dl) + abs(rc); continue
            back = pair[g2].get((rn, u), (0.0, 0.0))
            c += abs(dl - back[1]) + abs(rc - back[0])
    return c
RES = {"method": None}
if len(direct) == len(owners) and len(set(direct.values())) == len(owners):
    owners = direct; RES.update(method="direct_controller_chain", reciprocity_cost=cost(direct))
    print("owner-resolution: direct controller chain resolved all", len(owners), "owners; reciprocity residual", RES["reciprocity_cost"])
else:
    def owner_team(g):
        ts = [u2team.get(o) for (_, o) in pair[g] if o in u2team]; opp = "B" if np.mean([t=="A" for t in ts]) > .5 else "A"; return opp
    oteam = {g: owner_team(g) for g in owners}
    OA = [g for g in owners if oteam[g]=="A"]; OB = [g for g in owners if oteam[g]=="B"]
    UA = list(subj[subj.team=="A"].uuid); UB = list(subj[subj.team=="B"].uuid)
    assert len(OA)==5 and len(OB)==5, f"owner teams {len(OA)}/{len(OB)}; direct chain resolved {len(direct)} of {len(owners)}"
    best = []
    for pa in permutations(UA):
        for pb in permutations(UB):
            asg = dict(zip(OA, pa)); asg.update(dict(zip(OB, pb)))
            best.append((cost(asg), asg))
    best.sort(key=lambda x: x[0])
    runner = best[1][0] if len(best) > 1 else None
    print("owner-resolution (fallback): best cost", best[0][0], "| runner-up cost", runner)
    assert best[0][0] == 0 or (runner is not None and runner >= 1.5 * best[0][0] + 1.0), "reciprocity could not resolve owners unambiguously and the direct chain is incomplete"
    owners = best[0][1]; RES.update(method="reciprocity_fallback", reciprocity_cost=best[0][0], runner_up_cost=runner)
json.dump(RES, open(Path(sys.argv[4]).with_name("owner_resolution.json") if len(sys.argv) > 4 else "owner_resolution.json", "w"))
pr["owner"] = pr.owner.map(owners)
# teams: the guid-gap rule above is a guess; verify it against who damages whom (no friendly damage) and override on disagreement
_adj = {}
for a_, b_ in set(zip(pr.owner, pr.other)):
    _adj.setdefault(a_, set()).add(b_); _adj.setdefault(b_, set()).add(a_)
_col, _bad = {}, 0
_psmin = subj.sort_values("ps").uuid.tolist()
for s0 in _psmin:
    if s0 in _col or s0 not in _adj: continue
    _col[s0] = 0; st_ = [s0]
    while st_:
        u_ = st_.pop()
        for v_ in _adj.get(u_, ()):
            if v_ not in _col: _col[v_] = 1 - _col[u_]; st_.append(v_)
            elif _col[v_] == _col[u_]: _bad += 1
if len(_col) == len(subj) and _bad == 0:
    _first = _col[_psmin[0]]
    _new = {u: ("A" if c == _first else "B") for u, c in _col.items()}
    if _new != u2team:
        print("TEAM CHECK: guid-gap teams disagree with damage-opposition teams; using damage-opposition teams")
        u2team = _new; subj["team"] = subj.uuid.map(_new)
    else:
        print("team check: guid-gap teams agree with damage-opposition teams")
else:
    print("TEAM CHECK: could not 2-colour the damage graph (nodes", len(_col), "conflicts", _bad, "); keeping guid-gap teams, UNVERIFIED")
died = {(owners[k[0]],)+k[1:]: v for k, v in died.items()}

kills = (pr[pr.did_kill & pr.kill_t.notna()]
         .drop_duplicates(["rnd","owner","other"]).sort_values(["rnd","kill_t"])
         .rename(columns={"owner":"killer","other":"victim","kill_t":"t"})[["rnd","killer","victim","t"]].reset_index(drop=True))
n_death_events = int((ev.group=="characterDeath").sum())
print(f"kills reconstructed: {len(kills)}   characterDeath events: {n_death_events}")

# ---------- win-probability model (documented assumption: equal skill, next kill ~ alive share) ----------
@lru_cache(None)
def wp(a, b):
    if b == 0: return 1.0 if a > 0 else 0.5
    if a == 0: return 0.0
    return a/(a+b)*wp(a, b-1) + b/(a+b)*wp(a-1, b)
def li_raw(a, b):  # swing available from this state
    return abs(wp(a, b-1) - wp(a-1, b)) if a > 0 and b > 0 else 0.0

alive = {r: {"A":5,"B":5} for r in range(R)}
ks = []
for r, grp in kills.groupby("rnd"):
    al = {"A":5, "B":5}
    for k in grp.itertuples():
        kt, vt = u2team[k.killer], u2team[k.victim]
        a_k, a_v = al[kt], al[vt]
        before, after = wp(a_k, a_v), wp(a_k, a_v-1)
        ks.append(dict(rnd=int(r), t=int(k.t), killer=k.killer, victim=k.victim, kteam=kt, vteam=vt,
                       k_alive=a_k, v_alive=a_v, wpa=after-before, li_raw=li_raw(a_k, a_v),
                       wpA_after=(after if kt=="A" else 1-after)))
        al[vt] -= 1
    alive[r] = al
K = pd.DataFrame(ks)
K["li"] = K.li_raw / K.li_raw.mean()

# ---------- opening duels, trades, clutch ----------
K["opening"] = K.groupby("rnd").cumcount() == 0
K["traded"] = False
for i, k in K.iterrows():
    prior = K[(K.rnd==k.rnd) & (K.vteam==k.kteam) & (K.killer==k.victim) & (K.t > k.t) & (K.t <= k.t + 5000)]
    # kill i's victim killed a teammate of killer? "trade" = killer got killed by victim-team within 5s of killing? flipped below
# trade definition: a death is traded if the killer of that victim dies within 5s to the victim's team
D = K[["rnd","t","killer","victim"]].copy()
K["victim_traded"] = [bool(((K.rnd==k.rnd)&(K.victim==k.killer)&(K.t>k.t)&(K.t<=k.t+5000)).any()) for k in K.itertuples()]
K["trade_kill"] = [bool(((K.rnd==k.rnd)&(K.killer==u)&(K.victim==k.killer)).any()) for u in [None] for k in K.itertuples()] if False else False
tk = []
for k in K.itertuples():
    prev = K[(K.rnd==k.rnd)&(K.t<k.t)&(K.t>=k.t-5000)&(K.killer==k.victim)&(K.vteam==k.kteam)]
    tk.append(len(prev) > 0)
K["trade_kill"] = tk
K["clutch"] = (K.k_alive==1) & (K.v_alive>=2)

# ---------- utility assists ----------
GOOD = {"EnemiesRevealed","EnemiesMarked","EnemiesSuppressed","EnemiesVulnerabled","EnemiesNearsighted","EnemiesSeized","EnemiesSpotted","EnemiesDisplaced","EnemiesBlocked"}
fe = fx[fx.tag.isin(GOOD)&fx.target.notna()].copy()
lab2uuid = {}
# build label->uuid using codename labels from effects table (caster column = display label w/ codename)
for c, u in code2uuid.items(): lab2uuid[c] = u
fe["caster_uuid"] = fe.caster.map(lab2uuid); fe["target_uuid"] = fe.target.map(lab2uuid)
K["util_assist"] = False; K["util_caster"] = None
for i, k in K.iterrows():
    m = fe[(fe.target_uuid==k.victim)&(fe.abs_ms<=k.t+500)&(fe.abs_ms>=k.t-8000)&(fe.caster_uuid.map(u2team)==k.kteam)]
    if len(m): K.loc[i,"util_assist"] = True; K.loc[i,"util_caster"] = m.iloc[0].caster_uuid

# ---------- per-player table ----------
P = []
rounds_played = R
for u in subj.uuid:
    pp = pr[pr.owner==u]
    dmg_d, dmg_r = pp.dealt.sum(), pp.recv.sum()
    kk = K[K.killer==u]; dd = K[K.victim==u]
    P.append(dict(uuid=u, agent=u2agent[u], codename=subj.set_index("uuid").code[u], team=u2team[u],
        kills=len(kk), deaths=len(dd), dmg=dmg_d, dmg_taken=dmg_r, adr=dmg_d/R, dpr_taken=dmg_r/R,
        kwpa=kk.wpa.sum(), dwpa=-dd.wpa.sum(), wpa=kk.wpa.sum()-dd.wpa.sum(),
        avg_li_kills=kk.li.mean() if len(kk) else None,
        xk=dmg_d/100.0, kill_luck=len(kk)-dmg_d/100.0,
        fb=int(kk.opening.sum()), fd=int(dd.opening.sum()),
        trade_kills=int(kk.trade_kill.sum()), traded_deaths=int(dd.victim_traded.sum()),
        clutch_kills=int(kk.clutch.sum()), util_assisted_kills=int(kk.util_assist.sum()),
        util_assists_given=int((K.util_caster==u).sum())))
P = pd.DataFrame(P)
P["adr_idx"] = 100*P.adr/P.adr.mean()
P["kd_dmg_ratio"] = P.dmg/P.dmg_taken.replace(0,np.nan)
def kst(u):
    ok = 0
    for r in range(R):
        kr = K[K.rnd==r]
        if (kr.killer==u).any() or not (kr.victim==u).any() or bool(kr[kr.victim==u].victim_traded.any()): ok += 1
    return 100.0*ok/R
P["kst_pct"] = P.uuid.map(kst)
P["rank_wpa"] = P.wpa.rank(ascending=False).astype(int)


# ---------- economy (RoundInfos on the per-player info actor) ----------
oi = f[f.group_path.astype(str).str.endswith("OwnerExclusivePlayerInfo") & f.field_name.astype(str).str.startswith("RoundInfos[")].sort_values("time_ms")
rx2 = re.compile(r"^RoundInfos\[(\d+)\]\.(\w+)$"); eco = {}
for r_ in oi.itertuples():
    m_ = rx2.match(str(r_.field_name))
    if not m_ or r_.actor_net_guid not in owners: continue
    v_ = r_.value_i64 if pd.notna(r_.value_i64) else r_.value_f64
    eco.setdefault((owners[r_.actor_net_guid], int(m_[1])), {})[m_[2]] = v_
E = []
for (u_, idx), d_ in eco.items():
    rn = int(d_.get("RoundNumber", idx))
    E.append(dict(uuid=u_, agent=u2agent[u_], rnd=rn, start_money=d_.get("StartOfRoundMoney"), start_loadout=d_.get("StartOfRoundLoadoutValue"),
                  end_money=d_.get("EndOfRoundMoney"), end_loadout=d_.get("EndOfRoundLoadoutValue")))
E = pd.DataFrame(E)
print("economy rows:", len(E), "rounds:", sorted(E.rnd.unique()) if len(E) else None)
econ_usable = bool(len(E)) and float(E.start_loadout.fillna(0).sum()) > 0
print("economy usable:", econ_usable, "| max start_money:", float(E.start_money.fillna(0).max()) if len(E) else None)
if econ_usable:
    e1 = E.groupby("uuid").agg(avg_loadout=("start_loadout","mean"), total_loadout=("start_loadout","sum")).reset_index()
    P = P.merge(e1, on="uuid", how="left")
    P["dmg_per_1k_loadout"] = P.dmg / (P.total_loadout/1000.0)
    P["wpa_per_10k_loadout"] = P.wpa / (P.total_loadout/10000.0)

# ---------- per-round ----------
RR = []
plants = ev[ev.group=="spikePlanted"].time1.tolist()
for r in range(R):
    kr = K[K.rnd==r]; al = alive[r]
    endt = starts[r+1] if r+1 < R else ev.time1.max()
    pl = [p for p in plants if starts[r] <= p < endt]
    winner = "A" if al["B"]==0 else ("B" if al["A"]==0 else None)
    RR.append(dict(rnd=r, start_ms=int(starts[r]), kills=len(kr), alive_A=al["A"], alive_B=al["B"], winner_by_elim=winner,
        plant_ms=int(pl[0]) if pl else None,
        first_kill_ms=int(kr.t.min()) if len(kr) else None,
        timeline=[dict(t=int(k.t), wpA=round(float(k.wpA_after),4), killer=u2agent[k.killer], victim=u2agent[k.victim],
                       kteam=k.kteam, li=round(float(k.li),2), wpa=round(float(k.wpa),4), util=bool(k.util_assist), clutch=bool(k.clutch)) for k in kr.itertuples()]))

# duels matrix: damage exchanged
M = (pr.groupby(["owner","other"]).agg(dealt=("dealt","sum"), recv=("recv","sum")).reset_index())
M["owner"] = M.owner.map(u2agent); M["other"] = M.other.map(u2agent)

# death locations
DL = [dict(agent=u2agent[o], rnd=r, x=d["loc"][0], y=d["loc"][1], t=d.get("t")) for (o,r,rep),d in died.items() if "loc" in d]

# validations
chk = {}
chk["kills_vs_death_events"] = [len(K), n_death_events]
dd_ = pr.groupby("owner").dealt.sum().sum(); rr_ = pr.groupby("owner").recv.sum().sum()
chk["total_damage_dealt_vs_received"] = [float(dd_), float(rr_)]
chk["kill_time_vs_event_ms_max_gap"] = None
evt = np.sort(ev[ev.group=="characterDeath"].time1.values.astype("int64"))
if len(K): chk["kill_time_vs_event_ms_max_gap"] = float(max(np.min(np.abs(evt - int(t))) for t in K.t))
chk["deaths_with_location"] = [len(DL), len(K)]
print(json.dumps(chk, indent=1))


# ---------- Stage 1: per-kill credit inputs (utility setters, damage assisters) and heals ----------
kill_records = []
for k in K.itertuples():
    m_ = fe[(fe.target_uuid==k.victim)&(fe.abs_ms<=k.t+500)&(fe.abs_ms>=k.t-8000)&(fe.caster_uuid.map(u2team)==k.kteam)]
    setters = [dict(agent=u2agent[u_], tags=sorted(set(g_.tag)), n=int(len(g_))) for u_, g_ in m_.groupby("caster_uuid")]
    a_ = pr[(pr.rnd==k.rnd)&(pr.other==k.victim)&(pr.dealt>0)]
    a_ = a_[a_.owner.map(u2team)==k.kteam]
    assisters = [dict(agent=u2agent[o_], dmg=round(float(d_),1)) for o_, d_ in a_.groupby("owner").dealt.sum().items() if o_ != k.killer]
    kill_records.append(dict(rnd=int(k.rnd), t=int(k.t), killer=u2agent[k.killer], victim=u2agent[k.victim], kteam=k.kteam,
        wpa=round(float(k.wpa),4), li=round(float(k.li),3), setters=setters, assisters=assisters))
heal_records = []
for h_ in fx[fx.tag=="HealingDone"].drop_duplicates(["cast","target"]).itertuples():
    cu = lab2uuid.get(h_.caster); tm = u2team.get(cu)
    if cu is None or pd.isna(h_.round): continue
    al = {"A":5,"B":5}
    for kk in K[(K.rnd==int(h_.round))&(K.t<=h_.abs_ms)].itertuples(): al[kk.vteam]-=1
    own, opp = al[tm], al["B" if tm=="A" else "A"]
    cost = wp(own, opp) - wp(own-1, opp) if own>0 else 0.0
    heal_records.append(dict(agent=u2agent[cu], rnd=int(h_.round), t=int(h_.abs_ms), hp=round(float(h_.per_target_value),1),
        self=bool(h_.target==h_.caster), death_cost=round(float(cost),4)))
print("stage1 records: kills", len(kill_records), "| with utility setters", sum(1 for r_ in kill_records if r_["setters"]), "| with damage assisters", sum(1 for r_ in kill_records if r_["assisters"]), "| heals", len(heal_records), round(sum(h_["hp"] for h_ in heal_records),1),"HP")

res = dict(kill_records=kill_records, heal_records=heal_records, build=BUILD, mode=MODE, rounds=R, duration_s=DURATION_S, players=P.round(4).to_dict("records"),
           rounds_detail=RR, duels=M.round(1).to_dict("records"), death_locations=DL, economy=(E.to_dict("records") if econ_usable else []), checks=chk,
           model=dict(wp_table={f"{a}v{b}": round(wp(a,b),4) for a in range(1,6) for b in range(1,6)}))
json.dump(res, open(out, "w"), indent=1, default=lambda o: None if (isinstance(o,float) and np.isnan(o)) else (o.item() if hasattr(o,"item") else str(o)))
pd.set_option("display.width",250,"display.max_columns",40)
print(P[["agent","team","kills","deaths","dmg","adr","adr_idx","wpa","kwpa","dwpa","fb","fd","trade_kills","traded_deaths","clutch_kills","util_assisted_kills","util_assists_given","xk","kill_luck"]].round(2).sort_values("wpa",ascending=False).to_string(index=False))
print(pd.DataFrame(RR)[["rnd","kills","alive_A","alive_B","winner_by_elim","plant_ms"]].to_string(index=False))


# ======================================================================
# Compact shard: the only thing that needs to travel between machines.
# argv[5] = shard dir, argv[6] = match_id, argv[7] = raw .vrf size in bytes
# ======================================================================
if len(sys.argv) > 6:
    import hashlib, time
    shard = Path(sys.argv[5]); match_id = sys.argv[6]; raw_bytes = int(sys.argv[7]) if len(sys.argv) > 7 else None
    shard.mkdir(parents=True, exist_ok=True)
    def cat(df, cols):
        for c_ in cols:
            if c_ in df: df[c_] = df[c_].astype("category")
        return df
    T = {}
    pl = P.copy(); pl.insert(0, "match_id", match_id)
    T["players"] = cat(pl, ["match_id", "uuid", "agent", "codename", "team"])
    kt = K[["rnd","t","killer","victim","kteam","k_alive","v_alive","wpa","li","opening","victim_traded","trade_kill","clutch","util_assist"]].copy()
    kt.insert(0, "match_id", match_id)
    kt = kt.astype({"rnd":"int8","t":"int32","k_alive":"int8","v_alive":"int8","wpa":"float32","li":"float32"})
    T["kills"] = cat(kt, ["match_id","killer","victim","kteam"])
    dm = pr[["rnd","owner","other","dealt","recv","hits_d","hits_r","did_kill"]].copy(); dm.insert(0, "match_id", match_id)
    dm = dm.astype({"rnd":"int8","dealt":"float32","recv":"float32","hits_d":"int16","hits_r":"int16"})
    T["damage"] = cat(dm, ["match_id","owner","other"])
    ef = fx[["cast","round","abs_ms","caster","slot_id","tag","value","target","per_target_value"]].copy(); ef.insert(0, "match_id", match_id)
    ef = ef.astype({"round":"int8","abs_ms":"float32","value":"float32","per_target_value":"float32"})
    T["effects"] = cat(ef, ["match_id","cast","caster","tag","target"])
    # positions at 4 Hz, quantised to int16 (world units, centidegrees)
    mv = pd.read_parquet(exp/"movement.parquet", columns=["time_ms","character_net_guid","pos_x","pos_y","pos_z","yaw"])
    CN = {}
    for cj in [Path(__file__).resolve().parent / "skill" / "codenames.json", *Path('/root/.claude/skills/synced').glob('*/valorant-vrf/scripts/codenames.json')]:
        if cj.exists(): CN = json.load(open(cj))['map']; break
    assert CN, "codenames.json not found (expected parser/skill/codenames.json); the roster join would silently drop players"
    g2u = {}
    for a_, cp in act[["actor_net_guid","class_path"]].drop_duplicates().itertuples(index=False):
        m_ = re.search(r"/Characters/(\w+)/", str(cp))
        if m_:
            c_ = CN.get(m_.group(1), m_.group(1))   # actor paths use raw codenames, casts use public names for confirmed ones
            if c_ in code2uuid: g2u[int(a_)] = code2uuid[c_]
    mv["uuid"] = mv.character_net_guid.map(lambda g: g2u.get(int(g)))
    cov = float(mv.uuid.notna().mean()); mv = mv[mv.uuid.notna()].copy()
    mv["bucket"] = (mv.time_ms // 250).astype("int32")
    mv = mv.sort_values("time_ms").groupby(["uuid","bucket"], as_index=False).last()
    def q16(s, lo, hi, name, dtype):
        """Round to an integer and store; missing stays missing; out of range FAILS (never clipped)."""
        r = s.round()
        bad = r.notna() & ((r < lo) | (r > hi))
        assert not bad.any(), f"positions_4hz: {int(bad.sum())} {name} values outside [{lo},{hi}] (min {r.min()}, max {r.max()}); refusing to clip"
        return r.astype(dtype)
    yaw_deg = mv.yaw
    pos = pd.DataFrame({"match_id": match_id, "uuid": mv.uuid, "t": (mv.bucket*250).astype("int32"),
        "x": q16(mv.pos_x, -32768, 32767, "x", "Int16"), "y": q16(mv.pos_y, -32768, 32767, "y", "Int16"),
        "z": q16(mv.pos_z, -32768, 32767, "z", "Int16"), "yaw_cd": q16(yaw_deg * 100, 0, 36000, "yaw_cd", "UInt16")})
    T["positions_4hz"] = cat(pos, ["match_id","uuid"])
    index = {"schema_version": 2, "match_id": match_id, "build": BUILD, "mode": MODE,
             "rounds": int(R), "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "position_actor_coverage": round(cov, 3),
             "positions_4hz_conversion": {"version": "2", "bucket_ms": 250, "t": "bucket start in ms on the replay clock (time_ms // 250 * 250)",
                 "selection": "last native observation in each 250 ms bucket, per player; no interpolation, buckets with no observation are absent",
                 "xyz": "native world units rounded to the nearest integer, int16, no scale and no offset; out of range fails the shard",
                 "yaw_cd": "native yaw degrees x 100 rounded, uint16, range 0 to 36000, source wraparound unchanged",
                 "missing": "stored as null, never replaced by zero"},
             "tables": {}}
    for name, df in T.items():
        fp = shard / f"{name}.parquet"; df.to_parquet(fp, compression="zstd", compression_level=12, index=False)
        index["tables"][name] = {"rows": int(len(df)), "bytes": fp.stat().st_size, "sha256": hashlib.sha256(fp.read_bytes()).hexdigest()}
    json.dump(index, open(shard/"index.json", "w"), indent=1)
    tot = sum(v["bytes"] for v in index["tables"].values())
    exp_bytes = sum(p_.stat().st_size for p_ in exp.glob("*.parquet"))
    print("\n=== shard ===")
    for n_, v in index["tables"].items(): print(f"{n_:15s} {v['rows']:7d} rows {v['bytes']:9,d} bytes")
    print(f"shard total      {tot:,d} bytes")
    print(f"parquet export   {exp_bytes:,d} bytes  (shard is {100*tot/exp_bytes:.1f}% of it)")
    if raw_bytes: print(f"raw .vrf         {raw_bytes:,d} bytes  (shard is {100*tot/raw_bytes:.1f}% of it)")
    print("position actor coverage:", round(cov, 3), "| players with positions:", int(T["positions_4hz"].uuid.nunique()))
    assert cov > 0.99 and T["positions_4hz"].uuid.nunique() == 10, "position mapping incomplete"
