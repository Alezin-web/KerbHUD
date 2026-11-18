"""Ferramentas de linha de comando da Etapa 1 (somente leitura).

  python -m kerbhud run [--sim auto|iracing|lmu|demo] [--edit]   # abre o overlay (padrão)
  python -m kerbhud diag [--sim auto|iracing|lmu|demo] [--seconds 10] [--hz 4]
  python -m kerbhud snapshot [--sim ...]        # imprime 1 Snapshot em JSON
  python -m kerbhud probe-profile [--dir PASTA] # procura Driver/Safety Rank em arquivos locais do LMU
  python -m kerbhud probe-rest                  # lista endpoints da REST API local do LMU
  python -m kerbhud fetch-logos [--dir PASTA]    # baixa os logotipos das marcas (precisa de internet)
  python -m kerbhud logos-status [--dir PASTA]  # mostra quais logos de marcas estão instaladas e quais faltam
  python -m kerbhud fetch-flags [--dir PASTA]    # baixa as bandeiras dos países (precisa de internet)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from . import __version__
from .core.engine import Engine, load_settings
from .core.model import Snapshot, to_jsonable
from .core.brands import brand_for_car, load_overrides_file
from .core.paths import config_dir
from .providers.demo import STAGES as DEMO_STAGES


class _NoBrand:
    key = "NÃO RECONHECIDA"


_NO_BRAND = _NoBrand()

DEMO_SCENARIOS = list(DEMO_STAGES)


def _fmt_t(v) -> str:
    if v is None:
        return "  --  "
    m, s = divmod(v, 60)
    return f"{int(m)}:{s:06.3f}"


def _render(s: Snapshot) -> str:
    out = [f"[{s.sim.value.upper()}] {s.status_text}" + ("   *** DADOS SINTÉTICOS (DEMO) ***" if s.is_demo else "")]
    for w in s.warnings:
        out.append(f"  ! {w}")
    if not s.connected:
        return "\n".join(out)
    ss = s.session
    out.append(f"  Sessão: {ss.session_type} | pista: {ss.track_name} | {ss.track_length_m and round(ss.track_length_m)} m"
               f" | restante: {ss.time_remaining_s and round(ss.time_remaining_s)} s | bandeira: {ss.flag}")
    p = s.profile
    out.append(f"  Perfil [{p.source.value}]: lic={p.license_class} SR={p.license_sr} iR={p.irating} "
               f"driverRank={p.driver_rank} safetyRank={p.safety_rank}")
    i = s.inputs
    if i:
        out.append(f"  Inputs: v={i.speed_kmh:5.1f} km/h  marcha={i.gear:+d}  rpm={i.rpm:6.0f}/{i.rpm_max}  "
                   f"acel={i.throttle:4.2f} freio={i.brake:4.2f} emb={i.clutch:4.2f}  "
                   f"volante={i.steering:+.2f} ({i.steering_deg and round(i.steering_deg)}°)  "
                   f"shift={i.shift_pct and round(i.shift_pct, 2)}[{i.shift_source}]")
    else:
        out.append("  Inputs: indisponível (sem carro do jogador)")
    out.append(f"  Relógio: decorrido={ss.elapsed_s and round(ss.elapsed_s)}s total={ss.total_s and round(ss.total_s)}s "
               f"incidentes={ss.incidents}/{ss.incident_limit}")
    if s.debug:
        out.append("  Debug: " + ", ".join(f"{k}={v}" for k, v in s.debug.items()))
    out.append(f"  Piloto na garagem: {s.in_garage}   dirigindo: {s.driving}")
    out.append(f"  Carros: {len(s.cars)}   capacidades: {', '.join(sorted(s.capabilities))}")
    for c in sorted(s.cars, key=lambda c: c.position or 999)[:8]:
        mark = ">" if c.is_player else " "
        out.append(f"  {mark}P{c.position or '-':<3} #{c.car_number or '?':<4} {c.driver_name[:18]:<18} "
                   f"{(c.class_name or '')[:9]:<9} v{c.laps_completed} best {_fmt_t(c.best_lap)} last {_fmt_t(c.last_lap)} "
                   f"gapL {c.gap_leader if c.gap_leader is None else round(c.gap_leader, 1)} "
                   f"gapA {c.gap_ahead if c.gap_ahead is None else round(c.gap_ahead, 1)} [{c.status.value}] "
                   f"pneu={c.tire} nrg={c.energy_pct and round(c.energy_pct)} lic={c.license} iR={c.irating} "
                   f"veic={(c.vehicle_raw or '')[:80]!r} equipe={(c.team_name or '')[:30]!r} "
                   f"marca={(brand_for_car(c.car_model, c.vehicle_raw, c.team_name, c.class_name, s.sim) or _NO_BRAND).key}")
    return "\n".join(out)


def _engine_for(sim: str) -> Engine:
    load_overrides_file(config_dir() / "brand_overrides.json")
    cfg = load_settings(Path("config/settings.json"))
    cfg["simulator"] = sim
    return Engine(cfg)


def cmd_diag(a) -> int:
    eng = _engine_for(a.sim)
    eng.start()
    end = time.time() + a.seconds
    out = open(a.out, "w", encoding="utf-8") if a.out else None  # também grava num arquivo para você enviar
    try:
        if out:
            print(f"Gravando também em: {Path(a.out).resolve()}")
        while time.time() < end:
            text = _render(eng.latest()) + "\n" + "-" * 100
            print(text)
            if out:
                out.write(text + "\n")
                out.flush()
            time.sleep(1.0 / a.hz)
    finally:
        eng.stop()
        if out:
            out.close()
    return 0


def cmd_snapshot(a) -> int:
    eng = _engine_for(a.sim)
    eng.start()
    deadline = time.time() + a.wait
    snap = eng.latest()
    while time.time() < deadline and not snap.connected:
        time.sleep(0.2)
        snap = eng.latest()
    eng.stop()
    json.dump(to_jsonable(snap), sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


_RANK_RE = re.compile(r"(safety|driver)[ _\-]?(rank|rating)|\brank\b", re.I)
_TEXT_EXT = {".json", ".ini", ".txt", ".xml", ".cfg", ".plr", ".yaml", ".yml"}


def cmd_probe_profile(a) -> int:
    root = a.dir
    if root is None:
        # tenta descobrir a pasta UserData pela própria memória compartilhada do LMU
        from .core.memory import MappingNotFound, open_named_mapping
        from .providers import lmu_layout as L
        try:
            mem = open_named_mapping(L.LMU_SHARED_MEMORY_NAME)
            raw = mem.read(L.OFF_PATHS, L.MAX_PATH_LENGTH)  # primeiro campo: userData
            root = raw.split(b"\0", 1)[0].decode("utf-8", "replace")
            mem.close()
        except MappingNotFound:
            print("LMU não está publicando LMU_Data. Passe --dir <pasta UserData do LMU>.")
            return 1
    base = Path(root)
    print(f"Procurando em: {base}  (somente leitura)")
    hits = 0
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in _TEXT_EXT:
            continue
        try:
            if p.stat().st_size > 3_000_000:
                continue
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if _RANK_RE.search(line):
                    print(f"{p}:{n}: {line.strip()[:200]}")
                    hits += 1
                    if hits >= a.max:
                        print("... limite atingido")
                        return 0
        except OSError:
            continue
    print(f"{hits} ocorrência(s).")
    return 0


def cmd_probe_rest(a) -> int:
    url = f"http://localhost:{a.port}/swagger-schema.json"
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            schema = json.load(r)
    except Exception as exc:  # noqa: BLE001
        print(f"Não foi possível ler {url}: {exc}\nO LMU precisa estar aberto.")
        return 1
    paths = sorted((schema.get("paths") or {}).keys())
    pat = re.compile(r"rank|profile|standing|driver|session|player|race", re.I)
    print(f"{len(paths)} endpoints. Relevantes:")
    for p in paths:
        if pat.search(p):
            print("  ", p)
    return 0


def cmd_fetch_logos(a) -> int:
    from .core.logos import fetch_logos
    from .core.paths import logos_dir
    dest = Path(a.dir) if a.dir else logos_dir()
    print(f"Baixando logos para {dest} ... (arquivos PNG públicos do repositório 'car-logos-dataset')")
    res = fetch_logos(dest, overwrite=a.overwrite)
    print(res.summary)
    for e in res.errors:
        print("  falha:", e)
    return 1 if res.fatal else 0


def cmd_logos_status(a) -> int:
    from .core.logos import logos_status
    from .core.paths import logos_dir
    d = Path(a.dir) if a.dir else logos_dir()
    status = logos_status(d)
    have = [s for s in status if s.path is not None]
    absent = [s for s in status if s.path is None]
    print(f"Pasta de logos: {d}")
    print(f"Logos instaladas: {len(have)} de {len(status)} marcas do catálogo\n")
    for s in have:
        print(f"  [ok]   {s.name:<18} {s.path.name}")
    for s in absent:
        origem = "pode ser baixado" if s.in_dataset else "NÃO costuma existir no repositório: coloque o arquivo você mesmo"
        print(f"  [FALTA] {s.name:<17} {s.key}.png   ({origem})")
    if absent:
        print("\nPara adicionar uma logo: copie a imagem (png, webp, jpg ou svg) para a pasta acima com o nome indicado.")
        print("Para baixar as que existem no repositório: python -m kerbhud fetch-logos")
    return 0


def cmd_fetch_flags(a) -> int:
    from .core.flags import fetch_flags
    from .core.paths import flags_dir
    dest = Path(a.dir) if a.dir else flags_dir()
    print(f"Baixando bandeiras para {dest} ... (PNGs do FlagCDN, pode levar um minuto)")
    last = [0]

    def progress(done: int, total: int) -> None:
        if done - last[0] >= 25 or done == total:
            last[0] = done
            print(f"  {done}/{total}")

    res = fetch_flags(dest, overwrite=a.overwrite, progress=progress)
    print(res.summary)
    for e in res.errors[:10]:
        print("  falha:", e)
    return 1 if res.fatal else 0


def cmd_run(a) -> int:
    print(f"KerbHUD {__version__}  |  código em: {Path(__file__).resolve().parent}")
    try:
        from .ui.app import run
    except ImportError as exc:
        print(f"PySide6 não encontrado ({exc}). Instale com: pip install -r requirements.txt")
        return 1
    return run(sim=a.sim, edit=a.edit, demo_scenario=a.demo_scenario)


def version_text() -> str:
    """Tudo o que ajuda a saber QUAL cópia do app está rodando."""
    import platform
    try:
        from importlib.metadata import version as pkg_version
        qt = pkg_version("PySide6")
    except Exception:  # noqa: BLE001
        qt = "não instalado"
    from .core.paths import config_dir
    return (f"KerbHUD {__version__}\n"
            f"  código em ....: {Path(__file__).resolve().parent}\n"
            f"  Python .......: {platform.python_version()}  ({sys.executable})\n"
            f"  PySide6 ......: {qt}\n"
            f"  configuração .: {config_dir()}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("--version", "-V"):
        print(version_text())
        return 0
    if not argv:
        argv = ["run"]  # duplo clique / sem argumentos = abrir o overlay
    ap = argparse.ArgumentParser(prog="kerbhud")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ff = sub.add_parser("fetch-flags"); ff.add_argument("--dir"); ff.add_argument("--overwrite", action="store_true")
    ff.set_defaults(fn=cmd_fetch_flags)
    ls = sub.add_parser("logos-status"); ls.add_argument("--dir"); ls.set_defaults(fn=cmd_logos_status)
    fl = sub.add_parser("fetch-logos"); fl.add_argument("--dir"); fl.add_argument("--overwrite", action="store_true")
    fl.set_defaults(fn=cmd_fetch_logos)
    r = sub.add_parser("run"); r.add_argument("--sim", default="auto", choices=["auto", "iracing", "lmu", "demo"])
    r.add_argument("--edit", action="store_true", help="abre já em modo de edição")
    r.add_argument("--demo-scenario", default=None, choices=["tour", *DEMO_SCENARIOS],
                   help="cenário do modo DEMO (padrão: tour = roteiro completo)")
    r.set_defaults(fn=cmd_run)
    d = sub.add_parser("diag"); d.add_argument("--sim", default="auto", choices=["auto", "iracing", "lmu", "demo"])
    d.add_argument("--out", default=None, help="grava a saída também neste arquivo")
    d.add_argument("--seconds", type=float, default=10); d.add_argument("--hz", type=float, default=2)
    d.set_defaults(fn=cmd_diag)
    s = sub.add_parser("snapshot"); s.add_argument("--sim", default="auto", choices=["auto", "iracing", "lmu", "demo"])
    s.add_argument("--wait", type=float, default=5); s.set_defaults(fn=cmd_snapshot)
    pp = sub.add_parser("probe-profile"); pp.add_argument("--dir"); pp.add_argument("--max", type=int, default=200)
    pp.set_defaults(fn=cmd_probe_profile)
    pr = sub.add_parser("probe-rest"); pr.add_argument("--port", type=int, default=6397); pr.set_defaults(fn=cmd_probe_rest)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
