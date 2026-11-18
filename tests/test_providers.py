"""Testes da Etapa 1. Rodam em qualquer SO usando memória simulada (BytesMapping).

ATENÇÃO: estes testes provam que o código lê o layout que ELE MESMO descreve.
Eles NÃO substituem a validação com o jogo aberto (comando `diag`).
"""
import ctypes as C
import math
import struct
import time
import unittest

from kerbhud.core.engine import Engine, load_settings
from kerbhud.core.memory import BytesMapping, MappingNotFound, WinNamedMapping
from kerbhud.core.model import CarStatus, ProfileSource, Sim, to_jsonable
from kerbhud.providers import lmu_layout as L
from kerbhud.providers.base import ProviderDisconnected
from kerbhud.providers.demo import DemoProvider
from kerbhud.providers.iracing import IRacingProvider, _license_from
from kerbhud.providers.lmu import LmuProvider
from kerbhud.providers.session_yaml import parse_session_yaml


# --------------------------------------------------------------------------- #
class TestYaml(unittest.TestCase):
    SAMPLE = (
        "---\n"
        "WeekendInfo:\n"
        " TrackName: spa up\n"
        " TrackDisplayName: Circuit de Spa-Francorchamps\n"
        " TrackLength: 7.00 km\n"
        "SessionInfo:\n"
        " Sessions:\n"
        " - SessionNum: 0\n"
        "   SessionType: Race\n"
        "   SessionLaps: unlimited\n"
        "   ResultsPositions:\n"
        "   - Position: 1\n"
        "     CarIdx: 3\n"
        "   - Position: 2\n"
        "     CarIdx: 4\n"
        " - SessionNum: 1\n"
        "   SessionType: Practice\n"
        "DriverInfo:\n"
        " DriverCarIdx: 3\n"
        " Drivers:\n"
        " - CarIdx: 3\n"
        "   UserName: Ana: da Silva #1\n"
        "   TeamName: 'Equipe: X'\n"
        "   LicString: A 3.45\n"
        "   IRating: 2710\n"
        "   CarClassEstLapTime: 141.5\n"
        "   FlairName: Brazil\n"
        " - CarIdx: 4\n"
        "   UserName: Bob\n"
        "   FlairName: United States\n"
        "   LicString: R 1.10\n"
        "   IRating: 1350\n"
        "CameraInfo:\n"
        " Foo: bar\n"
    )

    def test_sections_lists_and_odd_values(self):
        y = parse_session_yaml(self.SAMPLE)
        self.assertNotIn("CameraInfo", y)
        self.assertEqual(y["WeekendInfo"]["TrackLength"], "7.00 km")
        sessions = y["SessionInfo"]["Sessions"]
        self.assertEqual([s["SessionType"] for s in sessions], ["Race", "Practice"])
        self.assertEqual(len(sessions[0]["ResultsPositions"]), 2)
        drivers = y["DriverInfo"]["Drivers"]
        self.assertEqual(len(drivers), 2)
        self.assertEqual(drivers[0]["UserName"], "Ana: da Silva #1")
        self.assertEqual(drivers[0]["TeamName"], "Equipe: X")
        self.assertEqual(drivers[1]["IRating"], "1350")

    def test_license_parse(self):
        self.assertEqual(_license_from({"LicString": "A 3.45"}), ("A", 3.45, "A 3.45"))
        self.assertEqual(_license_from({"LicString": "R 1.10"})[0], "R")
        self.assertEqual(_license_from({"LicLevel": "9"})[0], "C")


# --------------------------------------------------------------------------- #
def make_lmu_memory(n=3, player=1, with_telem=True):
    obj = L.ObjectOut()
    s = obj.scoring.scoringInfo
    s.mTrackName = b"Circuit de la Sarthe"
    s.mSession = 10
    s.mCurrentET = 123.456
    s.mStartET = 100.0
    s.mLapDist = 13626.0
    s.mNumVehicles = n
    s.mGamePhase = 5
    s.mSectorFlag[1] = 11  # amarela no setor 2
    s.mSessionTimeRemaining = 3000.0
    s.mMaxLaps = 100000000
    classes = [b"Hyper", b"Hyper", b"LMGT3"]
    for i in range(n):
        v = obj.scoring.vehScoringInfo[i]
        v.mDriverName = f"Driver {i}".encode()
        v.mVehicleName = f"Team {i} #{50 + i}:LM".encode()
        v.mPitGroup = f"Team {i}".encode()
        v.mID = 100 + i
        v.mVehFilename = b"ferrari_499p.veh"
        v.mPlace = i + 1
        v.mVehicleClass = classes[i % 3]
        v.mTotalLaps = 5 - i
        v.mBestLapTime = 210.5 + i
        v.mLastLapTime = -1.0 if i == 2 else 211.0
        v.mTimeBehindNext = 3.5 * i
        v.mTimeBehindLeader = 3.5 * i * (i + 1) / 2
        v.mLapDist = 1000.0 * (n - i)
        v.mIsPlayer = (i == player)
        v.mInPits = (i == 2)
        v.mPos.x, v.mPos.z = 10.0 * i, -5.0 * i
    t = obj.telemetry
    t.activeVehicles = n
    t.playerVehicleIdx = player
    t.playerHasVehicle = with_telem
    compounds = [b"Soft", b"Medium", b""]
    energy = [0.8, 55.0, 0.0]
    for i in range(n):
        if i == 2:
            continue  # carro sem telemetria publicada: entrada zerada (deve virar "desconhecido")
        te = t.telemInfo[i]
        te.mID = 100 + i
        te.mEngineMaxRPM = 8000.0
        te.mFrontTireCompoundName = compounds[i % 3]
        te.mVirtualEnergy = energy[i % 3]
    tv = t.telemInfo[player]
    tv.mElapsedTime = 99.5
    tv.mGear = 4
    tv.mEngineRPM = 7000.0
    tv.mEngineMaxRPM = 8000.0
    tv.mUnfilteredThrottle = 0.75
    tv.mUnfilteredBrake = 0.0
    tv.mUnfilteredClutch = 0.0
    tv.mUnfilteredSteering = -0.5
    tv.mPhysicalSteeringWheelRange = 540.0
    tv.mLocalVel.z = 50.0
    tv.mFuel, tv.mFuelCapacity = 40.0, 80.0
    tv.mDentSeverity[0], tv.mDentSeverity[3] = 2, 1
    tv.mOverheating = True
    for k, w in enumerate(tv.mWheels):
        w.mTemperature[0], w.mTemperature[1], w.mTemperature[2] = 350.0 + k, 352.0 + k, 354.0 + k  # Kelvin
        w.mPressure, w.mWear, w.mOptimalTemp = 180.0 + k, 0.9 - 0.1 * k, 358.15
    tv.mWheels[3].mFlat = True
    # linhas = X/Y/Z do mundo; colunas = eixos do carro. Frente = -coluna 2 = (1, 0): anda para +x; esquerda = coluna 0 = (0, 1)
    tv.mOri[0].x, tv.mOri[0].z = 0.0, -1.0
    tv.mOri[2].x, tv.mOri[2].z = 1.0, 0.0
    obj.scoring.vehScoringInfo[player].mFlag = 6
    obj.scoring.vehScoringInfo[player].mUnderYellow = True
    return bytearray(bytes(obj))


class TestLmu(unittest.TestCase):
    def test_layout_is_self_consistent(self):
        self.assertEqual(L.SIZE_TOTAL, C.sizeof(L.ObjectOut))
        self.assertGreater(L.OFF_TELEM_VEHICLES, L.OFF_SCORING_VEHICLES)
        self.assertEqual(L.OFF_SCORING_VEHICLES - L.OFF_SCORING_INFO, C.sizeof(L.ScoringInfo) + 12)

    def test_snapshot_from_fake_memory(self):
        mem = BytesMapping(make_lmu_memory())
        p = LmuProvider(opener=lambda: mem)
        self.assertTrue(p.connect())
        snap = p.poll()
        self.assertEqual(snap.sim, Sim.LMU)
        self.assertTrue(snap.session.active)
        self.assertEqual(snap.session.session_type, "Race")
        self.assertIsNone(snap.session.laps_total)  # valor "infinito" não vira número
        self.assertEqual(len(snap.cars), 3)
        me = snap.player()
        self.assertEqual(me.driver_name, "Driver 1")
        self.assertEqual(me.car_number, "51")
        self.assertEqual(me.position, 2)
        self.assertAlmostEqual(me.gap_ahead, 3.5)
        self.assertEqual(snap.cars[2].status, CarStatus.PITS)
        self.assertIsNone(snap.cars[2].last_lap)  # -1 não é tempo de volta
        self.assertEqual(snap.cars[1].class_position, 2)
        self.assertEqual(snap.cars[2].class_position, 1)  # único LMGT3
        i = snap.inputs
        self.assertAlmostEqual(i.speed_kmh, 180.0)
        self.assertEqual(i.gear, 4)
        self.assertAlmostEqual(i.throttle, 0.75)
        self.assertAlmostEqual(i.steering_deg, -135.0)
        self.assertEqual(i.shift_source, "derived")
        self.assertEqual(snap.profile.source, ProfileSource.UNAVAILABLE)
        self.assertNotIn("profile_ranks", snap.capabilities)

    def test_session_clock_tire_energy_and_vehicle(self):
        p = LmuProvider(opener=lambda: BytesMapping(make_lmu_memory()))
        p.connect()
        snap = p.poll()
        ss = snap.session
        self.assertAlmostEqual(ss.elapsed_s, 23.456)  # mCurrentET - mStartET
        self.assertAlmostEqual(ss.total_s, 23.456 + 3000.0)  # decorrido + restante
        self.assertIsNone(ss.incidents)  # LMU não publica incidentes: nada inventado
        c0, c1, c2 = snap.cars
        self.assertEqual((c0.tire, c1.tire), ("S", "M"))
        self.assertAlmostEqual(c0.energy_pct, 80.0, places=3)  # fração 0.8 (float32) -> 80 %
        self.assertAlmostEqual(c1.energy_pct, 55.0)  # já em porcentagem
        self.assertEqual((c2.tire, c2.energy_pct), (None, None))  # telemetria zerada != "0 %"
        self.assertIn("ferrari_499p.veh", c0.vehicle_raw)
        self.assertIn("tire", snap.capabilities)
        self.assertIn("energy", snap.capabilities)
        self.assertEqual(snap.debug["telemetria_validas"], 2)
        self.assertAlmostEqual(snap.debug["mCurrentET"], 123.456)

    def test_energy_percent_edge_cases(self):
        from kerbhud.providers.lmu import energy_percent
        self.assertIsNone(energy_percent(0.0))
        self.assertIsNone(energy_percent(-1.0))
        self.assertIsNone(energy_percent(float("nan")))
        self.assertAlmostEqual(energy_percent(1.0), 100.0)
        self.assertAlmostEqual(energy_percent(0.25), 25.0)
        self.assertAlmostEqual(energy_percent(73.0), 73.0)
        self.assertEqual(energy_percent(250.0), 100.0)

    def test_no_new_data_returns_none(self):
        p = LmuProvider(opener=lambda: BytesMapping(make_lmu_memory()))
        p.connect()
        self.assertIsNotNone(p.poll())
        self.assertIsNone(p.poll())

    def test_manual_ranks_are_marked_manual(self):
        p = LmuProvider(opener=lambda: BytesMapping(make_lmu_memory()),
                        manual_ranks={"driver_rank": "Silver", "safety_rank": "Gold"})
        p.connect()
        snap = p.poll()
        self.assertEqual(snap.profile.source, ProfileSource.MANUAL)
        self.assertIn("profile_ranks", snap.capabilities)

    def test_not_running(self):
        def boom():
            raise MappingNotFound("LMU_Data")
        self.assertFalse(LmuProvider(opener=boom).connect())

    def test_small_mapping_reports_layout_mismatch(self):
        p = LmuProvider(opener=lambda: BytesMapping(bytearray(1000)))
        p.connect()
        snap = p.poll()
        self.assertTrue(snap.warnings)
        self.assertEqual(snap.cars, [])


# --------------------------------------------------------------------------- #
IR_VARS = [  # nome, tipo irsdk, count
    ("SessionNum", 2, 1), ("SessionTimeRemain", 5, 1), ("SessionTimeTotal", 5, 1), ("IsOnTrack", 1, 1), ("IsInGarage", 1, 1),
    ("FuelLevel", 4, 1), ("FuelLevelPct", 4, 1), ("PitRepairLeft", 4, 1), ("PitOptRepairLeft", 4, 1),
    ("PlayerCarTowTime", 4, 1), ("Lat", 5, 1), ("Lon", 5, 1),
    ("SessionFlags", 3, 1), ("CarLeftRight", 2, 1),
    *[(f"{w}{k}", 4, 1) for w in ("LF", "RF", "LR", "RR") for k in
      ("tempL", "tempM", "tempR", "wearL", "wearM", "wearR", "pressure")],
    ("PlayerCarMyIncidentCount", 2, 1), ("CarIdxTireCompound", 2, 64),
    ("Speed", 4, 1), ("RPM", 4, 1), ("Gear", 2, 1),
    ("ThrottleRaw", 4, 1), ("BrakeRaw", 4, 1), ("ClutchRaw", 4, 1),
    ("SteeringWheelAngle", 4, 1), ("SteeringWheelAngleMax", 4, 1),
    ("CarIdxLapDistPct", 4, 64), ("CarIdxLapCompleted", 2, 64), ("CarIdxPosition", 2, 64),
    ("CarIdxClassPosition", 2, 64), ("CarIdxF2Time", 4, 64), ("CarIdxOnPitRoad", 1, 64),
    ("CarIdxTrackSurface", 2, 64), ("CarIdxLastLapTime", 4, 64), ("CarIdxBestLapTime", 4, 64),
]
_CH = {1: "?", 2: "i", 3: "I", 4: "f", 5: "d"}
_SZ = {1: 1, 2: 4, 3: 4, 4: 4, 5: 8}

IR_YAML = TestYaml.SAMPLE.replace(" TrackLength: 7.00 km\n", " TrackLength: 7.00 km\n WeekendOptions:\n  IncidentLimit: 25\n").replace(
    "DriverInfo:\n DriverCarIdx: 3\n",
    "DriverInfo:\n DriverCarIdx: 3\n DriverCarRedLine: 8000.0\n DriverCarSLFirstRPM: 6000.0\n DriverCarSLShiftRPM: 7000.0\n",
)


def make_iracing_memory(tick=10, status=1, values=None, yaml=None, skip=()):
    values = values or {}
    var_list = [v for v in IR_VARS if v[0] not in skip]
    # tabela de variáveis
    offsets, off = {}, 0
    for name, t, c in var_list:
        offsets[name] = off
        off += _SZ[t] * c
    buf_len = off
    yaml_bytes = (yaml or IR_YAML).encode("cp1252") + b"\0"
    var_off = 112
    var_table = b"".join(
        struct.pack("<iiiB3x32s64s32s", t, offsets[n], c, 0, n.encode(), b"", b"") for n, t, c in var_list
    )
    sess_off = var_off + len(var_table)
    buf_start = sess_off + len(yaml_bytes)
    n_buf = 3
    header = struct.pack("<12i", 2, status, 60, 1, len(yaml_bytes), sess_off, len(var_list), var_off, n_buf, buf_len, 0, 0)
    bufs_hdr = b"".join(
        struct.pack("<4i", tick - (2 - i), buf_start + i * buf_len, 0, 0) for i in range(n_buf)
    )
    assert len(header) == 48 and len(header + bufs_hdr) <= var_off
    mem = bytearray(buf_start + n_buf * buf_len)
    mem[0:len(header)] = header
    mem[48:48 + len(bufs_hdr)] = bufs_hdr
    mem[var_off:var_off + len(var_table)] = var_table
    mem[sess_off:sess_off + len(yaml_bytes)] = yaml_bytes
    # buffer mais recente = índice 2
    base = buf_start + 2 * buf_len
    for name, t, c in var_list:
        v = values.get(name)
        if v is None:
            continue
        v = v if isinstance(v, list) else [v]
        for k, item in enumerate(v):
            struct.pack_into("<" + _CH[t], mem, base + offsets[name] + k * _SZ[t], item)
    return mem


def ir_values():
    pct = [-1.0] * 64
    surf = [-1] * 64
    pos, cpos, lapc = [0] * 64, [0] * 64, [0] * 64
    f2 = [0.0] * 64
    lastl, bestl = [-1.0] * 64, [-1.0] * 64
    pit = [False] * 64
    for idx, p, ps, lap, f in ((3, 0.40, 2, 7, 12.5), (4, 0.55, 1, 7, 0.0)):
        pct[idx], surf[idx], pos[idx], cpos[idx], lapc[idx], f2[idx] = p, 3, ps, ps, lap, f
        lastl[idx], bestl[idx] = 140.2, 139.9
    pit[4] = True
    tire = [-1] * 64
    tire[3], tire[4] = 0, 1
    return {
        "SessionNum": 0, "SessionTimeRemain": 1800.0, "SessionTimeTotal": 2700.0, "IsOnTrack": True, "IsInGarage": False,
        "FuelLevel": 30.0, "FuelLevelPct": 0.5, "PitRepairLeft": 12.5, "PitOptRepairLeft": 4.0, "PlayerCarTowTime": 0.0,
        "Lat": -23.5, "Lon": -46.6, "SessionFlags": 0x8 | 0x20 | 0x4, "CarLeftRight": 4,
        **{f"{w}{k}": v for w, base in (("LF", 80.0), ("RF", 90.0), ("LR", 70.0), ("RR", 100.0)) for k, v in
           (("tempL", base), ("tempM", base + 3), ("tempR", base + 6), ("wearL", 0.9), ("wearM", 0.8),
            ("wearR", 0.7), ("pressure", 190.0))},
        "PlayerCarMyIncidentCount": 6, "CarIdxTireCompound": tire,
        "Speed": 50.0, "RPM": 6500.0, "Gear": 3,
        "ThrottleRaw": 0.8, "BrakeRaw": 0.1, "ClutchRaw": 1.0,
        "SteeringWheelAngle": math.radians(90), "SteeringWheelAngleMax": math.radians(450),
        "CarIdxLapDistPct": pct, "CarIdxLapCompleted": lapc, "CarIdxPosition": pos,
        "CarIdxClassPosition": cpos, "CarIdxF2Time": f2, "CarIdxOnPitRoad": pit,
        "CarIdxTrackSurface": surf, "CarIdxLastLapTime": lastl, "CarIdxBestLapTime": bestl,
    }


class TestIRacing(unittest.TestCase):
    def test_snapshot_from_fake_memory(self):
        mem = BytesMapping(make_iracing_memory(values=ir_values()))
        p = IRacingProvider(opener=lambda: mem)
        self.assertTrue(p.connect())
        snap = p.poll()
        self.assertEqual(snap.sim, Sim.IRACING)
        self.assertEqual(snap.session.track_name, "Circuit de Spa-Francorchamps")
        self.assertAlmostEqual(snap.session.track_length_m, 7000.0)
        self.assertEqual(snap.session.session_type, "Race")
        self.assertEqual(snap.player_idx, 3)
        self.assertEqual([c.idx for c in snap.cars], [3, 4])
        me = snap.player()
        self.assertEqual(me.driver_name, "Ana: da Silva #1")
        self.assertEqual(me.position, 2)
        self.assertAlmostEqual(me.gap_leader, 12.5)
        self.assertAlmostEqual(me.gap_ahead, 12.5)
        self.assertEqual(snap.cars[1].status, CarStatus.PITS)
        self.assertAlmostEqual(me.best_lap, 139.9, places=2)
        self.assertAlmostEqual(me.est_lap_time, 141.5)
        self.assertIsNone(snap.cars[1].est_lap_time)  # ausente no YAML: nada inventado
        # perfil: licença e iRating vêm do YAML
        self.assertEqual(snap.profile.license_class, "A")
        self.assertAlmostEqual(snap.profile.license_sr, 3.45)
        self.assertEqual(snap.profile.irating, 2710)
        self.assertEqual(snap.profile.source, ProfileSource.LIVE)
        i = snap.inputs
        self.assertAlmostEqual(i.speed_kmh, 180.0)
        self.assertAlmostEqual(i.throttle, 0.8, places=5)
        self.assertAlmostEqual(i.clutch, 0.0, places=5)  # ClutchRaw=1.0 => pedal solto
        self.assertAlmostEqual(i.steering_deg, -90.0, places=3)  # positivo do SDK = esquerda
        self.assertEqual(i.shift_source, "derived")
        self.assertAlmostEqual(i.shift_pct, 0.5, places=3)
        self.assertEqual(i.rpm_max, 8000.0)

    def test_session_clock_incidents_license_and_tire(self):
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=ir_values())))
        p.connect()
        snap = p.poll()
        ss = snap.session
        self.assertAlmostEqual(ss.elapsed_s, 900.0)  # total - restante
        self.assertAlmostEqual(ss.total_s, 2700.0)
        self.assertEqual((ss.incidents, ss.incident_limit), (6, 25))
        self.assertIn("incidents", snap.capabilities)
        a, b = snap.cars
        self.assertEqual((a.license_class, a.license_sr), ("A", 3.45))
        self.assertEqual((b.license_class, b.license_sr), ("R", 1.10))
        self.assertEqual((a.tire, b.tire), ("D", "W"))
        self.assertIn("tire", snap.capabilities)
        self.assertEqual(snap.debug["IncidentLimit(raw)"], "25")

    def test_unlimited_incidents_limit(self):
        y = IR_YAML.replace("IncidentLimit: 25", "IncidentLimit: unlimited")
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=ir_values(), yaml=y)))
        p.connect()
        snap = p.poll()
        self.assertIsNone(snap.session.incident_limit)  # "unlimited" não vira número
        self.assertEqual(snap.session.incidents, 6)

    def test_missing_sdk_variables_stay_unknown(self):
        mem = make_iracing_memory(values=ir_values(), skip=("PlayerCarMyIncidentCount", "CarIdxTireCompound"))
        p = IRacingProvider(opener=lambda: BytesMapping(mem))
        p.connect()
        snap = p.poll()
        self.assertIsNone(snap.session.incidents)  # SDK sem a variável: nada inventado
        self.assertTrue(all(c.tire is None for c in snap.cars))
        self.assertNotIn("incidents", snap.capabilities)
        self.assertNotIn("tire", snap.capabilities)

    def test_disconnect_when_session_ends(self):
        mem = BytesMapping(make_iracing_memory(values=ir_values()))
        p = IRacingProvider(opener=lambda: mem)
        p.connect()
        p.poll()
        mem.replace(make_iracing_memory(status=0))
        with self.assertRaises(ProviderDisconnected):
            p.poll()

    def test_no_new_tick_returns_none(self):
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=ir_values())))
        p.connect()
        self.assertIsNotNone(p.poll())
        self.assertIsNone(p.poll())

    def test_sim_open_but_no_session(self):
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(status=0)))
        self.assertFalse(p.connect())


# --------------------------------------------------------------------------- #
class TestStage6Data(unittest.TestCase):
    def test_lmu_tires_flags_and_pose(self):
        from kerbhud.core.model import CAP_FLAGS, CAP_POSE, CAP_TIRE_DETAIL
        p = LmuProvider(opener=lambda: BytesMapping(make_lmu_memory()))
        p.connect()
        s = p.poll()
        fl, rr = s.tires.wheels["fl"], s.tires.wheels["rr"]
        self.assertAlmostEqual(fl.temp_c, 352.0 - 273.15, places=3)
        self.assertEqual((fl.pressure_kpa, round(fl.wear_pct)), (180.0, 90))
        self.assertAlmostEqual(fl.optimal_c, 85.0, places=2)
        self.assertTrue(rr.flat)
        self.assertEqual(s.tires.compound, "Medium")
        self.assertEqual(set(s.session.flags), {"blue", "green"})  # 11 constante = valor de repouso: não é amarela
        self.assertEqual(s.pose.forward, (1.0, 0.0))
        self.assertEqual(s.pose.left, (0.0, 1.0))
        self.assertTrue({CAP_FLAGS, CAP_POSE, CAP_TIRE_DETAIL} <= s.capabilities)
        self.assertIn("lmu_bandeiras_brutas", s.debug)

    def test_lmu_flags_and_sector_watch(self):
        from types import SimpleNamespace as NS
        from kerbhud.core.sectorflags import SectorFlagWatch
        from kerbhud.providers.lmu import lmu_flags
        me = NS(mFlag=0, mUnderYellow=True)  # mUnderYellow sozinho não vale (o painel ficava sempre amarelo)
        self.assertEqual(lmu_flags(5, me, False), ["green"])
        self.assertEqual(lmu_flags(5, me, True), ["yellow", "green"])
        self.assertEqual(lmu_flags(5, NS(mFlag=6, mUnderYellow=False), False), ["blue", "green"])
        t = [0.0]
        w = SectorFlagWatch(clock=lambda: t[0])
        for _ in range(100):  # o jogo mantém [11, 11, 11] o tempo todo: é o repouso
            t[0] += 0.1
            self.assertFalse(w.update([11, 11, 11]))
        t[0] += 0.1
        self.assertFalse(w.update([11, 0, 11]))  # mudou agora: ainda não conta (precisa durar)
        t[0] += 0.5
        self.assertTrue(w.update([11, 0, 11]))   # durou: amarela no setor 2
        t[0] += 0.1
        self.assertFalse(w.update([11, 11, 11]))  # voltou ao repouso

    def test_lmu_without_telemetry_has_no_tires_or_pose(self):
        p = LmuProvider(opener=lambda: BytesMapping(make_lmu_memory(with_telem=False)))
        p.connect()
        s = p.poll()
        self.assertIsNone(s.tires)

    def test_iracing_flags_side_traffic_and_tires(self):
        from kerbhud.core.model import CAP_FLAGS, CAP_SIDE_TRAFFIC, CAP_TIRE_DETAIL
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=ir_values())))
        p.connect()
        s = p.poll()
        self.assertEqual(set(s.session.flags), {"yellow", "blue", "green"})
        self.assertEqual(s.side_traffic, (1, 1))
        lf = s.tires.wheels["fl"]
        self.assertAlmostEqual(lf.temp_c, 83.0)
        self.assertEqual((lf.pressure_kpa, round(lf.wear_pct)), (190.0, 80))
        self.assertTrue({CAP_FLAGS, CAP_SIDE_TRAFFIC, CAP_TIRE_DETAIL} <= s.capabilities)

    def test_iracing_side_traffic_table_and_missing_vars(self):
        for raw, expected in ((0, None), (1, (0, 0)), (2, (1, 0)), (3, (0, 1)), (5, (2, 0)), (6, (0, 2))):
            self.assertEqual(IRacingProvider._side_traffic(raw), expected)
        skip = ("SessionFlags", "CarLeftRight", "LFtempL", "LFtempM", "LFtempR")
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=ir_values(), skip=skip)))
        p.connect()
        s = p.poll()
        self.assertEqual(s.session.flags, [])
        self.assertIsNone(s.side_traffic)
        self.assertIsNone(s.tires.wheels["fl"].temp_c)  # LF sem temperatura, mas com desgaste
        self.assertIsNotNone(s.tires.wheels["fl"].wear_pct)


class TestFuelDamageAndMapData(unittest.TestCase):
    def test_lmu_fuel_and_damage_of_the_player(self):
        from kerbhud.core.model import CAP_DAMAGE, CAP_FUEL
        p = LmuProvider(opener=lambda: BytesMapping(make_lmu_memory()))
        p.connect()
        s = p.poll()
        self.assertEqual((s.fuel.level_l, s.fuel.capacity_l), (40.0, 80.0))
        self.assertEqual(s.damage.zones, [2, 0, 0, 1, 0, 0, 0, 0])
        self.assertTrue(s.damage.overheating)
        self.assertIn(CAP_FUEL, s.capabilities)
        self.assertIn(CAP_DAMAGE, s.capabilities)

    def test_lmu_without_telemetry_has_no_fuel_or_damage(self):
        p = LmuProvider(opener=lambda: BytesMapping(make_lmu_memory(with_telem=False)))
        p.connect()
        s = p.poll()
        self.assertIsNone(s.fuel)
        self.assertIsNone(s.damage)

    def test_iracing_fuel_repair_and_gps(self):
        from kerbhud.core.model import CAP_DAMAGE, CAP_FUEL, CAP_PLAYER_XY
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=ir_values())))
        p.connect()
        s = p.poll()
        self.assertEqual((s.fuel.level_l, s.fuel.capacity_l), (30.0, 60.0))
        self.assertEqual((s.damage.repair_required_s, s.damage.repair_optional_s), (12.5, 4.0))
        self.assertIsNone(s.damage.zones)  # o iRacing não publica avarias por região
        self.assertTrue({CAP_FUEL, CAP_DAMAGE, CAP_PLAYER_XY} <= s.capabilities)
        me = s.player()
        self.assertIsNotNone(me.world_x)
        self.assertLess(me.world_z, 0)  # latitude sul: z negativo (norte positivo)
        others = [c for c in s.cars if not c.is_player]
        self.assertTrue(all(c.world_x is None for c in others))  # só o piloto tem GPS

    def test_iracing_without_those_variables(self):
        skip = ("FuelLevel", "FuelLevelPct", "PitRepairLeft", "PitOptRepairLeft", "PlayerCarTowTime", "Lat", "Lon")
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=ir_values(), skip=skip)))
        p.connect()
        s = p.poll()
        self.assertIsNone(s.fuel)
        self.assertIsNone(s.damage)
        self.assertIsNone(s.player().world_x)


class TestGarageState(unittest.TestCase):
    def test_iracing_reports_garage_and_none_when_var_missing(self):
        vals = ir_values()
        vals["IsInGarage"] = True
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=vals)))
        p.connect()
        self.assertTrue(p.poll().in_garage)
        p2 = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=ir_values(), skip=("IsInGarage",))))
        p2.connect()
        self.assertIsNone(p2.poll().in_garage)
        p3 = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=ir_values())))
        p3.connect()
        self.assertFalse(p3.poll().in_garage)


class TestDemoAndEngine(unittest.TestCase):
    def test_demo_is_always_flagged(self):
        s = DemoProvider().poll()
        self.assertTrue(s.is_demo)
        self.assertEqual(s.sim, Sim.DEMO)
        self.assertTrue(any("DEMO" in w for w in s.warnings))
        pos = sorted(c.position for c in s.cars)
        self.assertEqual(pos, list(range(1, len(s.cars) + 1)))
        self.assertIsNotNone(s.player())

    def test_snapshot_is_json_serializable(self):
        import json
        json.dumps(to_jsonable(DemoProvider().poll()))

    def test_engine_demo_end_to_end(self):
        cfg = load_settings()
        cfg["simulator"] = "demo"
        eng = Engine(cfg)
        eng.start()
        deadline = time.time() + 3
        while time.time() < deadline and not eng.latest().connected:
            time.sleep(0.05)
        snap = eng.latest()
        eng.stop()
        self.assertTrue(snap.connected and snap.is_demo)

    def test_engine_recovers_after_disconnect(self):
        mem = BytesMapping(make_lmu_memory())
        prov = LmuProvider(opener=lambda: mem)
        cfg = load_settings()
        cfg["simulator"] = "lmu"
        cfg["update_hz"] = 100
        eng = Engine(cfg, providers={"lmu": prov, "iracing": IRacingProvider(opener=lambda: (_ for _ in ()).throw(MappingNotFound("x"))), "demo": DemoProvider()})
        eng.start()
        t0 = time.time()
        while time.time() - t0 < 3 and eng.latest().sim != Sim.LMU:
            time.sleep(0.02)
        self.assertEqual(eng.latest().sim, Sim.LMU)
        eng.stop()

    def test_named_mapping_not_found_on_this_os(self):
        import sys
        if sys.platform != "win32":
            with self.assertRaises(MappingNotFound):
                WinNamedMapping("LMU_Data")


if __name__ == "__main__":
    unittest.main()
