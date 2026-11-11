#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IOM GYM - phòng tập mini cho 'Interaction of Magic'.

  python3 gym.py list                         xem build / skill / relic / mục tiêu có sẵn
  python3 gym.py run scenarios/01_duel_co_ban.json     chạy 1 kịch bản
  python3 gym.py quick amgar baseline         chạy nhanh: A đấu B (nhiều người: a+b+c)
  python3 gym.py new ten_kich_ban             tạo file kịch bản mẫu để bạn tự sửa

Mỗi lần chạy sẽ lưu 1 file kết quả vào thư mục results/ (đầy đủ kịch bản + số liệu + nhật ký + cấu hình)
để bạn gửi lại cho người kiểm tra cân bằng.
"""
import argparse
import copy
import datetime
import difflib
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import Sim, load_cfg, set_path, parse_val  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


PASSIVE_NAME = {"molten_core": "Molten Core", "zephyr_core": "Zephyr Core", "fulgur_chain": "Fulgur Chain",
                "shadow_screep": "Shadow Screep", "frigid_core": "Frigid Core", "vague_drain": "Vague/Drained",
                "blood_loss": "Blood Loss", "eruptive_core": "Eruptive Core", "chronomancy": "Chronomancy", "break": "Break"}


# --------------------------------------------------------------------------- tiện ích
def die(msg):
    sys.exit("LỖI: " + msg)


def pct(x, d=0):
    return ("%." + str(d) + "f%%") % (100 * x)


def slug(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()[:40] or "kich-ban"


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def strip_notes(x):
    """Bỏ các khóa bắt đầu bằng '_' (ghi chú) trong kịch bản."""
    if isinstance(x, dict):
        return {k: strip_notes(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, list):
        return [strip_notes(v) for v in x]
    return x


def fmt_table(headers, rows, aligns=None):
    strs = [[str(c) for c in r] for r in rows]
    cols = len(headers)
    w = [max([len(headers[i])] + [len(r[i]) for r in strs]) for i in range(cols)]
    aligns = aligns or ["<"] + [">"] * (cols - 1)
    f = lambda r: "  ".join(("{:%s%d}" % (aligns[i], w[i])).format(r[i]) for i in range(cols))
    return [f(headers), "  ".join("-" * x for x in w)] + [f(r) for r in strs]


def suggest(name, options):
    m = difflib.get_close_matches(name, list(options), n=3, cutoff=0.5)
    return (" Có phải: %s ?" % ", ".join(m)) if m else ""


# --------------------------------------------------------------------------- dựng cấu hình từ kịch bản
def to_build(cfg, name, spec):
    """Đổi mô tả nhân vật trong kịch bản thành 'build' của engine.
    Cách ngắn: {"skills": [4 skill], "basic": "...", "relics": [...], "stats": {...}}
    (skill 1-2 = nhánh 1, skill 3-4 = nhánh 2; magic tự suy ra từ skill, hoặc ghi "magics": ["A","B"]).
    Cách đầy đủ: giống một mục trong config/builds.json (branch_a / branch_b)."""
    spec = copy.deepcopy(spec)
    if "branch_a" in spec:
        spec.setdefault("label", name)
        return spec
    sk = spec.get("skills")
    if not isinstance(sk, list) or len(sk) != 4:
        die("Nhân vật '%s': cần đúng 4 skill trong \"skills\" (2 skill nhánh 1 + 2 skill nhánh 2), nhận được: %s" % (name, sk))
    for s in sk:
        if s not in cfg["skills"] or str(s).startswith("_"):
            die("Nhân vật '%s': không có skill '%s'.%s" % (name, s, suggest(s, cfg["skills"])))
    mg = spec.get("magics")
    if mg:
        m1, m2 = (mg + [mg[0]])[:2] if len(mg) == 1 else mg[:2]
    else:
        m1, m2 = cfg["skills"][sk[0]]["magic"], cfg["skills"][sk[2]]["magic"]
    basic = spec.get("basic", "auto")
    if basic == "auto":
        basic = None
        for cand in ["%s_basic" % m1] + sorted(k for k, v in cfg["skills"].items()
                                              if not k.startswith("_") and v.get("magic") == m1 and v.get("tier") == "Basic"):
            if cand in cfg["skills"] and cand not in sk:
                basic = cand
                break
    b = {"label": spec.get("label", name), "basic": basic,
         "branch_a": {"magic": m1, "skills": sk[:2]}, "branch_b": {"magic": m2, "skills": sk[2:]}}
    for k in ("relic", "relics", "stats", "res", "priority", "passives_off", "target", "guard_q"):
        if k in spec:
            b[k] = spec[k]
    return b


def build_cfg(sc, cli_sets):
    cfg = load_cfg()
    cfg["skills"].update(sc.get("skills_def", {}))
    cfg["relics"].update(sc.get("relics_def", {}))
    cfg["scenarios"]["dummies"].update(sc.get("dummies", {}))
    cfg["scenarios"]["settings"].update(sc.get("settings", {}))
    for name, spec in sc.get("fighters", {}).items():
        cfg["builds"][name] = to_build(cfg, name, spec)
    for path, val in list(sc.get("set", {}).items()) + list(cli_sets.items()):
        try:
            set_path(cfg, path, val)
        except KeyError as ex:
            die("Ghi đè \"%s\": %s" % (path, ex))
    return cfg


def resolve_team(cfg, ids, side):
    out = []
    if not ids:
        die("Đội %s đang trống." % side)
    for x in ids:
        if x.startswith("dummy:"):
            if x[6:] not in cfg["scenarios"]["dummies"]:
                die("Không có mục tiêu '%s'.%s (xem: python3 gym.py list)" % (x, suggest(x[6:], cfg["scenarios"]["dummies"])))
            out.append(x)
        elif x in cfg["builds"] and not x.startswith("_"):
            out.append(x)
        elif x in cfg["scenarios"]["dummies"]:
            out.append("dummy:" + x)
        else:
            die("Không có nhân vật/build '%s'.%s (xem: python3 gym.py list)" % (x, suggest(x, [k for k in cfg["builds"] if not k.startswith("_")])))
    return out


def soft_check(cfg, team_ids):
    """Chỉ chặn những lỗi làm mô phỏng không chạy được (thiếu skill/relic)."""
    for x in team_ids:
        if x.startswith("dummy:"):
            continue
        b = cfg["builds"][x]
        ids = list(b["branch_a"]["skills"]) + list(b["branch_b"]["skills"]) + ([b["basic"]] if b.get("basic") else [])
        for s in ids:
            if s not in cfg["skills"]:
                die("'%s' dùng skill '%s' không tồn tại.%s" % (x, s, suggest(s, cfg["skills"])))
        rel = b.get("relics") if b.get("relics") is not None else ([b["relic"]] if b.get("relic") else [])
        for r in rel:
            if r not in cfg["relics"]:
                die("'%s' dùng relic '%s' không tồn tại.%s" % (x, r, suggest(r, cfg["relics"])))


# --------------------------------------------------------------------------- gom kết quả
class Agg:
    def __init__(self):
        self.n = 0
        self.m = defaultdict(lambda: defaultdict(float))
        self.up = defaultdict(lambda: defaultdict(float))
        self.sk_dmg, self.sk_cast = defaultdict(float), defaultdict(float)
        self.wins = defaultdict(int)
        self.t_end, self.t_win = [], {"A": [], "B": []}
        self.dmg = {"A": 0.0, "B": 0.0}
        self.blocked = defaultdict(float)
        self.stimes = {}
        self.samp = defaultdict(lambda: defaultdict(lambda: [0.0, 0, 0.0]))

    def add(self, sim):
        self.n += 1
        for name, d in sim.m.items():
            for k, v in d.items():
                self.m[name][k] += v
        for name, d in sim.up.items():
            for k, v in d.items():
                if k == "slow_max":
                    self.up[name][k] = max(self.up[name][k], v)
                else:
                    self.up[name][k] += v
        for k, v in sim.sk_dmg.items():
            self.sk_dmg[k] += v
        for k, v in sim.sk_cast.items():
            self.sk_cast[k] += v
        for k, v in sim.blocked_buffs.items():
            self.blocked[k] += v
        w = sim.winner()
        self.wins[w] += 1
        self.t_end.append(sim.t_end)
        if w in ("A", "B"):
            self.t_win[w].append(sim.t_end)
        self.dmg["A"] += sim.team_damage("A")
        self.dmg["B"] += sim.team_damage("B")
        for idx, (t, snap) in enumerate(sim.samples):
            self.stimes[idx] = t
            for name, (frac, dealt) in snap.items():
                a = self.samp[idx][name]
                if frac is not None:
                    a[0] += frac
                    a[1] += 1
                a[2] += dealt

    def avg(self, name, key):
        return self.m[name][key] / max(1, self.n)


def run_batch(cfg, A, B, mode, T, runs, seed, scenario=None):
    infinite = (mode == "dps")
    agg, logs = Agg(), []
    for i in range(runs):
        sim = Sim(cfg, A, B, seed=seed * 100003 + i, infinite=infinite, T=T, log=(i == 0), sample_every=5.0, scenario=scenario).run()
        agg.add(sim)
        if i == 0:
            logs = sim.logs
    return agg, logs


# --------------------------------------------------------------------------- tạo báo cáo
def describe(cfg, probe):
    L = []
    for e in probe.ents:
        side = "[%s]" % e.team
        if e.name.startswith("dummy:"):
            extra = ""
            d = cfg["scenarios"]["dummies"][e.name[6:]]
            if d.get("kind") == "object":
                extra += " | vật thể %s" % d.get("magic")
            if d.get("in_exothermal"):
                extra += " | trong Exothermal"
            if d.get("wet"):
                extra += " | đang Wet"
            L.append("%s %s: mục tiêu giả | HP %.0f | Def %.0f | RES %s%s | đứng yên" % (side, e.name, e.maxhp, e.stat("defense"), d.get("res") or "{}", extra))
            continue
        pass_names = ", ".join(PASSIVE_NAME.get(k, k) for k in sorted(e.passives)) or "-"
        L.append("%s %s: %s" % (side, e.name, e.label))
        L.append("     ATK %.0f | HP %.0f | Def %.0f | MC %s | DefIgnore %s + %.0f | dmg x%.2f | CDR %s" % (
            e.stat("atk"), e.maxhp, e.stat("defense"), pct(e.stat("mc")), pct(e.stat("pct_def_ignore"), 1),
            e.stat("flat_def_ignore"), e.stat("damage_mult"), pct(e.stat("cdr"))))
        mg = sorted(e.carried)
        L.append("     Magic: %s%s | Nội tại: %s | Relic: %s" % (" + ".join(mg), " (PureType)" if len(mg) == 1 else "", pass_names, ", ".join(e.relic_ids) or "-"))
        for sid in e.priority:
            st = e.skills[sid]
            sk = st["sk"]
            br = {"basic": "basic", "a": "nhánh1", "b": "nhánh2"}[st["branch"]]
            scale_val = sk.get("atk_scale", sk.get("atk_pct", sk.get("scale_atk", 1.0)))
            scale_str = f"+{round(float(scale_val)*100)}%ATK"
            L.append("       - %-14s %-7s %-9s %-8s base %-4s %-9s CD %.1f" % (
                sid, br, sk.get("tier", "?"), sk["magic"], sk.get("base", 0), scale_str, probe.cd_eff(e, st)))
    return L


def uptime_rows(agg, probe):
    rows = []
    for e in probe.ents:
        u = agg.up[e.name]
        tt = u["t"] or 1.0
        vals = [u["frozen"] / tt, u["freezing"] / tt, u["drained"] / tt, u["wet"] / tt, u["stunned"] / tt]
        slow, slowmax, bl, vg = u["slow_int"] / tt, u["slow_max"], u["bl_int"] / tt, u["vague_int"] / tt
        blocked = agg.blocked[e.name] / max(1, agg.n)
        if any(v > 0.0005 for v in vals) or slow > 0.0005 or bl > 0.01 or vg > 0.01 or blocked > 0:
            rows.append((e.name, pct(vals[0]), pct(vals[1]), pct(vals[2]), pct(vals[3]), pct(vals[4]),
                         "%s (max %s)" % (pct(slow, 1), pct(slowmax)), "%.1f" % bl, "%.1f" % vg, "%.1f" % blocked))
    return rows


def report(cfg, probe, agg, mode, T, runs):
    out = []
    A = [e for e in probe.ents if e.team == "A"]
    n = max(1, agg.n)
    avg_t = sum(agg.t_end) / n
    # ---- kết quả chính ----
    out.append("--- KẾT QUẢ ---")
    if mode == "fight":
        wa, wb, wd = agg.wins["A"], agg.wins["B"], agg.wins[None]
        ts = sorted(agg.t_end)
        out.append("Đội A thắng %s | Đội B thắng %s | hòa/hết giờ %s   (%d lần chạy)" % (pct(wa / n, 1), pct(wb / n, 1), pct(wd / n, 1), n))
        out.append("Thời gian trận: trung bình %.1fs | trung vị %.1fs | ngắn nhất %.1fs | dài nhất %.1fs" % (avg_t, ts[len(ts) // 2], ts[0], ts[-1]))
        if agg.t_win["A"]:
            ta = sorted(agg.t_win["A"])
            out.append("Khi A thắng: thời gian giết trung vị %.1fs" % ta[len(ta) // 2])
        out.append("Damage đội A / đội B trong cả trận (trung bình): %.0f / %.0f" % (agg.dmg["A"] / n, agg.dmg["B"] / n))
        T_dps = avg_t
    else:
        out.append("Chế độ DPS: mọi bên HP vô hạn, đo %gs, %d lần chạy." % (T, n))
        da, db = agg.dmg["A"] / n, agg.dmg["B"] / n
        out.append("Damage đội A: %.0f (%.1f/s) | đội B: %.0f (%.1f/s)%s" % (da, da / T, db, db / T,
                   ("   -> tỉ lệ A/B = %.2f" % (da / db)) if db > 1e-6 else "   (đội B không đánh trả)"))
        T_dps = T
    # ---- damage theo người ----
    out.append("")
    out.append("--- DAMAGE THEO NGƯỜI (trung bình mỗi lần chạy) ---")
    rows = []
    for e in probe.ents:
        m = agg.m[e.name]
        tot = (m["direct"] + m["dot"] + m["true"] + m["bonus"]) / n
        rows.append((e.team, e.name, "%.0f" % (m["direct"] / n), "%.0f" % (m["dot"] / n), "%.0f" % (m["true"] / n),
                     "%.0f" % (m["bonus"] / n), "%.0f" % tot, "%.1f" % (tot / max(1e-9, T_dps)), "%.0f" % (m["heal"] / n),
                     "%.0f" % (m["taken"] / n), "%.1f" % (m["blocks"] / n)))
    out += fmt_table(["đội", "tên", "trực tiếp", "DoT", "true", "thêm", "tổng", "DPS", "hồi", "nhận", "block"], rows,
                     ["<", "<", ">", ">", ">", ">", ">", ">", ">", ">", ">"])
    # ---- skill ----
    out.append("")
    out.append("--- SKILL (số lần cast & damage trung bình mỗi lần chạy) ---")
    rows = []
    for e in probe.ents:
        if not e.skills:
            continue
        tot = sum(agg.sk_dmg[(e.name, s)] for s in e.priority) / n or 1.0
        for sid in e.priority:
            st = e.skills[sid]
            d = agg.sk_dmg[(e.name, sid)] / n
            rows.append((e.name, sid, st["sk"].get("tier", "?"), st["sk"]["magic"], "%.1f" % (agg.sk_cast[(e.name, sid)] / n),
                         "%.0f" % d, pct(d / tot) if tot else "-"))
    out += fmt_table(["tên", "skill", "tier", "magic", "số cast", "damage", "%"], rows, ["<", "<", "<", "<", ">", ">", ">"])
    # ---- hiệu ứng ----
    rows = uptime_rows(agg, probe)
    if rows:
        out.append("")
        out.append("--- HIỆU ỨNG (tỉ lệ thời gian đang chịu, tính trên thời gian còn sống) ---")
        out += fmt_table(["tên", "Frozen", "Freezing", "Drained", "Wet", "choáng", "slow TB", "Blood Loss tầng", "Vague tầng", "buff bị chặn"], rows,
                         ["<"] + [">"] * 9)
    # ---- diễn biến ----
    if agg.stimes:
        out.append("")
        last_t = max(agg.t_end) if mode == "fight" else T
        idxs = [i for i in sorted(agg.stimes) if agg.stimes[i] <= last_t + 5.0]
        if mode == "fight":
            out.append("--- DIỄN BIẾN HP TRUNG BÌNH (mỗi 5s; 0% = đã chết) ---")
            ents = [e for e in probe.ents if not (e.name.startswith("dummy:") and False)]
            hdr = ["t(s)"] + [e.name for e in ents]
            rows = []
            for i in idxs:
                row = ["%.0f" % agg.stimes[i]]
                for e in ents:
                    a = agg.samp[i][e.name]
                    row.append(pct(a[0] / a[1]) if a[1] else "-")
                rows.append(row)
            out += fmt_table(hdr, rows, [">"] * len(hdr))
        else:
            out.append("--- DAMAGE TÍCH LŨY TRUNG BÌNH (mỗi 5s) ---")
            ents = [e for e in probe.ents if agg.m[e.name]["direct"] + agg.m[e.name]["dot"] + agg.m[e.name]["true"] + agg.m[e.name]["bonus"] > 0]
            hdr = ["t(s)"] + [e.name for e in ents]
            rows = []
            for i in idxs:
                rows.append(["%.0f" % agg.stimes[i]] + ["%.0f" % (agg.samp[i][e.name][2] / n) for e in ents])
            out += fmt_table(hdr, rows, [">"] * len(hdr))
    return out


def log_text(logs, limit=None):
    lines = ["[%6.1fs] %s" % (t, txt) for t, txt in logs]
    if limit is not None and len(lines) > limit:
        return lines[:limit] + ["... (còn %d dòng nữa, xem đầy đủ trong file kết quả)" % (len(lines) - limit)]
    return lines


def variant_row(name, agg, probe, mode, T):
    n = max(1, agg.n)
    tgt = [e for e in probe.ents if e.team == "B"][0]
    u = agg.up[tgt.name]
    tt = u["t"] or 1.0
    da, db = agg.dmg["A"] / n, agg.dmg["B"] / n
    avg_t = sum(agg.t_end) / n
    return (name,
            pct(agg.wins["A"] / n) if mode == "fight" else "-",
            "%.1f" % avg_t if mode == "fight" else "%gs" % T,
            "%.0f" % da, "%.0f" % db, ("%.2f" % (da / db)) if db > 1e-6 else "-",
            pct(u["frozen"] / tt), pct(u["drained"] / tt), pct(u["slow_int"] / tt, 1), "%.1f" % (u["bl_int"] / tt))


# --------------------------------------------------------------------------- chạy kịch bản
def run_scenario(sc, cli_sets, log_lines, save, runs_override=None, time_override=None, mode_override=None):
    sc = strip_notes(sc)
    name = sc.get("name", "kich-ban")
    variants = sc.get("variants") or [{"name": "gốc"}]
    base_sc = {k: v for k, v in sc.items() if k != "variants"}
    mode = mode_override or base_sc.get("mode", "fight")
    if mode not in ("fight", "dps"):
        die("\"mode\" phải là \"fight\" hoặc \"dps\".")
    runs = runs_override or int(base_sc.get("runs", 100))
    T = time_override or float(base_sc.get("time", 120 if mode == "fight" else 30))
    seed = int(base_sc.get("seed", 1))
    stamp = datetime.datetime.now()
    full, console = [], []
    summary_rows, details = [], []
    first_digest = None

    for vi, var in enumerate(variants):
        vname = var.get("name", "biến thể %d" % (vi + 1))
        vdiff = {k: v for k, v in var.items() if k != "name"}
        vsc = deep_merge(base_sc, vdiff)
        cfg = build_cfg(vsc, cli_sets)
        A = resolve_team(cfg, vsc.get("team_a", []), "A")
        B = resolve_team(cfg, vsc.get("team_b", []), "B")
        soft_check(cfg, A + B)
        probe = Sim(cfg, A, B, seed=0, infinite=True, T=1.0)
        agg, logs = run_batch(cfg, A, B, mode, T, runs, seed)
        summary_rows.append(variant_row(vname, agg, probe, mode, T))
        head = ["=" * 78, "%s%s" % (name, ("  |  biến thể: " + vname) if len(variants) > 1 else ""), "=" * 78,
                "Chế độ: %s | %d lần chạy | %s %gs | seed %d" % (mode, runs, "tối đa" if mode == "fight" else "đo", T, seed)]
        if vsc.get("note"):
            head.append("Ghi chú: " + vsc["note"])
        sets = dict(vsc.get("set", {}))
        sets.update(cli_sets)
        if sets:
            head.append("Ghi đè: " + "; ".join("%s=%s" % (k, json.dumps(v, ensure_ascii=False)) for k, v in sets.items()))
        head.append("")
        head += describe(cfg, probe)
        head.append("")
        body = report(cfg, probe, agg, mode, T, runs)
        block = head + body
        details.append((vname, vdiff, block, logs))
        if first_digest is None:
            used_b = {x: cfg["builds"][x] for x in A + B if not x.startswith("dummy:")}
            used_sk = set()
            used_rel = set()
            for b in used_b.values():
                used_sk |= set(b["branch_a"]["skills"]) | set(b["branch_b"]["skills"]) | ({b["basic"]} if b.get("basic") else set())
                used_rel |= set(b.get("relics") or ([b["relic"]] if b.get("relic") else []))
            first_digest = {
                "builds": used_b,
                "skills": {k: cfg["skills"][k] for k in sorted(used_sk)},
                "relics": {k: cfg["relics"][k] for k in sorted(used_rel)},
                "dummies": {x[6:]: cfg["scenarios"]["dummies"][x[6:]] for x in A + B if x.startswith("dummy:")},
                "settings": cfg["scenarios"]["settings"],
                "rules": cfg["rules"],
            }

    # ---- in ra màn hình ----
    for vi, (vname, vdiff, block, logs) in enumerate(details):
        if vi == 0 or len(details) == 1:
            console += block
            console += ["", "--- NHẬT KÝ TRẬN MẪU (lần chạy #1, %d dòng đầu) ---" % log_lines] + log_text(logs, log_lines)
        if len(details) > 1 and vi == 0:
            console += ["", "(Chi tiết đầy đủ của các biến thể còn lại nằm trong file kết quả.)"]
    if len(details) > 1:
        console += ["", "=" * 78, "SO SÁNH CÁC BIẾN THỂ", "=" * 78]
        console += fmt_table(["biến thể", "A thắng", "TTK TB", "dmg A", "dmg B", "A/B", "Frozen(B1)", "Drained(B1)", "slow(B1)", "BL tầng(B1)"],
                             summary_rows, ["<"] + [">"] * 9)
        console.append("(B1 = nhân vật/mục tiêu đầu tiên của đội B)")
    print("\n".join(console))

    # ---- lưu file ----
    if save:
        os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
        fn = os.path.join(HERE, "results", "%s_%s.md" % (stamp.strftime("%Y%m%d-%H%M%S"), slug(name)))
        md = ["# Phòng tập IOM: %s" % name, "", "Tạo lúc %s | %d lần chạy | chế độ %s" % (stamp.strftime("%Y-%m-%d %H:%M:%S"), runs, mode), ""]
        if sc.get("note"):
            md += ["**Ghi chú:** " + sc["note"], ""]
        if cli_sets:
            md += ["**Ghi đè dòng lệnh:** `%s`" % json.dumps(cli_sets, ensure_ascii=False), ""]
        md += ["## Kịch bản (JSON)", "", "```json", json.dumps(sc, ensure_ascii=False, indent=1), "```", ""]
        if len(details) > 1:
            md += ["## So sánh các biến thể", "", "```text"] + fmt_table(
                ["biến thể", "A thắng", "TTK TB", "dmg A", "dmg B", "A/B", "Frozen(B1)", "Drained(B1)", "slow(B1)", "BL tầng(B1)"],
                summary_rows, ["<"] + [">"] * 9) + ["```", ""]
        for vname, vdiff, block, logs in details:
            md += ["## Kết quả%s" % ((": " + vname) if len(details) > 1 else ""), ""]
            if vdiff:
                md += ["Khác biệt so với kịch bản gốc: `%s`" % json.dumps(vdiff, ensure_ascii=False), ""]
            md += ["```text"] + block + ["```", "", "### Nhật ký trận mẫu (lần chạy #1, đầy đủ)", "", "```text"] + log_text(logs) + ["```", ""]
        md += ["## Cấu hình đã dùng (để tái lập kết quả)", "", "```json", json.dumps(first_digest, ensure_ascii=False, indent=1), "```", ""]
        with open(fn, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        print("\nĐã lưu kết quả: %s" % os.path.relpath(fn, HERE))
        print("(Gửi file này để kiểm tra cân bằng: trong đó có kịch bản, số liệu, nhật ký trận và toàn bộ cấu hình đã dùng.)")


# --------------------------------------------------------------------------- các lệnh
def parse_sets(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            die("--set cần dạng đường.dẫn=giá_trị, nhận được: %s" % it)
        k, v = it.split("=", 1)
        out[k.strip()] = parse_val(v.strip())
    return out


def cmd_list(a):
    cfg = load_cfg()
    print("--- NHÂN VẬT / BUILD (dùng trong team_a, team_b) ---")
    for k, v in cfg["builds"].items():
        if not k.startswith("_"):
            print("  %-20s %s [%s + %s]" % (k, v.get("label", ""), v["branch_a"]["magic"], v["branch_b"]["magic"]))
    print("\n--- MỤC TIÊU GIẢ (viết dạng dummy:<tên>) ---")
    for k, d in cfg["scenarios"]["dummies"].items():
        print("  dummy:%-14s %s | HP %s | Def %s%s" % (k, d.get("kind", "player"), d.get("hp"), d.get("defense"), (" | " + d["magic"]) if d.get("magic") else ""))
    print("\n--- RELIC / NỘI TẠI ---")
    for k, r in cfg["relics"].items():
        if not k.startswith("_"):
            print("  %-26s %s%s" % (k, r.get("name", ""), ("  [cấp: %s]" % ", ".join(r["grants"])) if r.get("grants") else ""))
    print("\n--- SKILL (theo magic; dạng tên [tier]) ---")
    by = defaultdict(list)
    for k, v in cfg["skills"].items():
        if not k.startswith("_"):
            by[v["magic"]].append("%s[%s]" % (k, (v.get("tier") or "?")[0]))
    for m, lst in by.items():
        print("  %-9s %s" % (m, "  ".join(lst)))
    print("\nTier: B=Basic M=Mid H=High U=Ultimate. Xem chỉ số chi tiết bằng cách mở config/skills.json.")
    return 0


TEMPLATE = {
    "name": "Tên kịch bản",
    "_ghi_chu": "Các khóa bắt đầu bằng dấu _ chỉ là ghi chú, bị bỏ qua. Xóa những phần bạn không dùng.",
    "note": "Mô tả ngắn: bạn muốn kiểm tra điều gì? (sẽ được lưu vào file kết quả)",
    "mode": "fight",
    "_mode": "fight = đánh đến khi một đội chết (xem tỉ lệ thắng). dps = mọi bên HP vô hạn, đo damage trong 'time' giây.",
    "time": 60, "runs": 100, "seed": 1,
    "team_a": ["my_hero"],
    "team_b": ["baseline"],
    "_team": "Mỗi phần tử là tên nhân vật (trong 'fighters' hoặc config/builds.json) hoặc mục tiêu giả dạng dummy:<tên>.",
    "fighters": {
        "my_hero": {
            "skills": ["Amgar_1", "Amgar_2", "Sylva_3", "Sylva_4"],
            "_skills": "4 skill: 2 đầu = nhánh 1, 2 sau = nhánh 2. Magic tự suy ra từ skill.",
            "basic": "Amgar_basic",
            "relics": ["relic_atk"],
            "stats": {"atk": 250}
        }
    },
    "skills_def": {
        "my_skill": {"name": "Skill của tôi", "magic": "Amgar", "tier": "Mid", "base": 200, "cd": 5,
                     "_hieu_ung": "thêm \"effects\": [{\"type\": \"slow\", \"value\": 0.3, \"duration\": 3}] nếu muốn"}
    },
    "relics_def": {
        "my_relic": {"name": "Relic của tôi", "grants": [], "mods": [{"stat": "atk", "mode": "add", "value": 100}]}
    },
    "dummies": {
        "my_target": {"kind": "player", "hp": 3000, "defense": 500, "res": {}}
    },
    "set": {"rules.passives.molten_core.flat_ignore": 50},
    "_set": "Ghi đè bất kỳ số liệu nào: rules.*, skills.<id>.*, relics.<id>.*, builds.<id>.*",
    "settings": {},
    "variants": [
        {"name": "gốc"},
        {"name": "flat ignore 30", "set": {"rules.passives.molten_core.flat_ignore": 30}}
    ],
    "_variants": "Tùy chọn: chạy lại cùng kịch bản với các thay đổi và so sánh. Mỗi biến thể có thể đổi bất kỳ khóa nào (set, team_b, fighters...)."
}


def cmd_new(a):
    os.makedirs(os.path.join(HERE, "scenarios"), exist_ok=True)
    fn = os.path.join(HERE, "scenarios", slug(a.name).replace("-", "_") + ".json")
    if os.path.exists(fn):
        die("File đã tồn tại: %s" % os.path.relpath(fn, HERE))
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(TEMPLATE, f, ensure_ascii=False, indent=2)
    print("Đã tạo %s. Sửa file rồi chạy: python3 gym.py run %s" % (os.path.relpath(fn, HERE), os.path.relpath(fn, HERE)))
    return 0


def cmd_run(a):
    path = a.file if os.path.exists(a.file) else os.path.join(HERE, a.file)
    if not os.path.exists(path):
        die("Không thấy file kịch bản: %s" % a.file)
    try:
        with open(path, encoding="utf-8") as f:
            sc = json.load(f)
    except json.JSONDecodeError as ex:
        die("File kịch bản không phải JSON hợp lệ (dòng %d, cột %d): %s" % (ex.lineno, ex.colno, ex.msg))
    run_scenario(sc, parse_sets(a.set), a.log, not a.no_save, a.runs, a.time, a.mode)
    return 0


def cmd_quick(a):
    sc = {"name": a.name or ("%s vs %s" % (a.a, a.b)), "team_a": a.a.split("+"), "team_b": a.b.split("+"), "mode": a.mode or "fight"}
    if a.runs:
        sc["runs"] = a.runs
    if a.time:
        sc["time"] = a.time
    run_scenario(sc, parse_sets(a.set), a.log, not a.no_save)
    return 0


def main():
    p = argparse.ArgumentParser(description="IOM GYM - phòng tập mini", epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)

    def common(q):
        q.add_argument("--set", action="append", default=[], metavar="ĐƯỜNG.DẪN=GIÁ_TRỊ", help="ghi đè tạm 1 số liệu (lặp lại được)")
        q.add_argument("--log", type=int, default=30, help="số dòng nhật ký in ra màn hình (file kết quả luôn lưu đủ)")
        q.add_argument("--no-save", action="store_true", help="không lưu file kết quả")
        q.add_argument("--runs", type=int, default=None)
        q.add_argument("--time", type=float, default=None)
        q.add_argument("--mode", choices=["fight", "dps"], default=None)

    sp.add_parser("list")
    q = sp.add_parser("new"); q.add_argument("name")
    q = sp.add_parser("run"); q.add_argument("file"); common(q)
    q = sp.add_parser("quick"); q.add_argument("a"); q.add_argument("b"); q.add_argument("--name", default=None); common(q)
    a = p.parse_args()
    sys.exit({"list": cmd_list, "new": cmd_new, "run": cmd_run, "quick": cmd_quick}[a.cmd](a))


if __name__ == "__main__":
    main()
