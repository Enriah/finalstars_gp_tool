# -*- coding: utf-8 -*-
"""
IOM Sim - engine mô phỏng cho 'Interaction of Magic'.
Đọc luật từ config/*.json (rules, skills, relics, builds, scenarios).
Bạn KHÔNG cần sửa file này để chỉnh số liệu: hãy sửa JSON trong thư mục config.
"""
import copy
import heapq
import json
import os
import random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
INF = 1e18
PASSIVE_KEYS = ["molten_core", "zephyr_core", "fulgur_chain", "shadow_screep", "frigid_core", "vague_drain",
                "blood_loss", "eruptive_core", "chronomancy", "break"]
STAT_KEYS = ["atk", "hp", "defense", "mc", "pct_def_ignore", "flat_def_ignore", "res_pen", "damage_mult", "cdr",
             "cdr_nonbasic", "stamina_cost_mult", "speed_mult", "heal_mult", "res_debuff", "stamina"]
MAGICS = ["Agenet", "Sylva", "Aqua", "Ignis", "Petra", "Gale", "Amgar", "Glacia", "Sable",
          "Fulgur", "Cruor", "Ether", "TimeFlow", "Entropy", "Stardust", "Neutral"]
DEFAULT_TO = {"buff": "self", "debuff": "enemy", "slow": "enemy", "stun": "enemy", "dot": "enemy",
              "heal": "self", "shield": "self", "true_damage": "enemy", "cleanse": "self",
              "wet": "enemy", "lock_branch": "enemy"}


# --------------------------------------------------------------------------- config
def load_cfg(cfg_dir=None):
    cfg_dir = cfg_dir or os.path.join(HERE, "config")
    cfg = {}
    for n in ("rules", "skills", "relics", "builds", "scenarios"):
        with open(os.path.join(cfg_dir, n + ".json"), encoding="utf-8") as f:
            cfg[n] = json.load(f)
    return cfg


def parse_val(s):
    try:
        return json.loads(s)
    except Exception:
        return s


def set_path(cfg, path, value):
    """Đặt giá trị theo đường dẫn chấm, vd rules.passives.molten_core.flat_ignore"""
    keys = path.split(".")
    cur = cfg
    for k in keys[:-1]:
        if not isinstance(cur, dict) or k not in cur:
            raise KeyError("Đường dẫn sai tại '%s' (trong '%s')" % (k, path))
        cur = cur[k]
    last = keys[-1]
    if not isinstance(cur, dict):
        raise KeyError("Không thể đặt giá trị tại '%s'" % path)
    if last not in cur:
        print("  [cảnh báo] khóa mới '%s' được tạo (kiểm tra lại chính tả nếu bạn không định tạo mới)" % path)
    cur[last] = value


def get_path(cfg, path):
    cur = cfg
    for k in path.split("."):
        cur = cur[k]
    return cur


def apply_overrides(cfg, sets):
    for item in sets or []:
        if "=" not in item:
            raise ValueError("--set cần dạng đường.dẫn=giá_trị, nhận được: " + item)
        p, v = item.split("=", 1)
        set_path(cfg, p.strip(), parse_val(v.strip()))
    return cfg


# --------------------------------------------------------------------------- entity
class Ent:
    def __init__(self, sim, name, team, kind="player"):
        self.sim, self.name, self.team, self.kind = sim, name, team, kind
        self.magic = None
        self.bid = None
        self.label = name
        self.base, self.mods = {}, []
        self.res, self.res_pen = {}, {}
        self.carried = set()
        self.passives = set()
        self.relic_ids = []
        self.skills, self.priority, self.triggers = {}, [], []
        self.hp = self.maxhp = 1.0
        self.shield = []
        self.alive = True
        self.death_t = None
        self.gcd = 0.0
        self.stam, self.stam_t = 180.0, 99.0
        self.guard_lock = 0.0
        self.guard_q = None
        self.bl = {"stacks": [], "last": -9.0, "src": None}
        self.fc = {"exp": [], "freezing": False, "last": {}, "decay_t": 0.0, "src": None, "frozen_once": False}
        self.frozen_until = self.frozen_block = self.stun_until = -1.0
        self.wet_until = -1.0
        self.in_exo = False
        self.vg = {"exp": [], "last": -9.0, "src": None}
        self.drained_until = -1.0
        self.screep = {"exp": [], "last": -9.0, "src": None}
        self.slows, self.dots, self.guard_res = [], [], []
        self.lock_b_until = -1.0
        self.iframe_until = -1.0
        self.behavior = None
        self.dodge_lock = 0.0
        self.parry_lock = 0.0
        self.rev_ready = 0.0
        self.sturd_until = self.buried_until = -1.0
        self.break_last = -99.0
        self.target = None
        self.trig_last = {}

    # ---- chỉ số -------------------------------------------------------------
    def add_mod(self, stat, mode, value, group="default", until=None, name=None,
                max_stacks=None, debuff=False):
        if name:
            same = [m for m in self.mods if m.get("name") == name]
            if same and max_stacks is not None and len(same) >= max_stacks:
                for m in same:
                    m["until"] = until
                return
            for m in same:
                m["until"] = until
        self.mods.append({"stat": stat, "mode": mode, "value": value, "group": group,
                          "until": until, "name": name, "debuff": debuff})

    def stat(self, name):
        t = self.sim.t
        v = self.base.get(name, 1.0 if name == "damage_mult" else 0.0)
        groups = {}
        for m in self.mods:
            if m["stat"] != name or (m["until"] is not None and m["until"] <= t):
                continue
            if m["mode"] == "add":
                v += m["value"]
            else:
                groups[m["group"]] = groups.get(m["group"], 0.0) + m["value"]
        for g in groups.values():
            v *= (1.0 + g)
        cap = self.sim.caps.get(name)
        if cap is not None:
            v = min(v, cap)
        if name in ("defense", "atk", "hp", "mc", "flat_def_ignore", "pct_def_ignore", "cdr", "cdr_nonbasic"):
            v = max(0.0, v)
        return v

    def mcf(self, key):
        """Hệ số MagicCapacity áp cho passive 'key'."""
        p = self.sim.P.get(key, {})
        return (1.0 + self.stat("mc")) if p.get("mc_scales", True) else 1.0

    def res_for(self, magic, t):
        r = self.res.get(magic, self.res.get("*", 0.0))
        gs = [g for g in self.guard_res if g[0] == magic and g[2] > t]
        if gs:
            r += sum(g[1] for g in gs) if self.sim.R["stamina"]["block_res_stacks"] else max(g[1] for g in gs)
        return r

    def has(self, key):
        """Có nội tại 'key' không (từ magic hoặc relic)."""
        return key in self.passives

    # ---- trạng thái ---------------------------------------------------------
    def frozen(self):
        return self.sim.t < self.frozen_until

    def wet(self):
        return self.sim.t < self.wet_until

    def drained(self):
        return self.sim.t < self.drained_until

    def can_act(self):
        t = self.sim.t
        return self.alive and t >= self.stun_until and t >= self.frozen_until

    def slow_total(self):
        t = self.sim.t
        P = self.sim.P
        vals = []
        sc = self.screep["exp"]
        if sc:
            src = self.screep["src"]
            k = src.mcf("shadow_screep") if src else 1.0
            vals.append(len(sc) * P["shadow_screep"]["slow_per_stack"] * k)
        if self.fc["freezing"] and self.fc["exp"] and not self.in_exo:
            src = self.fc["src"]
            k = src.mcf("frigid_core") if src else 1.0
            vals.append(len(self.fc["exp"]) * P["frigid_core"]["slow_per_stack"] * k)
        vals += [s["v"] for s in self.slows if s["until"] > t]
        if not vals:
            return 0.0
        if self.sim.S("slow_stacking") == "additive":
            tot = sum(vals)
        else:
            rem = 1.0
            for v in vals:
                rem *= (1.0 - min(v, 1.0))
            tot = 1.0 - rem
        return max(0.0, min(tot, self.sim.S("max_slow")))


# --------------------------------------------------------------------------- simulation
class Sim:
    def __init__(self, cfg, team_a, team_b, seed=None, infinite=False, T=120.0, settings=None,
                 log=False, sample_every=None, scenario=None):
        self.cfg = cfg
        self.scenario = scenario or cfg.get("active_scenario")
        self.R = cfg["rules"]
        self.P = self.R["passives"]
        self.caps = self.R["stats_caps"]
        self.rng = random.Random(seed)
        self.dt = self.R["combat"]["dt"]
        self.T = T
        self.t = 0.0
        self.infinite = infinite
        self.settings = dict(cfg["scenarios"].get("settings", {}))
        if settings:
            self.settings.update(settings)
        self.ents = []
        self.events = []
        self._seq = 0
        self.m = defaultdict(lambda: defaultdict(float))       # metrics theo tên
        self.sk_dmg = defaultdict(float)
        self.sk_cast = defaultdict(int)
        self.up = defaultdict(lambda: defaultdict(float))      # uptime
        self.blocked_buffs = defaultdict(int)
        self.t_end = None
        self.log_on, self.logs = log, []
        self.sample_every, self.samples, self._next_sample = sample_every, [], 0.0
        self._flags = defaultdict(dict)
        names = defaultdict(int)
        for team, lst in (("A", team_a), ("B", team_b)):
            for spec in lst:
                e = self._make(spec, team)
                names[e.name] += 1
                if names[e.name] > 1:
                    e.name = "%s#%d" % (e.name, names[e.name])
                self.ents.append(e)
        self._post_setup()

    def S(self, key):
        return self.R["switches"][key]["value"]

    # ---- nhật ký / lấy mẫu (không dùng random nên không làm đổi kết quả) ----
    def L(self, text):
        if self.log_on:
            self.logs.append((self.t, text))

    def _flag_log(self, e, key, state, on, off):
        prev = self._flags[e.name].get(key, False)
        if state != prev:
            self._flags[e.name][key] = state
            self.L("%s: %s" % (e.name, on if state else off))

    def _stack_log(self, e, key, n, mx):
        prev = self._flags[e.name].get("n_" + key, 0)
        if n != prev:
            if n == 0:
                self.L("%s: %s hết" % (e.name, key))
            elif n >= mx and prev < mx:
                self.L("%s: %s đủ %d/%d tầng" % (e.name, key, n, mx))
            elif n == 1 and prev == 0:
                self.L("%s: %s bắt đầu (1 tầng)" % (e.name, key))
            self._flags[e.name]["n_" + key] = n

    def _take_sample(self):
        snap = {}
        for e in self.ents:
            m = self.m[e.name]
            dealt = m["direct"] + m["dot"] + m["true"] + m["bonus"]
            frac = 0.0 if not e.alive else (None if e.hp > 1e11 else max(0.0, e.hp / e.maxhp))
            snap[e.name] = (frac, dealt)
        self.samples.append((self._next_sample, snap))
        self._next_sample += self.sample_every

    # ---- dựng thực thể ----
    def _make(self, spec, team):
        if spec.startswith("dummy:"):
            return self._make_dummy(spec[6:], team)
        return self._make_player(spec, team)

    def _make_dummy(self, did, team):
        d = self.cfg["scenarios"]["dummies"][did]
        e = Ent(self, "dummy:" + did, team, d.get("kind", "player"))
        e.label = did
        e.magic = d.get("magic")
        e.base = dict(self.R["stats_base"])
        e.base["defense"] = d.get("defense", 300)
        e.base["hp"] = d.get("hp", 2000)
        for k in ("atk", "mc", "pct_def_ignore", "flat_def_ignore", "damage_mult", "cdr", "stamina"):
            if k in d:
                e.base[k] = d[k]
        e.res = dict(d.get("res", {}))
        e.in_exo = bool(d.get("in_exothermal", False))
        if d.get("wet"):
            e.wet_until = INF
        e.maxhp = e.stat("hp")
        e.hp = 1e12 if self.infinite else e.maxhp
        e.guard_q = d.get("guard_q", 0.0)
        e.stam = 180.0
        return e

    def _make_player(self, bid, team):
        b = self.cfg["builds"][bid]
        R, P = self.R, self.P
        e = Ent(self, bid, team, "player")
        e.bid, e.label = bid, b.get("label", bid)
        e.base = dict(R["stats_base"])
        e.base.update(b.get("stats", {}))
        e.res = dict(b.get("res", {}))
        e.target = b.get("target")
        ps = R["passive_system"]
        rel_ids = b.get("relics")
        if rel_ids is None:
            rel_ids = [b["relic"]] if b.get("relic") else []
        e.relic_ids = list(rel_ids)
        granted = set()
        for rid in rel_ids:
            rel = self.cfg["relics"][rid]
            for m in rel.get("mods", []):
                e.add_mod(m["stat"], m.get("mode", "add"), m["value"], m.get("group", "relic"))
            e.triggers += copy.deepcopy(rel.get("triggers", []))
            granted.update(rel.get("grants", []))
        a, bb = b["branch_a"], b["branch_b"]
        e.carried = {a["magic"], bb["magic"]}
        e.passives = set(granted)
        if ps.get("magic_grants_passive", True):
            for m in e.carried:
                e.passives.update(ps["magic_passive_map"].get(m, []))
        e.passives -= set(b.get("passives_off", []))
        sids = ([("basic", b["basic"])] if b.get("basic") else []) + [("a", s) for s in a["skills"]] + [("b", s) for s in bb["skills"]]
        for br, sid in sids:
            sk = self.cfg["skills"][sid]
            ch = int(sk.get("charges", 1))
            e.skills[sid] = {"sk": sk, "branch": br, "ch": ch, "max": ch, "rech": 0.0}
        # --- passive tĩnh (stat) ---
        mc = e.stat("mc")
        def f(key):
            return (1 + mc) if P[key].get("mc_scales", True) else 1.0
        if e.has("molten_core"):
            p, k = P["molten_core"], f("molten_core")
            e.add_mod("defense", "pct", p["def_pct"] * k, "passive")
            e.add_mod("flat_def_ignore", "add", p["flat_ignore"] * k)
            e.add_mod("pct_def_ignore", "add", p["pct_ignore"] * k)
        if e.has("zephyr_core"):
            p, k = P["zephyr_core"], f("zephyr_core")
            e.add_mod("stamina_cost_mult", "add", -p["stamina_cost_reduction"] * k)
            e.add_mod("speed_mult", "add", p["speed_bonus"] * k)
        if e.has("chronomancy"):
            p, k = P["chronomancy"], f("chronomancy")
            stat = "cdr" if p["scope"] == "all" else "cdr_nonbasic"
            e.add_mod(stat, "add", p["cd_reduction"] * k)
        if a["magic"] == bb["magic"]:
            p, k = P["pure_type"], f("pure_type")
            e.add_mod("damage_mult", "pct", p["damage_bonus"] * k, "pure_type")
            e.res_pen[a["magic"]] = p["res_pen"] * k
        e.maxhp = e.stat("hp")
        e.hp = 1e12 if self.infinite else e.maxhp
        e.stam = e.stat("stamina")
        e.guard_q = b.get("guard_q", None)
        pr = b.get("priority")
        if not pr:
            nb = [s for br, s in sids if br != "basic"]
            nb.sort(key=lambda s: -self.cfg["skills"][s].get("base", 0))
            pr = nb + ([b["basic"]] if b.get("basic") else [])
        e.priority = pr
        if self.scenario and isinstance(self.scenario, dict):
            team_key = "team_a" if team == "A" else "team_b"
            if team_key in self.scenario:
                e.behavior = copy.deepcopy(self.scenario[team_key])
        return e

    def _post_setup(self):
        # Genesis: có vật thể Petra trong trận -> thêm charge cho skill Kim/Mộc có charge
        if self.settings.get("petra_object_present"):
            g = self.P["genesis"]["extra_charges"]
            for e in self.ents:
                if e.kind != "player":
                    continue
                for st in e.skills.values():
                    if st["max"] > 1 and st["sk"]["magic"] in ("Agenet", "Sylva"):
                        st["max"] += g
                        st["ch"] += g if st["sk"]["magic"] == "Sylva" else 0

    # ---- tính damage thuần (không đổi trạng thái) ----
    def compute(self, src, tgt, base, magic, atk=None, bypass_def=False, final_raw=False, is_bl=False):
        t, P, caps = self.t, self.P, self.caps
        sturd = P["sturd"]
        kim_obj = tgt.kind == "object" and tgt.magic == "Agenet"
        df_cfg = self.R.get("damage_formula", {})

        if final_raw:
            raw = base
        else:
            a = atk if atk is not None else src.stat("atk")
            dmg_mult = src.stat("damage_mult")
            raw_fn = getattr(self, "_cached_raw_fn", None)
            if raw_fn is None:
                raw_expr = df_cfg.get("raw_expr")
                if raw_expr and str(raw_expr).strip():
                    try:
                        code = compile(str(raw_expr).strip(), "<raw_expr>", "eval")
                        raw_fn = lambda a_val, b_val, m_val: eval(code, {"__builtins__": None, "max": max, "min": min}, {"atk": a_val, "base": b_val, "damage_mult": m_val})
                    except Exception:
                        raw_fn = lambda a_val, b_val, m_val: (a_val + b_val) * m_val
                else:
                    raw_fn = lambda a_val, b_val, m_val: (a_val + b_val) * m_val
                self._cached_raw_fn = raw_fn
            try:
                raw = float(self._cached_raw_fn(a, base, dmg_mult))
            except Exception:
                raw = (a + base) * dmg_mult

        if kim_obj and magic == "Ignis" and t < tgt.sturd_until:
            raw *= 1 + sturd["ignis_bonus"]

        if bypass_def:
            red = 0.0
        else:
            pct = min(src.stat("pct_def_ignore"), caps["pct_def_ignore"])
            flat = min(src.stat("flat_def_ignore"), caps["flat_def_ignore"])
            dfn = tgt.stat("defense")
            if kim_obj and t < tgt.sturd_until:
                dfn *= 1 - sturd["def_debuff"]
            if tgt.kind == "object" and tgt.magic == "Ignis" and t < tgt.buried_until:
                dfn *= 1 - P["wet"]["buried_def_debuff"]
            d = max(0.0, dfn * (1 - pct) - flat)

            def_k = float(df_cfg.get("def_k", 100.0))
            def_fn = getattr(self, "_cached_def_fn", None)
            if def_fn is None:
                def_expr = df_cfg.get("def_expr")
                if def_expr and str(def_expr).strip():
                    try:
                        code = compile(str(def_expr).strip(), "<def_expr>", "eval")
                        def_fn = lambda d_val, k_val: eval(code, {"__builtins__": None, "max": max, "min": min}, {"d": d_val, "def_k": k_val})
                    except Exception:
                        def_fn = lambda d_val, k_val: d_val / (k_val + d_val)
                else:
                    def_fn = lambda d_val, k_val: d_val / (k_val + d_val)
                self._cached_def_fn = def_fn
            try:
                red = float(self._cached_def_fn(d, def_k))
            except Exception:
                red = d / (def_k + d)
            red = max(0.0, min(1.0, red))

        if kim_obj and magic in sturd["immune_magics"]:
            mult = 1 - sturd["immune_res"]
        elif is_bl and not P["blood_loss"]["res_applies"]:
            mult = 1.0
        else:
            r = tgt.res_for(magic, t)
            pen = min(1.0, src.res_pen.get(magic, 0.0) + src.stat("res_pen"))
            r = r * (1 - pen) - tgt.stat("res_debuff")

            res_fn = getattr(self, "_cached_res_fn", None)
            if res_fn is None:
                res_expr = df_cfg.get("res_expr")
                if res_expr and str(res_expr).strip():
                    try:
                        code = compile(str(res_expr).strip(), "<res_expr>", "eval")
                        res_fn = lambda r_val, cap_val: eval(code, {"__builtins__": None, "max": max, "min": min}, {"r": r_val, "caps_res": cap_val})
                    except Exception:
                        res_fn = lambda r_val, cap_val: 1 - r_val / 2 if r_val < 0 else 1 - min(r_val, cap_val)
                else:
                    res_fn = lambda r_val, cap_val: 1 - r_val / 2 if r_val < 0 else 1 - min(r_val, cap_val)
                self._cached_res_fn = res_fn
            try:
                mult = float(self._cached_res_fn(r, caps["res"]))
            except Exception:
                mult = 1 - r / 2 if r < 0 else 1 - min(r, caps["res"])

        return raw * (1 - red) * mult

    # ---- gây damage ----
    def hit(self, src, tgt, base, magic, atk=None, dot=False, true=False, bypass_def=False,
            final_raw=False, cat=None, trigger=True, is_bl=False, sid=None):
        t = self.t
        if not tgt.alive or tgt.iframe_until > t:
            return 0.0
        dealt = base if true else self.compute(src, tgt, base, magic, atk, bypass_def, final_raw, is_bl)
        rem = dealt
        if not true:
            for sh in tgt.shield:
                if sh[1] > t and sh[0] > 0 and rem > 0:
                    take = min(sh[0], rem)
                    sh[0] -= take
                    rem -= take
        tgt.hp -= rem
        c = cat or ("true" if true else "dot" if dot else "direct")
        self.m[src.name][c] += dealt
        self.m[tgt.name]["taken"] += dealt
        if sid:
            self.sk_dmg[(src.name, sid)] += dealt
        if self.log_on and not dot:
            hp_txt = "" if tgt.hp > 1e11 else "  [HP %.0f/%.0f]" % (max(0.0, tgt.hp), tgt.maxhp)
            ab = "  (khiên hấp thụ %.0f)" % (dealt - rem) if (not true and dealt - rem > 0.5) else ""
            self.L("%s → %s: %s (%s) %.0f dmg%s%s" % (src.name, tgt.name, sid or cat or ("true" if true else "dmg"), magic, dealt, ab, hp_txt))
        if trigger and not dot and (dealt > 0 or self.S("trigger_on_zero_damage")):
            self._on_hit(src, tgt, magic, dealt)
        self._check_death(tgt)
        return dealt

    def raw_extra(self, src, tgt, amount, cat, true=False):
        """Sát thương thêm (Break/Chain): đã tính xong, chỉ đi qua Shield (trừ true) và HP."""
        if not tgt.alive or tgt.iframe_until > self.t or amount <= 0:
            return
        rem = amount
        if not true:
            for sh in tgt.shield:
                if sh[1] > self.t and sh[0] > 0 and rem > 0:
                    take = min(sh[0], rem)
                    sh[0] -= take
                    rem -= take
        tgt.hp -= rem
        self.m[src.name][cat] += amount
        self.m[tgt.name]["taken"] += amount
        if self.log_on:
            self.L("%s → %s: %s %.0f%s" % (src.name, tgt.name, "TRUE DAMAGE (bỏ qua Def/RES/khiên)" if true else "sát thương thêm", amount,
                                           "" if tgt.hp > 1e11 else "  [HP %.0f/%.0f]" % (max(0.0, tgt.hp), tgt.maxhp)))
        self._check_death(tgt)

    def heal(self, e, amount, quiet=False):
        if amount <= 0 or not e.alive:
            return
        amount *= e.stat("heal_mult")
        if e.hp < e.maxhp:
            e.hp = min(e.maxhp, e.hp + amount)
        self.m[e.name]["heal"] += amount
        if self.log_on and not quiet and amount >= 0.01 * e.maxhp:
            self.L("%s: hồi %.0f HP" % (e.name, amount))
        mode = self.P["blood_loss"]["heal_clears"]
        if e.bl["stacks"]:
            if mode == "all":
                e.bl["stacks"] = []
            elif isinstance(mode, int) and mode > 0:
                del e.bl["stacks"][:mode]

    def cleanse(self, e, undispellable=False):
        e.mods = [m for m in e.mods if not m["debuff"]]
        e.slows, e.dots = [], []
        e.screep["exp"] = []
        e.fc["exp"], e.fc["freezing"] = [], False
        e.bl["stacks"] = []
        e.frozen_until = e.stun_until = -1.0
        if undispellable:
            e.vg["exp"] = []
            e.drained_until = -1.0

    def _check_death(self, e):
        if e.hp > 0 or not e.alive:
            return
        P = self.P["eruptive_core"]
        if (e.has("eruptive_core") or (e.kind == "object" and e.magic == "Entropy")) and self.t >= e.rev_ready:
            k = (1 + e.stat("mc")) if P.get("mc_scales", True) else 1.0
            e.hp = 0.0
            self.heal(e, P["heal_pct"] * k * e.maxhp)
            self.cleanse(e, undispellable=self.S("eruptive_clears_undispellable"))
            e.iframe_until = self.t + P["iframe"]
            e.rev_ready = self.t + P["cooldown"]
            self.m[e.name]["revives"] += 1
            self.L("%s: HỒI SINH (Eruptive Core) còn %.0f HP, bất tử %.2fs" % (e.name, e.hp, P["iframe"]))
            return
        e.alive = False
        e.death_t = self.t
        self.L("%s: CHẾT" % e.name)

    # ---- phản ứng khi nhận sát thương ----
    def _enemies_of(self, e):
        return [x for x in self.ents if x.team != e.team]

    def _on_hit(self, src, tgt, magic, dealt):
        t, P = self.t, self.P
        # Blood Loss
        if tgt.kind == "player" and magic != "Cruor":
            cr = None
            for x in self._enemies_of(tgt):
                if x.alive and x.has("blood_loss") and (self.S("blood_loss_any_source") or x is src):
                    cr = x
                    break
            p = P["blood_loss"]
            if cr and t - tgt.bl["last"] >= p["icd"] - 1e-9 and len(tgt.bl["stacks"]) < p["max_stacks"]:
                tgt.bl["stacks"].append(t + p["duration"] * cr.mcf("blood_loss"))
                tgt.bl["last"], tgt.bl["src"] = t, cr
        # Glacia -> Frigid Core
        if magic == "Glacia" and src.has("frigid_core"):
            self._frigid_add(src, tgt)
        # Sable -> Shadow Screep
        if magic == "Sable" and src.has("shadow_screep"):
            p, sc = P["shadow_screep"], tgt.screep
            if t - sc["last"] >= p["icd"] - 1e-9:
                sc["last"], sc["src"] = t, src
                dur = p["stack_duration"] * src.mcf("shadow_screep") if p["stack_duration"] else INF
                sc["exp"].append(t + dur)
                if len(sc["exp"]) > p["max_stacks"]:
                    sc["exp"].pop(0)
        # Ether -> Vague ; kích hoạt Drained bằng magic khác
        if magic == "Ether" and src.has("vague_drain"):
            p, vg = P["vague_drain"], tgt.vg
            if t - vg["last"] >= p["icd"] - 1e-9 and len(vg["exp"]) < p["max_stacks"]:
                vg["last"], vg["src"] = t, src
                vg["exp"].append(t + p["stack_duration"] if p["stack_duration"] else INF)
        elif tgt.vg["exp"] and tgt.vg["src"] is src:
            p = P["vague_drain"]
            k = src.mcf("vague_drain")
            dur = len(tgt.vg["exp"]) * p["drained_per_stack"] * k
            cap = p["drained_cap"] * (k if p.get("mc_scales_cap") else 1.0)
            tgt.drained_until = max(tgt.drained_until, t + min(dur, cap))
            tgt.vg["exp"] = []
        # Aqua -> Wet (+ Buried lên Ignis)
        if magic == "Aqua":
            w = P["wet"]
            if (tgt.kind == "object" and tgt.magic in w["objects"]) or \
               (tgt.kind == "player" and self.S("wet_on_players")):
                tgt.wet_until = t + w["duration"] * (src.mcf("wet") if "mc_scales" in w else 1.0)
                fc = tgt.fc
                if fc["freezing"] and not tgt.in_exo:
                    if self.S("frozen_retrigger_on_wet") or not fc["frozen_once"]:
                        self._freeze(tgt, fc["src"] or src)
            if tgt.kind == "object" and tgt.magic == "Ignis":
                tgt.buried_until = t + w["buried_duration"]
        # Ignis -> Sturd (Kim object)
        if magic == "Ignis" and tgt.kind == "object" and tgt.magic == "Agenet":
            tgt.sturd_until = t + P["sturd"]["duration"]
        # Fulgur Chain
        if magic == "Fulgur" and src.has("fulgur_chain") and tgt.kind == "object":
            p = P["fulgur_chain"]
            if tgt.magic in p["trigger_magics"] or tgt.wet():
                bonus = p["bonus_pct"] * src.mcf("fulgur_chain") * dealt
                self.raw_extra(src, tgt, bonus, "bonus")
                n = 0
                for x in self._enemies_of(src):
                    if n >= p["max_secondary"]:
                        break
                    if x is tgt or not x.alive:
                        continue
                    if x.kind == "object" or self.S("chain_hits_players"):
                        self.raw_extra(src, x, bonus, "bonus")
                        n += 1
                extra_n = min(int(self.settings.get("chain_extra_targets", 0)), p["max_secondary"] - n)
                if extra_n > 0:
                    self.m[src.name]["bonus"] += bonus * extra_n
                    self.m[src.name]["bonus_virtual"] += bonus * extra_n
        # Break (Kim) lên mục tiêu Frozen
        if src.has("break") and tgt.frozen():
            p = P["break"]
            self.raw_extra(src, tgt, p["bonus_pct"] * dealt, "bonus")
            icd = max(p["icd"], P["reaction"]["icd"]) if self.S("break_uses_reaction_icd") else p["icd"]
            if t - tgt.break_last >= icd - 1e-9:
                tgt.break_last = t
                self.raw_extra(src, tgt, p["true_pct_max_hp"] * tgt.maxhp, "true", true=True)
        # relic on_hit
        for i, tr in enumerate(src.triggers):
            if tr["type"] == "on_hit" and t - src.trig_last.get(i, -99) >= tr.get("icd", 0) - 1e-9:
                src.trig_last[i] = t
                for eff in tr["effects"]:
                    self.apply_effect(eff, src, tgt)

    def _frigid_add(self, src, tgt):
        p, fc, t = self.P["frigid_core"], tgt.fc, self.t
        if tgt.in_exo or (tgt.kind == "object" and tgt.magic == "Ignis"):
            return
        key = src.name if self.S("frigid_icd_per_source") else "*"
        if t - fc["last"].get(key, -99) < p["icd"] - 1e-9:
            return
        fc["last"][key] = t
        fc["src"] = src
        if len(fc["exp"]) < p["max_stacks"]:
            fc["exp"].append(t + p["stack_duration"] if p["stack_duration"] else INF)

    def _freeze(self, tgt, src):
        p, t = self.P["frigid_core"], self.t
        if tgt.in_exo or t < tgt.frozen_block:
            return
        dur = p["frozen_duration"] * src.mcf("frigid_core")
        tgt.frozen_until = max(tgt.frozen_until, t + dur)
        tgt.fc["frozen_once"] = True
        tgt.frozen_block = (t + dur + p["frozen_immunity"]) if p["frozen_immunity"] > 0 else -1.0

    # ---- hiệu ứng tổng quát (skill/relic) ----
    def apply_effect(self, eff, src, enemy):
        t = self.t
        typ = eff["type"]
        to = eff.get("to", DEFAULT_TO.get(typ, "enemy"))
        tgt = src if to == "self" else enemy
        if tgt is None or not tgt.alive:
            return
        use_mc = eff.get("mc", self.R["mc"]["skill_effects_scale"])
        k = (1 + src.stat("mc")) if use_mc else 1.0
        dur = eff.get("duration", 0.0) * k
        if self.log_on:
            self.L("%s → %s: hiệu ứng %s%s" % (src.name, tgt.name, typ, (" " + str(eff.get("stat"))) if eff.get("stat") else ""))
        if typ in ("buff", "debuff"):
            if typ == "buff" and tgt.drained():
                self.blocked_buffs[tgt.name] += 1
                self.L("   → buff bị Drained CHẶN")
                return
            tgt.add_mod(eff["stat"], eff.get("mode", "pct"), eff["value"] * k, eff.get("group", "skill"),
                        until=t + dur, name=eff.get("name"), max_stacks=eff.get("max_stacks"),
                        debuff=(typ == "debuff"))
        elif typ == "slow":
            name, mx = eff.get("name"), eff.get("max_stacks", 1)
            same = [s for s in tgt.slows if name and s["name"] == name and s["until"] > t]
            if same and len(same) >= mx:
                for s in same:
                    s["until"] = t + dur
            else:
                for s in same:
                    s["until"] = t + dur
                tgt.slows.append({"v": eff["value"] * k, "until": t + dur, "name": name})
        elif typ == "stun":
            tgt.stun_until = max(tgt.stun_until, t + dur)
        elif typ == "dot":
            tgt.dots.append({"until": t + dur, "next": t, "tick": eff.get("tick", 0.5),
                             "base": eff.get("dps_base", 0.0) * k, "coef": eff.get("atk_coef", 0.0),
                             "magic": eff.get("magic", "Neutral"), "src": src, "atk": src.stat("atk")})
        elif typ == "heal":
            self.heal(tgt, (eff.get("amount", 0.0) + eff.get("pct_max", 0.0) * tgt.maxhp) * k)
        elif typ == "shield":
            tgt.shield.append([(eff.get("amount", 0.0) + eff.get("pct_max", 0.0) * tgt.maxhp) * k, t + dur])
        elif typ == "true_damage":
            amt = eff.get("amount", 0.0) + eff.get("pct_max", 0.0) * tgt.maxhp
            self.hit(src, tgt, amt * k, "True", true=True, trigger=False)
        elif typ == "cleanse":
            self.cleanse(tgt)
        elif typ == "wet":
            tgt.wet_until = t + dur
        elif typ == "lock_branch":
            tgt.lock_b_until = max(tgt.lock_b_until, t + dur)

    # ---- chiến đấu ----
    def pick_target(self, e):
        en = [x for x in self.ents if x.team != e.team and x.alive]
        if not en:
            return None
        if e.target:
            for x in en:
                if x.name == e.target:
                    return x
        for kind in self.settings.get("target_order", ["player", "object"]):
            for x in en:
                if x.kind == kind:
                    return x
        return en[0]

    def cd_eff(self, e, st):
        cdr = e.stat("cdr") + (e.stat("cdr_nonbasic") if st["branch"] != "basic" else 0.0)
        return st["sk"].get("cd", 1.0) * (1.0 - min(cdr, self.caps.get("cdr") or 1.0))

    def schedule(self, delay, fn):
        self._seq += 1
        heapq.heappush(self.events, (self.t + delay, self._seq, fn))

    def act(self, e):
        if e.kind != "player" or not e.can_act() or e.gcd > self.t + 1e-9 or e.guard_lock > self.t + 1e-9:
            return
        # Kỷ luật quản lý thể lực từ kịch bản hành vi người chơi
        if hasattr(e, "behavior") and e.behavior:
            mv = e.behavior.get("movement", {})
            disc = mv.get("stamina_discipline", 0.5)
            # Người có kỷ luật cao giữ thể lực dự trữ để luôn sẵn sàng né/parry thay vì xả cạn kiệt
            if disc >= 0.65 and e.stam < 35.0 and e.hp > e.maxhp * 0.25:
                return
        tgt = self.pick_target(e)
        if tgt is None:
            return
        for sid in e.priority:
            st = e.skills[sid]
            if st["ch"] < 1:
                continue
            if st["branch"] == "b" and self.t < e.lock_b_until:
                continue
            self.cast(e, sid, st, tgt)
            return

    def cast(self, e, sid, st, tgt):
        t, R = self.t, self.R
        sk = st["sk"]
        st["ch"] -= 1
        if st["rech"] <= 1e-9:
            st["rech"] = self.cd_eff(e, st)
        e.gcd = t + sk.get("cast_time", R["combat"]["gcd"])
        self.sk_cast[(e.name, sid)] += 1
        self.L("%s dùng %s → %s" % (e.name, sid, tgt.name))
        atk = e.stat("atk")                                  # snapshot ATK lúc cast
        for tr_i, tr in enumerate(e.triggers):
            if tr["type"] == "on_cast" and t - e.trig_last.get(tr_i, -99) >= tr.get("icd", 0) - 1e-9:
                e.trig_last[tr_i] = t
                for eff in tr["effects"]:
                    self.apply_effect(eff, e, tgt)
        for eff in sk.get("effects", []):                    # hiệu ứng 'on cast' (to=self)
            if eff.get("to", DEFAULT_TO.get(eff["type"], "enemy")) == "self":
                self.apply_effect(eff, e, tgt)

        # 1. Kiểm tra iframe lướt né (Dodge)
        if tgt.iframe_until > t:
            self.L("   → %s đang lướt né trong i-frames, đòn đánh vô hiệu hóa" % tgt.name)
            return

        nh = int(sk.get("hits", 1))
        if nh <= 0:
            return
        p_hit = sk.get("hit_chance")
        p_hit = R["combat"]["p_hit"] if p_hit is None else p_hit
        if tgt.frozen() or t < tgt.stun_until:
            p_hit = 1.0
        else:
            p_hit = min(1.0, p_hit + tgt.slow_total() * R["combat"]["slow_hit_bonus"])
            # Ảnh hưởng giữ cự ly / kiting từ người phòng thủ
            if hasattr(tgt, "behavior") and tgt.behavior:
                sp = tgt.behavior.get("movement", {}).get("spacing", 0.0)
                p_hit = max(0.20, p_hit - sp * 0.15)
        if self.rng.random() > p_hit:
            self.L("   → trượt (do cự ly / độ chính xác)")
            return

        # 2. Cơ chế phòng thủ người chơi (Parry / Dodge / Guard)
        if tgt.kind == "player" and tgt.can_act():
            if hasattr(tgt, "behavior") and tgt.behavior:
                beh = tgt.behavior
                psy = beh.get("psychology", {})
                p_thresh = psy.get("panic_hp_threshold", 0.30)
                comp = psy.get("composure", 0.60)
                under_pressure = (tgt.hp <= tgt.maxhp * p_thresh)

                if under_pressure:
                    if comp < 0.50:
                        self.m[tgt.name]["panics"] += 1
                        comp_mult = max(0.40, 0.50 + comp)
                        react_penalty = (0.50 - comp) * 0.35
                    elif comp >= 0.80:
                        self.m[tgt.name]["clutches"] += 1
                        comp_mult = min(1.25, 1.0 + (comp - 0.80) * 0.60)
                        react_penalty = -0.04
                    else:
                        comp_mult = 1.0
                        react_penalty = 0.0
                else:
                    comp_mult = 1.0
                    react_penalty = 0.0

                # Kiểm tra phản xạ nhận diện đòn đánh
                react_time = max(0.06, beh.get("reaction_time", 0.22) + react_penalty)
                cast_t = sk.get("cast_time", R["combat"]["gcd"])
                react_window = max(0.12, cast_t + 0.12)
                prob_react = min(1.0, max(0.15, react_window / (react_time * 2.0)))
                can_react = (self.rng.random() < prob_react)

                if can_react:
                    # A. PARRY (Đỡ gạt phản công)
                    parry_cfg = beh.get("parry", {})
                    p_cost = parry_cfg.get("stamina_cost", 10.0) * tgt.stat("stamina_cost_mult")
                    p_rate = parry_cfg.get("rate", 0.20) * comp_mult
                    if tgt.stam >= p_cost and t >= getattr(tgt, "parry_lock", 0.0) and self.rng.random() < p_rate:
                        tgt.stam -= p_cost
                        tgt.stam_t = 0.0
                        tgt.parry_lock = t + 0.8
                        c_stun = parry_cfg.get("counter_stun", 0.6)
                        e.stun_until = max(e.stun_until, t + c_stun)
                        self.m[tgt.name]["parries"] += 1
                        self.L("   ★ %s PARRY HOÀN HẢO! Đỡ gạt tuyệt đỉnh, %s bị choáng %.1fs!" % (tgt.name, e.name, c_stun))
                        counter_dmg = max(10.0, tgt.stat("atk") * 0.35)
                        self.hit(tgt, e, counter_dmg, "Neutral", sid="parry_counter", true=True)
                        return

                    # B. DODGE (Lướt né đòn)
                    dodge_cfg = beh.get("dodge", {})
                    d_cost = dodge_cfg.get("stamina_cost", 25.0) * tgt.stat("stamina_cost_mult")
                    d_rate = dodge_cfg.get("rate", 0.40) * comp_mult
                    if tgt.stam >= d_cost and t >= getattr(tgt, "dodge_lock", 0.0) and self.rng.random() < d_rate:
                        tgt.stam -= d_cost
                        tgt.stam_t = 0.0
                        d_cd = dodge_cfg.get("cd", 1.5)
                        tgt.dodge_lock = t + d_cd
                        iframes = dodge_cfg.get("iframes", 0.30)
                        tgt.iframe_until = t + iframes
                        self.m[tgt.name]["dodges"] += 1
                        self.L("   ◆ %s LƯỚT NÉ (DODGE) thành công! (stamina còn %.0f)" % (tgt.name, tgt.stam))
                        return

                    # C. GUARD (Block đòn thường)
                    guard_cfg = beh.get("guard", {})
                    g_cost = guard_cfg.get("stamina_cost", R["stamina"]["guard_cost"]) * tgt.stat("stamina_cost_mult")
                    g_rate = guard_cfg.get("rate", R["combat"]["guard_q"]) * comp_mult
                    if tgt.stam >= g_cost and self.rng.random() < g_rate:
                        tgt.stam -= g_cost
                        tgt.stam_t = 0.0
                        tgt.guard_lock = t + R["combat"]["guard_lock"]
                        if not tgt.drained():
                            tgt.guard_res.append((sk["magic"], R["stamina"]["block_res_bonus"],
                                                  t + R["stamina"]["block_res_duration"]))
                        else:
                            self.blocked_buffs[tgt.name] += 1
                        self.m[tgt.name]["blocks"] += 1
                        self.L("   → %s BLOCK đòn đánh (stamina còn %.0f)" % (tgt.name, tgt.stam))
                        return
                else:
                    if tgt.stam < 20.0:
                        self.L("   ! %s kiệt sức (hết stamina), không thể phòng thủ!" % tgt.name)
                    else:
                        self.L("   ! %s không kịp phản xạ đòn đánh!" % tgt.name)
            else:
                q = tgt.guard_q if tgt.guard_q is not None else R["combat"]["guard_q"]
                cost = R["stamina"]["guard_cost"] * tgt.stat("stamina_cost_mult")
                if tgt.stam >= cost and q > 0 and self.rng.random() < q:
                    tgt.stam -= cost
                    tgt.stam_t = 0.0
                    tgt.guard_lock = t + R["combat"]["guard_lock"]
                    if not tgt.drained():
                        tgt.guard_res.append((sk["magic"], R["stamina"]["block_res_bonus"],
                                              t + R["stamina"]["block_res_duration"]))
                    else:
                        self.blocked_buffs[tgt.name] += 1
                    self.m[tgt.name]["blocks"] += 1
                    self.L("   → %s BLOCK (stamina còn %.0f)" % (tgt.name, tgt.stam))
                    return
        interval = sk.get("hit_interval", 0.2)
        for i in range(nh):
            self.schedule(i * interval, lambda e=e, tgt=tgt, sk=sk, sid=sid, atk=atk, first=(i == 0):
                          self._land(e, tgt, sk, sid, atk, first))

    def _land(self, e, tgt, sk, sid, atk, first):
        if not tgt.alive:
            return
        if sk.get("base", 0) or not sk.get("true_base"):
            self.hit(e, tgt, sk.get("base", 0), sk["magic"], atk=atk, sid=sid)
        if sk.get("true_base"):
            self.hit(e, tgt, sk["true_base"], sk["magic"], true=True, sid=sid)
        if first:
            for eff in sk.get("effects", []):
                if eff.get("to", DEFAULT_TO.get(eff["type"], "enemy")) != "self":
                    self.apply_effect(eff, e, tgt)

    def tick_ent(self, e):
        t, dt, P = self.t, self.dt, self.P
        if not e.alive:
            return
        # dọn hết hạn
        e.bl["stacks"] = [x for x in e.bl["stacks"] if x > t]
        e.screep["exp"] = [x for x in e.screep["exp"] if x > t]
        e.vg["exp"] = [x for x in e.vg["exp"] if x > t]
        e.fc["exp"] = [x for x in e.fc["exp"] if x > t]
        if not e.fc["exp"]:
            e.fc["freezing"] = False
        if self.log_on:
            self._stack_log(e, "Blood Loss", len(e.bl["stacks"]), P["blood_loss"]["max_stacks"])
            self._stack_log(e, "Shadow Screep", len(e.screep["exp"]), P["shadow_screep"]["max_stacks"])
            self._stack_log(e, "Vague", len(e.vg["exp"]), P["vague_drain"]["max_stacks"])
            self._stack_log(e, "Frigid Core", len(e.fc["exp"]), P["frigid_core"]["max_stacks"])
        e.shield = [s for s in e.shield if s[1] > t and s[0] > 0]
        e.guard_res = [g for g in e.guard_res if g[2] > t]
        if len(e.mods) > 0:
            e.mods = [m for m in e.mods if m["until"] is None or m["until"] > t]
        # stamina
        e.stam_t += dt
        cap = e.base.get("stamina", 180)
        rg = self.R["stamina"]
        if e.stam_t >= rg["regen_delay"] and e.stam < cap:
            e.stam = min(cap, e.stam + rg["regen"] * dt)
        # tâm lý chiến đấu (panic / clutch)
        if hasattr(e, "behavior") and e.behavior:
            psy = e.behavior.get("psychology", {})
            p_thresh = psy.get("panic_hp_threshold", 0.30)
            comp = psy.get("composure", 0.60)
            if e.hp <= e.maxhp * p_thresh:
                if comp < 0.50:
                    self.m[e.name]["panic_t"] += dt
                elif comp >= 0.80:
                    self.m[e.name]["clutch_t"] += dt
        # nạp charge
        for st in e.skills.values():
            if st["ch"] < st["max"]:
                st["rech"] -= dt
                if st["rech"] <= 1e-9:
                    st["ch"] += 1
                    st["rech"] = self.cd_eff(e, st) if st["ch"] < st["max"] else 0.0
        # Blood Loss DoT
        n = len(e.bl["stacks"])
        if n and e.kind == "player":
            p, cr = P["blood_loss"], e.bl["src"]
            if cr is not None:
                amt = p["pct_per_stack"] * n * cr.mcf("blood_loss") * dt * e.maxhp
                dealt = self.hit(cr, e, amt, "Cruor", dot=True, bypass_def=p["bypass_def"],
                                 final_raw=True, cat="dot", trigger=False, is_bl=True)
                if dealt > 0 and cr.alive:
                    self.heal(cr, p["lifesteal"] * dealt, quiet=True)
        # Frigid Core: kích hoạt Freezing + xả tầng
        fc, p = e.fc, P["frigid_core"]
        if not fc["freezing"] and len(fc["exp"]) >= p["max_stacks"] and not e.in_exo:
            fc["freezing"], fc["decay_t"], fc["frozen_once"] = True, t, False
            if e.wet():
                self._freeze(e, fc["src"] or e)
        if fc["freezing"]:
            while t - fc["decay_t"] >= p["decay_interval"] - 1e-9 and fc["exp"]:
                fc["decay_t"] += p["decay_interval"]
                fc["exp"].pop(0)
            if not fc["exp"]:
                fc["freezing"] = False
        # DoT của skill
        keep = []
        for d in e.dots:
            if d["until"] <= t:
                continue
            if t >= d["next"]:
                d["next"] += d["tick"]
                base = (d["base"] + d["atk"] * d["coef"]) * d["tick"]
                self.hit(d["src"], e, base, d["magic"], atk=0.0, dot=True, trigger=False)
            keep.append(d)
        e.dots = keep
        # relic periodic
        for i, tr in enumerate(e.triggers):
            if tr["type"] == "periodic" and t - e.trig_last.get(i, 0.0) >= tr["every"] - 1e-9:
                e.trig_last[i] = t
                for eff in tr["effects"]:
                    self.apply_effect(eff, e, self.pick_target(e))

    def _uptime(self, e):
        if not e.alive:
            return
        dt, u = self.dt, self.up[e.name]
        if self.log_on:
            self._flag_log(e, "frozen", e.frozen(), "BỊ ĐÓNG BĂNG (Frozen)", "hết Frozen")
            self._flag_log(e, "freezing", e.fc["freezing"], "vào trạng thái Freezing", "hết Freezing")
            self._flag_log(e, "drained", e.drained(), "bị DRAINED (không nhận buff mới)", "hết Drained")
            self._flag_log(e, "wet", e.wet() and e.wet_until < 1e17, "bị Wet", "hết Wet")
            self._flag_log(e, "stun", self.t < e.stun_until, "bị choáng", "hết choáng")
            self._flag_log(e, "slow", e.slow_total() > 0.05, "bị làm chậm", "hết làm chậm")
        u["t"] += dt
        if e.frozen():
            u["frozen"] += dt
        if e.fc["freezing"]:
            u["freezing"] += dt
        if e.drained():
            u["drained"] += dt
        if e.wet():
            u["wet"] += dt
        if self.t < e.stun_until:
            u["stunned"] += dt
        u["slow_int"] += e.slow_total() * dt
        u["slow_max"] = max(u["slow_max"], e.slow_total())
        u["bl_int"] += len(e.bl["stacks"]) * dt
        u["vague_int"] += len(e.vg["exp"]) * dt

    def run(self):
        dt = self.dt
        while self.t < self.T:
            if self.sample_every and self.t >= self._next_sample - 1e-9:
                self._take_sample()
            while self.events and self.events[0][0] <= self.t + 1e-9:
                _, _, fn = heapq.heappop(self.events)
                fn()
            for e in self.ents:
                self.tick_ent(e)
            order = self.ents[:]
            self.rng.shuffle(order)          # tránh thiên vị bên hành động trước
            for e in order:
                self.act(e)
            for e in self.ents:
                self._uptime(e)
            self.t += dt
            if not self.infinite:
                a = any(x.alive and x.team == "A" for x in self.ents)
                b = any(x.alive and x.team == "B" for x in self.ents)
                if not (a and b):
                    break
        self.t_end = self.t
        if self.sample_every:                       # điền các mốc còn lại bằng trạng thái cuối
            while self._next_sample <= self.T + 1e-9:
                self._take_sample()
        return self

    # ---- kết quả ----
    def winner(self):
        a = any(x.alive and x.team == "A" for x in self.ents)
        b = any(x.alive and x.team == "B" for x in self.ents)
        if a and not b:
            return "A"
        if b and not a:
            return "B"
        return None

    def team_damage(self, team):
        tot = 0.0
        for e in self.ents:
            if e.team == team:
                m = self.m[e.name]
                tot += m["direct"] + m["dot"] + m["true"] + m["bonus"]
        return tot


# --------------------------------------------------------------------------- kiểm tra luật skill / build
def skill_dps_potential(cfg, sk):
    """DPS tiềm năng nếu dùng liên tục theo cooldown: (ATK gốc + base) * hits / cd (+ true_base)."""
    atk = cfg["rules"]["stats_base"]["atk"]
    hits = sk.get("hits", 1)
    cd = max(1e-9, sk.get("cd", 1.0))
    return ((atk + sk.get("base", 0)) * hits + sk.get("true_base", 0) * hits) / cd if hits else 0.0


def validate_cfg(cfg):
    """Trả về (lỗi, cảnh báo) theo 'skill_rules' trong rules.json."""
    R = cfg["rules"]
    sr = R["skill_rules"]
    errs, warns = [], []
    skills = {k: v for k, v in cfg["skills"].items() if not k.startswith("_")}
    tiers = sr["tiers"]
    for sid, sk in skills.items():
        if sk.get("magic") not in MAGICS:
            errs.append("Skill %s: magic '%s' không hợp lệ" % (sid, sk.get("magic")))
        if "tier" not in sk:
            warns.append("Skill %s chưa có 'tier' (%s)" % (sid, "/".join(tiers)))
        elif sk["tier"] not in tiers:
            errs.append("Skill %s: tier '%s' không thuộc %s" % (sid, sk["tier"], tiers))
        for eff in sk.get("effects", []):
            if eff.get("type") not in DEFAULT_TO:
                errs.append("Skill %s: effect type '%s' không hỗ trợ" % (sid, eff.get("type")))
        band = sr.get("tier_bands", {}).get(sk.get("tier"), {})
        vals = {"base": sk.get("base", 0), "cd": sk.get("cd", 1.0), "dps": skill_dps_potential(cfg, sk)}
        for key, rng in band.items():
            if key.startswith("_") or not rng:
                continue
            lo, hi = rng
            v = vals.get(key)
            if v is not None and ((lo is not None and v < lo) or (hi is not None and v > hi)):
                warns.append("Skill %s (%s): %s = %.1f ngoài dải thiết kế [%s, %s] của tier" % (sid, sk["tier"], key, v, lo, hi))
    # bể basic của từng magic
    for m in MAGICS:
        if m in ("Stardust", "Neutral"):
            continue
        if not any(sk["magic"] == m and sk.get("tier") == sr["basic_tier"] for sk in skills.values()):
            warns.append("Magic %s chưa có skill tier %s nào: không ai chọn được basic khi lấy %s làm nhánh 1" % (m, sr["basic_tier"], m))
    for bid, b in cfg["builds"].items():
        if bid.startswith("_"):
            continue
        chosen = []
        for key in ("branch_a", "branch_b"):
            br = b[key]
            if len(br["skills"]) != sr["skills_per_branch"]:
                errs.append("Build %s: %s có %d skill (luật: %d)" % (bid, key, len(br["skills"]), sr["skills_per_branch"]))
            for sid in br["skills"]:
                if sid not in skills:
                    errs.append("Build %s: không có skill '%s'" % (bid, sid))
                elif skills[sid]["magic"] != br["magic"]:
                    errs.append("Build %s: skill %s thuộc %s nhưng nằm ở nhánh %s" % (bid, sid, skills[sid]["magic"], br["magic"]))
            chosen += br["skills"]
        bs = b.get("basic")
        if bs not in skills:
            errs.append("Build %s: basic '%s' không tồn tại" % (bid, bs))
            continue
        if skills[bs].get("tier") != sr["basic_tier"]:
            errs.append("Build %s: basic '%s' có tier '%s', phải là %s" % (bid, bs, skills[bs].get("tier"), sr["basic_tier"]))
        if sr["basic_magic_must_match_first_branch"] and skills[bs]["magic"] != b["branch_a"]["magic"]:
            errs.append("Build %s: basic '%s' thuộc %s nhưng nhánh 1 là %s (basic phải lấy từ bể basic của nhánh 1)" % (
                bid, bs, skills[bs]["magic"], b["branch_a"]["magic"]))
        allsk = chosen + [bs]
        if sr["distinct_skills"] and len(set(allsk)) != len(allsk):
            dup = sorted({x for x in allsk if allsk.count(x) > 1})
            errs.append("Build %s: skill bị trùng %s (5 skill phải khác nhau)" % (bid, dup))
        ps = R["passive_system"]
        if b.get("relic") and b.get("relics"):
            warns.append("Build %s: có cả 'relic' và 'relics' (chỉ 'relics' được dùng)" % bid)
        rel_ids = b.get("relics") if b.get("relics") is not None else ([b["relic"]] if b.get("relic") else [])
        if len(rel_ids) > ps["relic_slots"]:
            errs.append("Build %s: mang %d relic nhưng relic_slots = %d" % (bid, len(rel_ids), ps["relic_slots"]))
        if ps["relic_unique"] and len(set(rel_ids)) != len(rel_ids):
            errs.append("Build %s: relic bị trùng %s" % (bid, rel_ids))
        for rid in rel_ids:
            if rid not in cfg["relics"] or rid.startswith("_"):
                errs.append("Build %s: relic '%s' không tồn tại" % (bid, rid))
        for pk in b.get("passives_off", []):
            if pk not in PASSIVE_KEYS:
                errs.append("Build %s: passives_off '%s' không hợp lệ" % (bid, pk))
    for rid, rel in cfg["relics"].items():
        if rid.startswith("_"):
            continue
        for g in rel.get("grants", []):
            if g not in PASSIVE_KEYS or g not in R["passives"]:
                errs.append("Relic %s: grants '%s' không hợp lệ (hợp lệ: %s)" % (rid, g, ", ".join(PASSIVE_KEYS)))
        for m in rel.get("mods", []):
            if m.get("stat") not in STAT_KEYS:
                errs.append("Relic %s: stat '%s' không hợp lệ" % (rid, m.get("stat")))
    return errs, warns
