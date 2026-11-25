"""Provider do Le Mans Ultimate (memória compartilhada nativa `LMU_Data`).

Somente leitura. Pré-requisito no jogo: Settings > Gameplay > "Enable Plugins".
Sem essa opção o jogo não publica o mapeamento `LMU_Data`.

O que NÃO existe na memória compartilhada (ver docs/NOTAS-TECNICAS.pt-BR.md, seção Limitações):
  * número do carro como campo próprio (tentamos extrair de `mVehicleName`);
  * Driver Rank / Safety Rank do perfil (valor manual nas configurações até
    confirmarmos uma fonte local; use `kerbhud probe-profile`).
"""
from __future__ import annotations

import ctypes as C
import math
import re
import time
from typing import Optional

from ..core.assists import lockup
from ..core.sectorflags import SectorFlagWatch
from ..core.shiftlearn import ShiftLearner
from ..core.heading import MotionHeading, OriCalibrator, TurnSense
from ..core.memory import MappingBoundsError, MappingNotFound, MemoryView, Opener, open_named_mapping
from ..core.model import (
    CAP_BEST_LAST_LAP, CAP_CAR_NUMBER, CAP_CLASS, CAP_ENERGY, CAP_GAPS, CAP_INPUTS,
    CAP_PROFILE_RANKS, CAP_SHIFT_LIGHTS_DERIVED, CAP_STANDINGS, CAP_STEERING_ANGLE, CAP_TIRE,
    CAP_TRACKMAP_PCT, CAP_TRACKMAP_XY, CAP_CONTACT, CAP_DAMAGE, CAP_FLAGS, CAP_FUEL, CAP_POSE, CAP_TIRE_DETAIL, CarDamage, ContactState,
    TIRE_CORNERS, PlayerPose, TireSet, TireWheel, CarState, CarStatus, DriverProfile,
    FuelState, Inputs,
    ProfileSource, SessionState, Sim, Snapshot,
)
from . import lmu_layout as L
from ..core.tires import normalize_compound
from .base import Provider, ProviderDisconnected

EXTRA_REFRESH_S = 0.25  # telemetria de todos os carros (pneu/energia) muda devagar

_CAR_NO = re.compile(r"#\s*(\d{1,3})\b")


def _txt(b: bytes) -> str:
    return b.split(b"\0", 1)[0].decode("utf-8", errors="replace").strip()


def _clean_name(name: str) -> str:
    """O LMU acrescenta um código de jogador online ("Denis Golubev#8275"); o overlay mostra só o nome."""
    return re.sub(r"\s*#\d{3,}$", "", name).strip() or name


def _valid_time(v: float) -> Optional[float]:
    # LMU/rF2 usa -1 (ou valores <= 0) quando ainda não há tempo.
    return v if v and v > 0 and math.isfinite(v) else None


def session_type_name(code: int) -> str:
    if code == 0:
        return "Test Day"
    if 1 <= code <= 4:
        return "Practice"
    if 5 <= code <= 8:
        return "Qualifying"
    if code == 9:
        return "Warmup"
    if 10 <= code <= 13:
        return "Race"
    return f"Session {code}"


def energy_percent(raw: float) -> Optional[float]:
    """Energia virtual -> 0..100. VERIFICAR a escala no jogo: valores <= 1 são tratados como fração."""
    if not raw or not math.isfinite(raw) or raw <= 0:
        return None  # 0 = carro sem energia virtual (ou dado ausente): não mostramos "0%"
    return raw * 100.0 if raw <= 1.0 else min(raw, 100.0)


def tire_set(telem) -> Optional[TireSet]:
    """Rodas do carro do piloto (rF2: FL, FR, RL, RR; temperaturas em Kelvin, desgaste 1 = novo). VERIFICAR no jogo."""
    wheels: dict[str, TireWheel] = {}
    for corner, w in zip(TIRE_CORNERS, telem.mWheels):
        temps = [float(t) for t in w.mTemperature]
        temp = (sum(temps) / 3 - 273.15) if all(t > 100.0 for t in temps) else None
        opt = float(w.mOptimalTemp)
        opt_c = (opt - 273.15 if opt > 200.0 else opt) if opt > 1.0 else None
        press = float(w.mPressure) if 0 < w.mPressure < 1000 else None
        wear = float(w.mWear) * 100.0 if 0.0 <= w.mWear <= 1.001 else None
        zones = tuple(t - 273.15 for t in temps) if all(t > 100.0 for t in temps) else None  # esquerda/centro/direita
        wheels[corner] = TireWheel(temp_c=temp, optimal_c=opt_c, pressure_kpa=press, wear_pct=wear, temps_c=zones,
                                   flat=bool(w.mFlat), detached=bool(w.mDetached))
    if not any(w.temp_c is not None or w.pressure_kpa is not None or w.wear_pct is not None
               for w in wheels.values()):
        return None
    return TireSet(wheels=wheels, compound=_txt(telem.mFrontTireCompoundName) or None)


def tire_raw_debug(telem) -> str:
    """Valores CRUS dos pneus como o jogo envia (para o diagnóstico): temperatura (3 zonas), carcaça, camada interna,
    carga, pressão e temperatura ideal. Serve para conferir a unidade (Kelvin ou °C) e qual campo é qual."""
    out = []
    for corner, w in zip(TIRE_CORNERS, telem.mWheels):
        r = lambda v: round(float(v), 1)  # noqa: E731
        out.append(f"{corner}: mTemperature={[r(t) for t in w.mTemperature]} carcaca={r(w.mTireCarcassTemperature)} "
                   f"interna={[r(t) for t in w.mTireInnerLayerTemperature]} carga={r(w.mTireLoad)} "
                   f"pressao={r(w.mPressure)} ideal={r(w.mOptimalTemp)} desgaste={round(float(w.mWear), 3)}")
    return " | ".join(out)


def player_pose(ori) -> Optional[PlayerPose]:
    """Eixos do carro no mundo (plano x/z) a partir de `mOri`.

    Pelo SDK do rFactor 2, `mOri` são as LINHAS da matriz: o produto escalar de um vetor local com a linha 0/1/2 dá o
    X/Y/Z do MUNDO. Logo o eixo local x (esquerda) no mundo é a COLUNA 0 (linha0.x, linha2.x) e o eixo local z
    (traseira) é a COLUNA 2 (linha0.z, linha2.z): frente = -coluna 2. A leitura é conferida com o movimento do carro
    (`OriCalibrator`)."""
    def unit(x: float, z: float) -> Optional[tuple[float, float]]:
        n = math.hypot(x, z)
        return (x / n, z / n) if n > 1e-6 and math.isfinite(n) else None
    fwd = unit(-float(ori[0].z), -float(ori[2].z))
    left = unit(float(ori[0].x), float(ori[2].x))
    return PlayerPose(forward=fwd, left=left) if fwd and left else None


def lmu_flags(game_phase: int, player_scoring, sector_yellow: bool) -> list[str]:
    """Bandeiras mostradas ao piloto (VERIFICAR): fase do jogo, selo azul do carro e amarela de setor.

    A amarela de setor vem de `SectorFlagWatch` (mudança do valor de repouso de `mSectorFlag`): antes qualquer valor
    diferente de 0 contava e o painel ficava SEMPRE amarelo no LMU (relato do usuário, que persistiu quando só o valor 11
    contava). `mUnderYellow` também não conta (a amarela geral é a fase 6)."""
    flags: list[str] = []
    if game_phase == 7:
        flags.append("red")
    if player_scoring is not None and int(player_scoring.mFlag) == 6:
        flags.append("blue")
    if sector_yellow:
        flags.append("yellow")
    if game_phase == 6:
        flags.append("caution")
    if game_phase == 8:
        flags.append("checkered")
    if game_phase == 5:
        flags.append("green")
    return flags


def flag_name(game_phase: int) -> Optional[str]:
    return {5: "green", 6: "fcy", 7: "stopped", 8: "checkered"}.get(game_phase)


DRIVING_MS = 6.0  # abaixo disso (~22 km/h) a direção pelo movimento não é confiável


class LmuProvider(Provider):
    sim = Sim.LMU

    def __init__(self, opener: Optional[Opener] = None, manual_ranks: Optional[dict] = None):
        self._opener: Opener = opener or (lambda: open_named_mapping(L.LMU_SHARED_MEMORY_NAME))
        self._mem: Optional[MemoryView] = None
        self._manual = manual_ranks or {}
        self._last_stamp: Optional[tuple] = None
        self._warned_layout = False
        self._heading = MotionHeading()
        self._ori_cal = OriCalibrator()
        self._turn = TurnSense()
        self._shift = ShiftLearner()
        self._sectors = SectorFlagWatch()
        self._extra: dict[int, tuple[Optional[str], Optional[float]]] = {}  # mID -> (pneu, energia%)
        self._extra_at = 0.0
        self._extra_debug: dict = {}

    # ------------------------------------------------------------------ #
    def hint(self) -> str:
        return ("Le Mans Ultimate: abra o jogo e ative Settings > Gameplay > "
                "'Enable Plugins' (necessário para publicar LMU_Data).")

    def connect(self) -> bool:
        if self._mem is not None:
            return True
        try:
            self._mem = self._opener()
        except MappingNotFound:
            return False
        self._last_stamp = None
        self._heading.reset()
        self._ori_cal = OriCalibrator()
        self._turn = TurnSense()
        self._sectors.reset()
        self._extra, self._extra_at = {}, 0.0
        return True

    def close(self) -> None:
        if self._mem is not None:
            self._mem.close()
            self._mem = None

    # ------------------------------------------------------------------ #
    def poll(self) -> Optional[Snapshot]:
        mem = self._mem
        if mem is None:
            raise ProviderDisconnected("não conectado")
        warnings: list[str] = []
        if mem.size < L.SIZE_TOTAL:
            warnings.append(
                f"Mapeamento LMU_Data menor que o esperado ({mem.size} < {L.SIZE_TOTAL} bytes): "
                "o layout do jogo pode ter mudado. Rode 'kerbhud diag --sim lmu'."
            )
            snap = Snapshot(sim=Sim.LMU, connected=True, warnings=warnings,
                            status_text="Layout LMU incompatível")
            return snap
        try:
            info = L.ScoringInfo.from_buffer_copy(mem.read(L.OFF_SCORING_INFO, C.sizeof(L.ScoringInfo)))
            n = max(0, min(int(info.mNumVehicles), L.MAX_MAPPED_VEHICLES))
            veh_arr = (L.VehicleScoring * n).from_buffer_copy(
                mem.read(L.OFF_SCORING_VEHICLES, n * C.sizeof(L.VehicleScoring))
            ) if n else []
            hdr = mem.read(L.OFF_TELEM_HEADER, 3)
            player_idx, has_vehicle = hdr[1], bool(hdr[2])
            telem = None
            if has_vehicle and player_idx < L.MAX_MAPPED_VEHICLES:
                off = L.OFF_TELEM_VEHICLES + player_idx * C.sizeof(L.VehicleTelemetry)
                telem = L.VehicleTelemetry.from_buffer_copy(mem.read(off, C.sizeof(L.VehicleTelemetry)))
        except (MappingNotFound, MappingBoundsError, ValueError, OSError) as exc:
            raise ProviderDisconnected(str(exc)) from exc

        stamp = (round(info.mCurrentET, 4), round(telem.mElapsedTime, 4) if telem else None)
        if stamp == self._last_stamp:
            return None  # jogo pausado / sem atualização
        self._last_stamp = stamp
        self._refresh_extra(mem, hdr[0])

        return self._build(info, veh_arr, telem, warnings)

    # ------------------------------------------------------------------ #
    def _refresh_extra(self, mem: MemoryView, active: int) -> None:
        """Lê a telemetria de TODOS os veículos (a cada 0,25 s) para pneu e energia virtual.

        Só aceitamos uma entrada como válida se o motor tem RPM máximo > 0; entradas zeradas
        (carros sem telemetria publicada) viram "desconhecido", nunca "0%".
        """
        now = time.monotonic()
        if now - self._extra_at < EXTRA_REFRESH_S:
            return
        self._extra_at = now
        n = max(0, min(int(active), L.MAX_MAPPED_VEHICLES))
        if n == 0:
            self._extra = {}
            return
        try:
            arr = (L.VehicleTelemetry * n).from_buffer_copy(
                mem.read(L.OFF_TELEM_VEHICLES, n * C.sizeof(L.VehicleTelemetry)))
        except (MappingBoundsError, ValueError, OSError):
            return
        extra: dict[int, tuple[Optional[str], Optional[float]]] = {}
        sample = None
        for t in arr:
            if t.mEngineMaxRPM <= 0:
                continue
            tire = normalize_compound(_txt(t.mFrontTireCompoundName))
            energy = energy_percent(float(t.mVirtualEnergy))
            if energy is not None and sample is None:
                sample = float(t.mVirtualEnergy)
            extra[int(t.mID)] = (tire, energy)
        self._extra = extra
        self._extra_debug = {"telemetria_validas": len(extra), "veiculos_ativos": n,
                             "mVirtualEnergy(amostra bruta)": sample}

    # ------------------------------------------------------------------ #
    def _build(self, info, vehicles, telem, warnings) -> Snapshot:
        track_len = info.mLapDist if info.mLapDist and info.mLapDist > 0 else None
        track_name = _txt(info.mTrackName) or None
        n = len(vehicles)
        active = n > 0 and track_name is not None
        remaining = float(info.mSessionTimeRemaining) if info.mSessionTimeRemaining > 0 else None
        start_et = float(info.mStartET) if info.mStartET and info.mStartET > 0 else 0.0
        elapsed = max(0.0, float(info.mCurrentET) - start_et) if active and info.mCurrentET > 0 else None
        total = None
        if elapsed is not None and remaining is not None:
            total = elapsed + remaining
        elif active and 0 < info.mEndET - start_et < 1e7:
            total = float(info.mEndET) - start_et
        session = SessionState(
            elapsed_s=elapsed, total_s=total,
            active=active,
            track_name=track_name,
            track_length_m=track_len,
            session_type=session_type_name(info.mSession) if active else None,
            time_remaining_s=remaining,
            laps_total=info.mMaxLaps if 0 < info.mMaxLaps < 100000 else None,
            flag=flag_name(info.mGamePhase) if active else None,
            in_realtime=bool(info.mInRealtime),
        )

        cars: list[CarState] = []
        player_idx: Optional[int] = None
        for i, v in enumerate(vehicles):
            vname = _txt(v.mVehicleName)
            m = _CAR_NO.search(vname)
            if v.mFinishStatus == 3:
                status = CarStatus.DISQUALIFIED
            elif v.mFinishStatus == 2:
                status = CarStatus.OUT
            elif v.mFinishStatus == 1:
                status = CarStatus.FINISHED
            elif v.mInGarageStall:
                status = CarStatus.GARAGE
            elif v.mInPits:
                status = CarStatus.PITS
            else:
                status = CarStatus.RUNNING
            pct = (v.mLapDist / track_len) % 1.0 if track_len else None
            car = CarState(
                idx=i,
                driver_name=_clean_name(_txt(v.mDriverName)),
                team_name=_txt(v.mPitGroup) or None,
                car_number=m.group(1) if m else None,
                car_model=None,  # não confirmado na memória compartilhada
                class_name=_txt(v.mVehicleClass) or None,
                position=int(v.mPlace) or None,
                laps_completed=int(v.mTotalLaps),
                lap_dist_pct=pct,
                best_lap=_valid_time(v.mBestLapTime),
                last_lap=_valid_time(v.mLastLapTime),
                gap_leader=float(v.mTimeBehindLeader) if v.mPlace > 1 else 0.0,
                laps_behind_leader=int(v.mLapsBehindLeader),
                gap_ahead=float(v.mTimeBehindNext) if v.mPlace > 1 else None,
                est_lap_time=_valid_time(v.mEstimatedLapTime),
                status=status,
                is_player=bool(v.mIsPlayer),
                world_x=float(v.mPos.x),
                world_z=float(v.mPos.z),
                vehicle_raw=" ".join(x for x in (vname, _txt(v.mVehFilename)) if x) or None,
            )
            car.tire, car.energy_pct = self._extra.get(int(v.mID), (None, None))
            if car.is_player:
                player_idx = i
            cars.append(car)

        # Posição na classe: agrupa por classe e ordena pela posição geral.
        by_class: dict[str, list[CarState]] = {}
        for c in cars:
            by_class.setdefault(c.class_name or "", []).append(c)
        for group in by_class.values():
            group.sort(key=lambda c: c.position or 999)
            for rank, c in enumerate(group, start=1):
                c.class_position = rank

        inputs = self._inputs(telem) if telem is not None else None
        if inputs is not None:
            self._apply_shift(inputs)

        caps = {CAP_STANDINGS, CAP_GAPS, CAP_BEST_LAST_LAP, CAP_CLASS,
                CAP_TRACKMAP_PCT, CAP_TRACKMAP_XY}
        if any(c.car_number for c in cars):
            caps.add(CAP_CAR_NUMBER)
        if inputs is not None:
            caps |= {CAP_INPUTS, CAP_SHIFT_LIGHTS_DERIVED}
            if inputs.steering_deg is not None:
                caps.add(CAP_STEERING_ANGLE)

        if any(c.tire for c in cars):
            caps.add(CAP_TIRE)
        if any(c.energy_pct is not None for c in cars):
            caps.add(CAP_ENERGY)
        fuel = damage = contact = None
        if telem is not None:
            if 0 < telem.mFuelCapacity < 1000 and 0 <= telem.mFuel <= telem.mFuelCapacity * 1.05 + 1:
                fuel = FuelState(level_l=float(telem.mFuel), capacity_l=float(telem.mFuelCapacity))
                caps.add(CAP_FUEL)
            zones = [min(2, int(v)) for v in telem.mDentSeverity]
            damage = CarDamage(zones=zones, detached=bool(telem.mDetached), overheating=bool(telem.mOverheating))
            caps.add(CAP_DAMAGE)
            # superfície rF2: 2 grama, 3 terra, 4 brita (zebra e asfalto não contam). Limiares em core/incidents.py.
            contact = ContactState(impact_et=float(telem.mLastImpactET), impact_mag=float(telem.mLastImpactMagnitude),
                                   wheels_off=sum(1 for w in telem.mWheels if int(w.mSurfaceType) in (2, 3, 4)))
            caps.add(CAP_CONTACT)
        tires = tire_set(telem) if telem is not None else None
        if tires is not None:
            caps.add(CAP_TIRE_DETAIL)
        pose = None
        me_v = vehicles[player_idx] if player_idx is not None and player_idx < len(vehicles) else None
        if telem is not None:
            pose = player_pose(telem.mOri)
        if pose is None and me_v is not None:
            pose = player_pose(me_v.mOri)
        motion = self._heading.update(float(me_v.mPos.x), float(me_v.mPos.z)) if me_v is not None else None
        ori_src = telem.mOri if telem is not None else (me_v.mOri if me_v is not None else None)
        ori = [(float(o.x), float(o.y), float(o.z)) for o in ori_src[:3]] if ori_src is not None else None
        speed = inputs.speed_ms if inputs is not None else 0.0
        driving = self._heading.moving and speed >= DRIVING_MS and motion is not None  # andando de verdade (não é salto/teleporte)
        if driving:
            if ori is not None:
                self._ori_cal.observe(ori, motion)
            self._turn.observe(motion, inputs.steering if inputs is not None else 0.0, speed)
        else:
            self._turn.observe(None, 0.0, 0.0)
        pose_debug = None
        fwd = None
        if driving:  # andando: a frente é para onde o carro vai
            fwd = motion
            if pose is not None:
                dot = max(-1.0, min(1.0, pose.forward[0] * motion[0] + pose.forward[1] * motion[1]))
                pose_debug = round(math.degrees(math.acos(dot)), 1)  # quanto o mOri (leitura do SDK) discorda
        elif ori is not None and self._ori_cal.forward(ori) is not None:
            fwd = self._ori_cal.forward(ori)  # parado: a leitura do mOri que se provou certa andando
        elif pose is None and motion is not None:
            fwd = motion  # sem orientação válida: a última direção em que andou
        if fwd is not None:
            left = self._turn.left_of(fwd)  # esquerda pelo giro do volante, se já há evidência
            if left is None:
                left = (-fwd[1], fwd[0])  # sem evidência ainda: o que o diagnóstico real do LMU confirmou (volante)
            pose = PlayerPose(forward=fwd, left=left)
        if pose is not None:
            caps.add(CAP_POSE)
        if active:
            session.flags = lmu_flags(int(info.mGamePhase), me_v, self._sectors.update([int(f) for f in info.mSectorFlag]))
            raw_flags = (f"fase={int(info.mGamePhase)} setores={[int(f) for f in info.mSectorFlag]} "
                         f"mFlag={int(me_v.mFlag) if me_v is not None else None} "
                         f"underYellow={bool(me_v.mUnderYellow) if me_v is not None else None} "
                         f"yellowState={bytes(info.mYellowFlagState)!r} repouso={[self._sectors.baseline(i) for i in range(3)]}")
            caps.add(CAP_FLAGS)
        profile = self._profile(caps)
        debug = {"mCurrentET": float(info.mCurrentET), "mStartET": float(info.mStartET),
                 "mEndET": float(info.mEndET), "mSessionTimeRemaining": float(info.mSessionTimeRemaining),
                 "mMaxLaps": int(info.mMaxLaps), **self._extra_debug}
        if telem is not None:
            debug["pneus_brutos"] = tire_raw_debug(telem)  # conferir a temperatura dos pneus (unidade e campos)
        if active:
            debug["lmu_bandeiras_brutas"] = raw_flags  # confira com o que aparece na tela do jogo
        if pose_debug is not None:
            debug["pose_mOri_vs_movimento_graus"] = pose_debug  # perto de 0 = mOri concorda com o movimento
        best = self._ori_cal.best()
        if best is not None:
            debug["pose_mOri_leitura_certa"] = f"{best[0]} ({best[1]:.2f})"  # qual leitura do mOri bate com o movimento
        if self._ori_cal.n:
            debug["pose_candidatos"] = " | ".join(f"{k} {v:.2f}" for k, v in self._ori_cal.top()) + f" | n={self._ori_cal.n}"
            debug["pose_giro_volante"] = round(self._turn.evidence, 2)  # |valor| >= 0,6: o lado esquerdo vem do volante
        return Snapshot(
            sim=Sim.LMU, connected=True, session=session, inputs=inputs, cars=cars,
            player_idx=player_idx, profile=profile, capabilities=frozenset(caps), fuel=fuel, damage=damage, contact=contact, tires=tires, pose=pose,
            in_garage=(next((c.status == CarStatus.GARAGE for c in cars if c.is_player), None)),  # VERIFICAR no jogo
            warnings=warnings,
            status_text="Le Mans Ultimate conectado" if active else "LMU conectado (sem sessão ativa)",
            debug=debug,
        )

    def _apply_shift(self, i: Inputs) -> None:
        """Troca o RPM de referência do LED pelo aprendido nas trocas de marcha (o jogo não informa o do shift light)."""
        self._shift.observe(i.gear, i.rpm, i.throttle, i.rpm_max, time.monotonic())
        ref = self._shift.reference(i.rpm_max)
        if ref:
            i.shift_pct = max(0.0, min(1.0, i.rpm / ref))

    @staticmethod
    def _inputs(t) -> Inputs:
        lv = t.mLocalVel
        speed = math.sqrt(lv.x * lv.x + lv.y * lv.y + lv.z * lv.z)
        rpm_max = float(t.mEngineMaxRPM) if t.mEngineMaxRPM and t.mEngineMaxRPM > 0 else None
        shift = None
        if rpm_max:
            shift = max(0.0, min(1.0, t.mEngineRPM / rpm_max))
        rng = float(t.mPhysicalSteeringWheelRange)
        steer = max(-1.0, min(1.0, float(t.mUnfilteredSteering)))
        # ASSUNÇÃO A VALIDAR (ver docs/NOTAS-TECNICAS.pt-BR.md): mPhysicalSteeringWheelRange em graus,
        # curso total do volante; ângulo = steer * range / 2.
        steer_deg = steer * rng / 2.0 if 0 < rng < 5000 else None
        return Inputs(
            throttle=max(0.0, min(1.0, float(t.mUnfilteredThrottle))),
            brake=max(0.0, min(1.0, float(t.mUnfilteredBrake))),
            clutch=max(0.0, min(1.0, float(t.mUnfilteredClutch))),
            steering=steer,
            steering_deg=steer_deg,
            gear=int(t.mGear),
            rpm=float(t.mEngineRPM),
            rpm_max=rpm_max,
            speed_ms=speed,
            shift_pct=shift,
            shift_source="derived" if shift is not None else None,
            abs_active=bool(t.mABSActive), tc_active=bool(t.mTCActive),
            lockup=lockup(speed, float(t.mUnfilteredBrake), [float(w.mLongitudinalPatchVel) for w in t.mWheels]),
        )

    def _profile(self, caps: set) -> DriverProfile:
        dr, sr = self._manual.get("driver_rank"), self._manual.get("safety_rank")
        cb = self._manual.get("contact_badge")
        if dr or sr or cb:
            caps.add(CAP_PROFILE_RANKS)
            return DriverProfile(driver_rank=dr, safety_rank=sr, contact_badge=cb, source=ProfileSource.MANUAL,
                                 notes=["Ranks informados manualmente nas configurações."])
        return DriverProfile(
            source=ProfileSource.UNAVAILABLE,
            notes=["Driver Rank/Safety Rank não são expostos na telemetria do LMU; "
                   "configure manualmente ou rode 'kerbhud probe-profile'."],
        )
