"""Provider do iRacing (iRacing SDK, memória compartilhada, SOMENTE LEITURA).

Implementação própria e enxuta do protocolo irsdk (sem pacote externo):
  * cabeçalho -> tabela de variáveis -> buffers triplos de telemetria;
  * YAML de sessão para pilotos, carros, licença e iRating.

Licença e iRating vêm do YAML de sessão (`DriverInfo.Drivers[]`) e não de
telemetria: são dados de perfil publicados pelo iRacing para a sessão atual.

Pontos marcados "VERIFICAR" dependem de confirmação com o jogo aberto; o
comando `kerbhud diag --sim iracing` mostra os valores brutos para isso.
"""
from __future__ import annotations

import math
import re
import struct
import time
from dataclasses import dataclass
from typing import Any, Optional

from ..core.memory import MappingBoundsError, MappingNotFound, MemoryView, Opener, open_named_mapping
from ..core.model import (
    CAP_BEST_LAST_LAP, CAP_CAR_MODEL, CAP_CAR_NUMBER, CAP_CLASS, CAP_GAPS, CAP_INCIDENTS, CAP_INPUTS,
    CAP_PROFILE_IRATING, CAP_PROFILE_LICENSE, CAP_SHIFT_LIGHTS_DERIVED,
    CAP_SHIFT_LIGHTS_SIM, CAP_STANDINGS, CAP_STEERING_ANGLE, CAP_TIRE, CAP_TRACKMAP_PCT, CAP_DAMAGE, CAP_FUEL,
    CAP_FLAGS, CAP_PLAYER_XY, CAP_PLAYER_XY_ESTIMATED, CAP_SIDE_TRAFFIC, CAP_TIRE_DETAIL, CarDamage, CarState, FuelState,
    TIRE_CORNERS, TireSet, TireWheel,
    CarStatus, DriverProfile, Inputs, ProfileSource, SessionState, Sim, Snapshot,
)
from ..core.deadreckon import DeadReckoner
from ..core.flags import country_code
from ..core.livegap import live_gaps
from ..core.liveorder import LiveOrder
from ..core.log import get_logger
from ..core.textfmt import is_race
from .base import Provider, ProviderDisconnected
from .session_yaml import as_float, as_int, parse_session_yaml

IRSDK_MEMMAP_NAME = "Local\\IRSDKMemMapFileName"
IRSDK_ST_CONNECTED = 1
MAX_CARS = 64

_HEADER = struct.Struct("<12i")  # ver,status,tickRate,sessInfoUpdate,sessInfoLen,sessInfoOff,numVars,varHdrOff,numBuf,bufLen,pad,pad
_BUF = struct.Struct("<4i")  # tickCount, bufOffset, pad, pad
_BUF_TABLE_OFFSET = 48
_VARHDR = struct.Struct("<iiiB3x32s64s32s")  # type, offset, count, countAsTime, name, desc, unit
_VARHDR_SIZE = _VARHDR.size  # 144

_TYPES = {  # irsdk_VarType -> (struct char, size)
    0: ("c", 1), 1: ("?", 1), 2: ("i", 4), 3: ("I", 4), 4: ("f", 4), 5: ("d", 8),
}

_LIC_STR = re.compile(r"^\s*([A-Za-z])\s+(\d+(?:\.\d+)?)")
# LicLevel -> classe (fallback caso LicString venha vazio). VERIFICAR.
_LIC_LEVEL_CLASS = [(4, "R"), (8, "D"), (12, "C"), (16, "B"), (20, "A")]


@dataclass(frozen=True)
class VarHeader:
    type: int
    offset: int
    count: int
    name: str


def _cstr(b: bytes) -> str:
    return b.split(b"\0", 1)[0].decode("cp1252", errors="replace")


def _license_from(drv: dict) -> tuple[Optional[str], Optional[float], Optional[str]]:
    """Retorna (classe, SR, texto) a partir de LicString/LicLevel."""
    s = drv.get("LicString") or ""
    m = _LIC_STR.match(s)
    if m:
        return m.group(1).upper(), float(m.group(2)), f"{m.group(1).upper()} {m.group(2)}"
    lvl = as_int(drv.get("LicLevel"))
    if lvl is not None:
        for top, letter in _LIC_LEVEL_CLASS:
            if lvl <= top:
                return letter, None, letter
        return "P", None, "P"
    return None, None, None


def _hex_color(v: Any) -> Optional[str]:
    try:
        n = int(str(v), 0)
    except (TypeError, ValueError):
        return None
    return f"#{n & 0xFFFFFF:06x}"


FROZEN_AFTER_S = 8.0       # pneus iguais por tanto tempo com o carro andando = o jogo não está atualizando
FROZEN_MIN_SPEED_MS = 5.0


class IRacingProvider(Provider):
    sim = Sim.IRACING

    def __init__(self, opener: Optional[Opener] = None, invert_clutch: bool = True, live_positions: bool = True):
        self._opener: Opener = opener or (lambda: open_named_mapping(IRSDK_MEMMAP_NAME))
        self._mem: Optional[MemoryView] = None
        self._vars: dict[str, VarHeader] = {}
        self._vars_key: Optional[tuple] = None
        self._last_tick = -1
        self._sess_update = -1
        self._clock = time.monotonic
        self._tire_sig: Optional[tuple] = None  # assinatura dos valores de pneu e quando mudou pela última vez
        self._tire_changed_at = 0.0
        self._tire_last: dict[str, TireWheel] = {}  # última leitura REAL de cada roda (o iRacing só atualiza no pit)
        self._yaml: dict[str, Any] = {}
        self._drivers: dict[int, dict] = {}
        self._dead_reckoning = DeadReckoner()  # posição estimada: o iRacing normal não publica Lat/Lon
        # VERIFICAR: ClutchRaw do iRacing vale 1.0 com o pedal solto. Se na sua
        # configuração for o contrário, desligue em settings (invert_clutch=false).
        self._invert_clutch = invert_clutch
        self._live_positions = live_positions  # corrida: ordem pela posição na pista, não pela oficial (que só muda na linha)
        self._live_order = LiveOrder()

    # ------------------------------------------------------------------ #
    def hint(self) -> str:
        return "iRacing: abra o simulador e entre em uma sessão (o SDK só publica dados com a sessão ativa)."

    def connect(self) -> bool:
        if self._mem is None:
            try:
                self._mem = self._opener()
            except MappingNotFound:
                return False
        try:
            hdr = self._header()
        except (MappingBoundsError, MappingNotFound):
            self.close()
            return False
        if not hdr[1] & IRSDK_ST_CONNECTED:
            return False  # simulador aberto, mas sem sessão
        self._reset_cache()
        return True

    def close(self) -> None:
        if self._mem is not None:
            self._mem.close()
            self._mem = None
        self._reset_cache()

    def _reset_cache(self) -> None:
        self._vars.clear()
        self._vars_key = None
        self._last_tick = -1
        self._sess_update = -1
        self._tire_last = {}
        self._tire_sig = None
        self._yaml = {}
        self._drivers = {}
        self._dead_reckoning.reset()
        self._live_order.reset()

    # ------------------------------------------------------------------ #
    def _header(self) -> tuple:
        assert self._mem is not None
        return _HEADER.unpack(self._mem.read(0, _HEADER.size))

    def _read_var_table(self, hdr: tuple) -> None:
        assert self._mem is not None
        num_vars, off = hdr[6], hdr[7]
        key = (num_vars, off)
        if key == self._vars_key and self._vars:
            return
        raw = self._mem.read(off, num_vars * _VARHDR_SIZE)
        self._vars = {}
        for i in range(num_vars):
            t, o, c, _cat, name, _d, _u = _VARHDR.unpack_from(raw, i * _VARHDR_SIZE)
            self._vars[_cstr(name)] = VarHeader(t, o, c, _cstr(name))
        self._vars_key = key

    def _latest_buffer(self, hdr: tuple) -> tuple[int, bytes]:
        """Lê o buffer de telemetria mais recente, validando que não foi sobrescrito."""
        assert self._mem is not None
        num_buf, buf_len = hdr[8], hdr[9]
        for _attempt in range(3):
            ticks = []
            for i in range(min(num_buf, 4)):
                tick, off, _p1, _p2 = _BUF.unpack(self._mem.read(_BUF_TABLE_OFFSET + i * _BUF.size, _BUF.size))
                ticks.append((tick, off))
            tick, off = max(ticks)
            data = self._mem.read(off, buf_len)
            tick2 = _BUF.unpack(self._mem.read(
                _BUF_TABLE_OFFSET + ticks.index((tick, off)) * _BUF.size, _BUF.size))[0]
            if tick2 == tick:
                return tick, data
        raise MappingBoundsError("buffer de telemetria instável")

    def _get(self, buf: bytes, name: str, default: Any = None) -> Any:
        vh = self._vars.get(name)
        if vh is None:
            return default
        ch, size = _TYPES.get(vh.type, ("i", 4))
        if vh.count == 1:
            return struct.unpack_from("<" + ch, buf, vh.offset)[0]
        return list(struct.unpack_from(f"<{vh.count}{ch}", buf, vh.offset))

    def _refresh_yaml(self, hdr: tuple) -> None:
        assert self._mem is not None
        upd, length, off = hdr[3], hdr[4], hdr[5]
        if upd == self._sess_update or length <= 0:
            return
        text = self._mem.read(off, length).split(b"\0", 1)[0].decode("cp1252", errors="replace")
        self._sess_update = upd  # marca já: se a leitura falhar, não tenta de novo 60 vezes por segundo até o próximo upd
        try:
            self._yaml = parse_session_yaml(text)
        except Exception:  # noqa: BLE001 - texto estranho do jogo: mantém os dados da sessão anterior
            get_logger().exception("Não foi possível ler o texto de sessão do iRacing (SessionInfo)")
            return
        drivers = (self._yaml.get("DriverInfo") or {}).get("Drivers") or []
        self._drivers = {}
        for d in drivers:
            idx = as_int(d.get("CarIdx"))
            if idx is not None:
                self._drivers[idx] = d

    # ------------------------------------------------------------------ #
    def poll(self) -> Optional[Snapshot]:
        if self._mem is None:
            raise ProviderDisconnected("não conectado")
        try:
            hdr = self._header()
            if not hdr[1] & IRSDK_ST_CONNECTED:
                raise ProviderDisconnected("sessão do iRacing encerrada")
            self._read_var_table(hdr)
            self._refresh_yaml(hdr)
            tick, buf = self._latest_buffer(hdr)
        except (MappingBoundsError, MappingNotFound, struct.error) as exc:
            raise ProviderDisconnected(str(exc)) from exc
        if tick == self._last_tick:
            return None
        self._last_tick = tick
        return self._build(buf)

    # ------------------------------------------------------------------ #
    def _build(self, buf: bytes) -> Snapshot:
        g = lambda name, d=None: self._get(buf, name, d)  # noqa: E731
        weekend = self._yaml.get("WeekendInfo") or {}
        dinfo = self._yaml.get("DriverInfo") or {}
        sinfo = self._yaml.get("SessionInfo") or {}

        track_len_km = as_float(weekend.get("TrackLength"))
        if track_len_km is not None and "mi" in str(weekend.get("TrackLength", "")).lower():
            track_len_m = track_len_km * 1609.344
        else:
            track_len_m = track_len_km * 1000.0 if track_len_km is not None else None

        sess_num = g("SessionNum", 0)
        session_type = None
        laps_total = None
        for s in sinfo.get("Sessions") or []:
            if as_int(s.get("SessionNum")) == sess_num:
                session_type = s.get("SessionType")
                laps_total = as_int(s.get("SessionLaps"))  # "unlimited" -> None
        remain = g("SessionTimeRemain")
        remain_ok = remain is not None and 0 <= remain < 604800  # 604800 s = "sem limite"
        total = g("SessionTimeTotal")
        total_ok = total is not None and 0 < total < 604800
        elapsed = (total - remain) if (total_ok and remain_ok and remain <= total) else None
        inc = g("PlayerCarMyIncidentCount")  # VERIFICAR: nome da variável no seu SDK
        wopts = weekend.get("WeekendOptions") if isinstance(weekend.get("WeekendOptions"), dict) else {}
        inc_limit = as_int(wopts.get("IncidentLimit"))  # "unlimited" -> None
        session = SessionState(
            active=True,
            track_name=weekend.get("TrackDisplayName") or weekend.get("TrackName"),
            track_length_m=track_len_m,
            session_type=session_type,
            time_remaining_s=remain if remain_ok else None,
            laps_total=laps_total,
            flag=None,
            flags=self._flags(g("SessionFlags")),
            in_realtime=bool(g("IsOnTrack", False)),
            elapsed_s=elapsed,
            total_s=total if total_ok else None,
            incidents=int(inc) if inc is not None else None,
            incident_limit=inc_limit if (inc_limit and inc_limit > 0) else None,
        )

        player_idx = as_int(dinfo.get("DriverCarIdx"))
        cars = self._cars(buf, player_idx, live=self._live_positions and is_race(session_type))
        caps = {CAP_STANDINGS, CAP_BEST_LAST_LAP, CAP_CLASS, CAP_TRACKMAP_PCT, CAP_CAR_NUMBER,
                CAP_CAR_MODEL, CAP_PROFILE_IRATING, CAP_PROFILE_LICENSE}
        if any(c.gap_leader is not None for c in cars):
            caps |= {CAP_GAPS}
        if session.incidents is not None:
            caps.add(CAP_INCIDENTS)
        if any(c.tire for c in cars):
            caps.add(CAP_TIRE)

        fuel, damage = self._fuel(buf), self._damage(buf)
        if fuel is not None:
            caps.add(CAP_FUEL)
        if damage is not None:
            caps.add(CAP_DAMAGE)
        if session.flags or g("SessionFlags") is not None:
            caps.add(CAP_FLAGS)
        tires = self._tires(buf)
        if tires is not None:
            caps.add(CAP_TIRE_DETAIL)
        side = self._side_traffic(g("CarLeftRight"))
        if side is not None:
            caps.add(CAP_SIDE_TRAFFIC)
        xy = self._player_xy(buf)
        if xy is not None:  # GPS do carro do piloto (só em builds de depuração do iRacing): serve para gravar o traçado
            caps.add(CAP_PLAYER_XY)
        else:  # o normal: sem Lat/Lon. Estima o caminho por velocidade x rumo (o traçado corrige a deriva)
            xy = self._dead_reckoning.update(g("SessionTime"), g("Speed"), g("YawNorth"))
            if xy is not None:
                caps.add(CAP_PLAYER_XY_ESTIMATED)
        if xy is not None:
            for c in cars:
                if c.is_player:
                    c.world_x, c.world_z = xy

        inputs = self._inputs(buf, dinfo)
        if inputs is not None:
            caps |= {CAP_INPUTS, CAP_STEERING_ANGLE}
            caps.add(CAP_SHIFT_LIGHTS_SIM if inputs.shift_source == "sim" else CAP_SHIFT_LIGHTS_DERIVED)

        profile = DriverProfile(source=ProfileSource.UNAVAILABLE)
        me = self._drivers.get(player_idx) if player_idx is not None else None
        if me:
            lic_class, lic_sr, _txt = _license_from(me)
            profile = DriverProfile(
                license_class=lic_class, license_sr=lic_sr, irating=as_int(me.get("IRating")),
                source=ProfileSource.LIVE,
            )
        return Snapshot(
            sim=Sim.IRACING, connected=True, session=session, inputs=inputs, cars=cars,
            player_idx=player_idx, profile=profile, capabilities=frozenset(caps), fuel=fuel, damage=damage, tires=tires, side_traffic=side,
            in_garage=(bool(g("IsInGarage")) if g("IsInGarage") is not None else None),  # VERIFICAR no jogo
            driving=self._driving(g("IsOnTrack"), g("IsReplayPlaying")),
            status_text="iRacing conectado",
            debug={"SessionTimeTotal": total, "SessionTimeRemain": remain,
                   "IncidentLimit(raw)": wopts.get("IncidentLimit"),
                   "PlayerCarMyIncidentCount": inc,
                   "CarIdxTireCompound(presente)": "CarIdxTireCompound" in self._vars,
                   "pneus_brutos": self.tire_raw_debug(buf),
                   "posicao_do_carro": ("GPS Lat/Lon" if CAP_PLAYER_XY in caps else
                                        "estimada (Speed+YawNorth)" if CAP_PLAYER_XY_ESTIMATED in caps else
                                        "indisponível (faltam Lat/Lon e YawNorth/SessionTime)")},
        )

    # ------------------------------------------------------------------ #
    def _cars(self, buf: bytes, player_idx: Optional[int], live: bool = False) -> list[CarState]:
        g = lambda name: self._get(buf, name)  # noqa: E731
        pct = g("CarIdxLapDistPct") or []
        lap_done = g("CarIdxLapCompleted") or []
        pos = g("CarIdxPosition") or []
        cpos = g("CarIdxClassPosition") or []
        f2 = g("CarIdxF2Time") or []
        est = g("CarIdxEstTime") or []
        on_pit = g("CarIdxOnPitRoad") or []
        surface = g("CarIdxTrackSurface") or []
        last = g("CarIdxLastLapTime") or []
        best = g("CarIdxBestLapTime") or []
        compound = g("CarIdxTireCompound") or []  # VERIFICAR: pode não existir em SDKs antigos

        def at(arr, i, default=None):
            return arr[i] if i < len(arr) else default

        cars: list[CarState] = []
        for idx, d in sorted(self._drivers.items()):
            if idx >= MAX_CARS or as_int(d.get("CarIsPaceCar"), 0) == 1 or as_int(d.get("IsSpectator"), 0) == 1:
                continue
            surf = at(surface, idx, -1)
            p = at(pct, idx, -1.0)
            # Piloto registrado que ainda não entrou no mundo (ou já saiu dele) NÃO é descartado: entra como
            # "fora da pista" e os módulos o mostram apagado.
            lic_class, lic_sr, lic_txt = _license_from(d)
            if surf == -1:
                status = CarStatus.OUT
            elif at(on_pit, idx, False):
                status = CarStatus.PITS
            else:
                status = CarStatus.RUNNING
            lt, bt = at(last, idx, -1.0), at(best, idx, -1.0)
            cars.append(CarState(
                idx=idx,
                driver_name=d.get("UserName", ""),
                team_name=d.get("TeamName") or None,
                car_number=d.get("CarNumber") or None,
                car_model=d.get("CarScreenName") or d.get("CarScreenNameShort") or None,
                class_name=d.get("CarClassShortName") or None,
                class_color=_hex_color(d.get("CarClassColor")),
                position=at(pos, idx, 0) or None,
                class_position=at(cpos, idx, 0) or None,
                laps_completed=at(lap_done, idx, None),
                lap_dist_pct=p if p is not None and p >= 0 else None,
                best_lap=bt if bt and bt > 0 else None,
                last_lap=lt if lt and lt > 0 else None,
                est_lap_time=as_float(d.get("CarClassEstLapTime")),  # usado pelo Relative; None se ausente
                status=status,
                is_player=(idx == player_idx),
                irating=as_int(d.get("IRating")),
                license=lic_txt,
                license_class=lic_class,
                license_sr=lic_sr,
                tire=self._tire(at(compound, idx, -1)),
                vehicle_raw=" ".join(x for x in (d.get("CarPath"), d.get("CarScreenName")) if x) or None,
                country=country_code(d.get("FlairName")),  # VERIFICAR: "flair" = país do piloto no iRacing
            ))

        # Corrida: a posição oficial só muda na linha de chegada; a ordem ao vivo vem da posição na pista.
        if live:
            self._live_order.apply(cars)
        else:
            self._live_order.reset()

        # Sem posição publicada (comum em treino): ordena pela melhor volta real.
        if cars and all(c.position is None for c in cars):
            ranked = sorted((c for c in cars if c.best_lap), key=lambda c: c.best_lap)
            for r, c in enumerate(ranked, start=1):
                c.position = r
            for cls in {c.class_name for c in ranked}:
                for r, c in enumerate([c for c in ranked if c.class_name == cls], start=1):
                    c.class_position = r

        # Gaps: CarIdxF2Time = tempo atrás do líder (corrida). Gap para o carro à frente
        # é a diferença entre carros consecutivos na ordem de posição.
        ordered = sorted((c for c in cars if c.position), key=lambda c: c.position or 0)
        prev: Optional[CarState] = None
        leader_laps = ordered[0].laps_completed if ordered else None
        for c in ordered:
            f = at(f2, c.idx, None)
            if f is not None and f >= 0 and (c.position == 1 or f > 0):
                c.gap_leader = float(f)
                if prev is not None and prev.gap_leader is not None:
                    c.gap_ahead = max(0.0, c.gap_leader - prev.gap_leader)
            if leader_laps is not None and c.laps_completed is not None:
                c.laps_behind_leader = max(0, leader_laps - c.laps_completed)
            prev = c
        if live:  # corrida: Int/Gap pela posição na pista, a cada leitura (o do jogo só muda na linha de chegada)
            def _est(i: int) -> Optional[float]:
                v = at(est, i, None)
                return float(v) if v is not None and v >= 0 else None
            fresh = live_gaps(cars, _est)
            if fresh:
                for c in cars:
                    c.gap_leader, c.gap_ahead = fresh.get(c.idx, (None, None))
        return cars

    def _fuel(self, buf: bytes) -> Optional[FuelState]:
        g = lambda name, d=None: self._get(buf, name, d)  # noqa: E731
        level = g("FuelLevel")
        if level is None or not (0 <= level < 5000):
            return None
        pct = g("FuelLevelPct")  # 0..1; com o nível dá a capacidade
        cap = float(level) / float(pct) if pct and pct > 0.02 else None
        return FuelState(level_l=float(level), capacity_l=cap)

    def _damage(self, buf: bytes) -> Optional[CarDamage]:
        """O iRacing NÃO publica avarias por região; só os tempos de reparo e de reboque (VERIFICAR no jogo)."""
        g = lambda name, d=None: self._get(buf, name, d)  # noqa: E731
        req, opt, tow = g("PitRepairLeft"), g("PitOptRepairLeft"), g("PlayerCarTowTime")
        if req is None and opt is None and tow is None:
            return None
        pos = lambda v: float(v) if v is not None and 0 <= v < 100000 else None  # noqa: E731
        return CarDamage(repair_required_s=pos(req), repair_optional_s=pos(opt), tow_s=pos(tow))

    @staticmethod
    def _driving(on_track, replay) -> Optional[bool]:
        """Piloto dentro do carro? `IsOnTrack` é falso na garagem, no replay e na tela entre sessões; no replay o iRacing
        continua publicando o carro do piloto, então só `IsInGarage` não basta para esconder o overlay."""
        if on_track is None:
            return None
        return bool(on_track) and not bool(replay)

    def _player_xy(self, buf: bytes) -> Optional[tuple[float, float]]:
        """Lat/Lon (graus) do carro do piloto -> metros, norte para cima (x = leste, z = norte)."""
        g = lambda name, d=None: self._get(buf, name, d)  # noqa: E731
        lat, lon = g("Lat"), g("Lon")
        if lat is None or lon is None or (lat == 0 and lon == 0) or abs(lat) > 90 or abs(lon) > 180:
            return None
        return (math.radians(lon) * 6371000.0 * math.cos(math.radians(lat)), math.radians(lat) * 6371000.0)

    #: bits de SessionFlags (irsdk_Flags) -> nossa bandeira
    _FLAG_BITS = ((0x10, "red"), (0x10000, "black"), (0x20000, "disqualify"), (0x100000, "repair"),
                  (0x8 | 0x100, "yellow"), (0x4000 | 0x8000, "caution"), (0x20, "blue"), (0x40, "debris"),
                  (0x2, "white"), (0x1, "checkered"), (0x4, "green"))

    @classmethod
    def _flags(cls, raw: Optional[int]) -> list[str]:
        if raw is None:
            return []
        return [name for mask, name in cls._FLAG_BITS if int(raw) & mask]

    @staticmethod
    def _side_traffic(raw: Optional[int]) -> Optional[tuple[int, int]]:
        """CarLeftRight: 0 desligado, 1 livre, 2 esquerda, 3 direita, 4 ambos, 5 dois à esquerda, 6 dois à direita."""
        table = {1: (0, 0), 2: (1, 0), 3: (0, 1), 4: (1, 1), 5: (2, 0), 6: (0, 2)}
        return table.get(int(raw)) if raw is not None else None

    def tire_raw_debug(self, buf: bytes) -> str:
        """Diagnóstico: valores CRUS dos pneus como o iRacing envia (nomes que existem, zonas e pressão por roda) e se o
        módulo recebeu pneus. Serve para ver o que o jogo realmente manda (ex.: zerado fora do pit)."""
        corners = ("LF", "RF", "LR", "RR")
        names = sorted(n for n in self._vars if n[:2] in corners and any(k in n for k in ("temp", "wear", "ress")))
        parts = []
        for pre in corners:
            vals = []
            for suffix in ("tempCL", "tempCM", "tempCR", "tempL", "tempM", "tempR", "wearL", "wearM", "wearR",
                           "pressure", "coldPressure"):
                v = self._get(buf, pre + suffix)
                if v is not None:
                    vals.append(f"{suffix}={v:.2f}" if isinstance(v, float) else f"{suffix}={v}")
            parts.append(f"{pre}[{' '.join(vals) or 'sem variaveis'}]")
        return (f"variaveis={len(names)} " + " ".join(parts)
                + f" | IsOnTrack={self._get(buf, 'IsOnTrack')} OnPitRoad={self._get(buf, 'OnPitRoad')}"
                + f" PlayerTrackSurface={self._get(buf, 'PlayerTrackSurface')}")

    def _tires(self, buf: bytes) -> Optional[TireSet]:
        """Temperatura, pressão e desgaste por roda (VERIFICAR os nomes e quando o iRacing atualiza o desgaste)."""
        g = lambda name, d=None: self._get(buf, name, d)  # noqa: E731
        prefix = {"fl": "LF", "fr": "RF", "rl": "LR", "rr": "RR"}
        wheels: dict[str, TireWheel] = {}
        for corner in TIRE_CORNERS:
            pre = prefix[corner]
            # temperatura da carcaça (tempC*). ATENÇÃO: num diagnóstico real (Porsche 992 Cup, até 231 km/h) ela ficou
            # CONGELADA no valor de antes de sair do box; por isso há a detecção de "valor parado" mais abaixo.
            # A de superfície (temp*) só entra se a da carcaça não existir.
            temps = [g(f"{pre}tempC{s}") for s in ("L", "M", "R")]
            if any(t is None for t in temps) or not any(t > 0.0 for t in temps):  # ausente ou zerada: não é leitura
                temps = [g(f"{pre}temp{s}") for s in ("L", "M", "R")]
            wear = [g(f"{pre}wear{s}") for s in ("L", "M", "R")]
            press = g(f"{pre}pressure")
            # O iRacing só atualiza parte desses valores no pit; na pista manda zero ou nada. Zero NÃO é leitura:
            # vira "sem leitura" e, se houver uma leitura real anterior, ela é mantida e marcada como "último pit".
            temp = sum(temps) / 3 if all(t is not None and t > 0.0 for t in temps) else None
            wear_ok = all(w is not None and w > 0.0 for w in wear)
            wear_v = sum(wear) / 3 * 100.0 if wear_ok else None
            if temp is not None and not (-50 < temp < 400):
                temp = None
            if wear_v is not None and not (0 < wear_v <= 100.5):
                wear_v = None
            if press is not None and not (0 < press < 1000):
                press = None
            zt = tuple(temps) if temp is not None else None
            zw = tuple(w * 100.0 for w in wear) if wear_v is not None else None
            if zw is not None and not all(0 < w <= 100.5 for w in zw):
                zw = None
            fresh = TireWheel(temp_c=temp, pressure_kpa=press, wear_pct=wear_v, temps_c=zt, wear_zones=zw)
            last = self._tire_last.get(corner)
            stale = False
            if last is not None:  # completa o que faltou agora com a última leitura real
                for name in ("temp_c", "pressure_kpa", "wear_pct", "temps_c", "wear_zones"):
                    if getattr(fresh, name) is None and getattr(last, name) is not None:
                        setattr(fresh, name, getattr(last, name))
                        stale = True
            fresh.stale = stale
            if temp is not None or wear_v is not None or press is not None:
                self._tire_last[corner] = TireWheel(temp_c=fresh.temp_c, pressure_kpa=fresh.pressure_kpa,
                                                    wear_pct=fresh.wear_pct, temps_c=fresh.temps_c, wear_zones=fresh.wear_zones)
            if any(getattr(fresh, n) is not None for n in ("temp_c", "pressure_kpa", "wear_pct")):
                wheels[corner] = fresh
        # Valores que NÃO mudam com o carro andando não são leitura ao vivo (o iRacing só atualiza no pit/garagem):
        # marcados como "última leitura", em vez de passar por dados de agora.
        sig = tuple((c, round(w.temp_c or 0.0, 2), round(w.wear_pct or 0.0, 2), round(w.pressure_kpa or 0.0, 1))
                    for c, w in sorted(wheels.items()))
        now = self._clock()
        if sig != self._tire_sig:
            self._tire_sig, self._tire_changed_at = sig, now
        moving = float(g("Speed", 0.0) or 0.0) > FROZEN_MIN_SPEED_MS
        if wheels and moving and now - self._tire_changed_at > FROZEN_AFTER_S:
            for w in wheels.values():
                w.stale = True
        return TireSet(wheels=wheels) if wheels else None

    @staticmethod
    def _tire(index: Optional[int]) -> Optional[str]:
        """Índice de composto do iRacing -> letra. VERIFICAR: assumimos 0 = seco, 1 = chuva."""
        if index is None or index < 0:
            return None
        return {0: "D", 1: "W"}.get(int(index), str(int(index)))

    # ------------------------------------------------------------------ #
    def _inputs(self, buf: bytes, dinfo: dict) -> Optional[Inputs]:
        g = lambda name, d=None: self._get(buf, name, d)  # noqa: E731
        if "Throttle" not in self._vars and "ThrottleRaw" not in self._vars:
            return None
        thr = g("ThrottleRaw", g("Throttle", 0.0))
        brk = g("BrakeRaw", g("Brake", 0.0))
        clu_raw = g("ClutchRaw", g("Clutch", 0.0))
        clu = (1.0 - clu_raw) if self._invert_clutch else clu_raw
        ang = g("SteeringWheelAngle", 0.0)  # rad; VERIFICAR: positivo = esquerda no iRacing
        ang_max = g("SteeringWheelAngleMax", None)
        steer_deg = -math.degrees(ang)  # convertido para positivo = direita
        steer = max(-1.0, min(1.0, -ang / ang_max)) if ang_max else max(-1.0, min(1.0, steer_deg / 450.0))
        rpm = g("RPM", 0.0)
        rpm_max = as_float(dinfo.get("DriverCarRedLine")) or as_float(dinfo.get("DriverCarSLBlinkRPM"))
        shift_sim = g("ShiftIndicatorPct", None)
        first, last_led = as_float(dinfo.get("DriverCarSLFirstRPM")), as_float(dinfo.get("DriverCarSLLastRPM"))
        blink_rpm = as_float(dinfo.get("DriverCarSLBlinkRPM"))
        blink: Optional[bool] = None
        if first is not None and last_led and last_led > first:  # mesmos RPMs do shift light do jogo: LEDs em sincronia com ele
            shift, src = max(0.0, min(1.0, (rpm - first) / (last_led - first))), "sim"
            blink = (rpm >= blink_rpm) if blink_rpm else None
        elif shift_sim is not None:
            shift, src = max(0.0, min(1.0, shift_sim)), "sim"
        else:
            first, shift_rpm = as_float(dinfo.get("DriverCarSLFirstRPM")), as_float(dinfo.get("DriverCarSLShiftRPM"))
            if first is not None and shift_rpm and shift_rpm > first:
                shift, src = max(0.0, min(1.0, (rpm - first) / (shift_rpm - first))), "derived"
            else:
                shift, src = None, None
        return Inputs(
            throttle=max(0.0, min(1.0, thr)), brake=max(0.0, min(1.0, brk)),
            clutch=max(0.0, min(1.0, clu)), steering=steer, steering_deg=steer_deg,
            gear=int(g("Gear", 0)), rpm=float(rpm), rpm_max=rpm_max,
            speed_ms=float(g("Speed", 0.0)), shift_pct=shift, shift_source=src, shift_blink=blink,
            abs_active=bool(g("BrakeABSactive", False)) if "BrakeABSactive" in self._vars else None,  # o TC o iRacing não informa
        )
