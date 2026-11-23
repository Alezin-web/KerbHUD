import os
import tempfile
import unittest

from kerbhud.core.assists import assist_on, lockup, pulse
from kerbhud.core.history import TelemetryHistory
from kerbhud.core.model import Inputs, Sim, Snapshot
from kerbhud.core.wheels import get_wheel_image, get_wheel_style, valid_image


class LockupTest(unittest.TestCase):
    def test_needs_brake_speed_and_real_slip(self):
        self.assertTrue(lockup(50.0, 0.8, [0.0, 0.0, 20.0, 0.0]))       # roda deslizando 40% da velocidade
        self.assertTrue(lockup(50.0, 0.8, [-20.0]))                      # o sinal não importa
        self.assertFalse(lockup(50.0, 0.8, [2.0, 3.0, 1.0, 0.0]))        # frenagem normal (ABS/limite): sem travar
        self.assertFalse(lockup(50.0, 0.0, [40.0]))                      # sem freio: patinando, não travando
        self.assertFalse(lockup(3.0, 0.9, [3.0]))                        # devagar demais: razão instável
        self.assertFalse(lockup(50.0, 0.8, [float("nan"), float("inf")]))  # lixo do jogo não vira alarme

    def test_assist_and_pulse(self):
        self.assertTrue(assist_on(True, None) and assist_on(None, True))
        self.assertFalse(assist_on(None, None) or assist_on(False, False))  # sem informação: nada aparece
        self.assertTrue(all(0.6 <= pulse(t / 10) <= 1.0 for t in range(100)))


class HistoryFlagsTest(unittest.TestCase):
    def test_flags_are_recorded_per_sample(self):
        h = TelemetryHistory()
        on = Snapshot(sim=Sim.LMU, connected=True, inputs=Inputs(brake=1.0, abs_active=True, lockup=True))
        off = Snapshot(sim=Sim.LMU, connected=True, inputs=Inputs(brake=0.5))
        h.on_snapshot(on, now=1.0)
        h.on_snapshot(off, now=1.1)
        a, b = h.window(5.0)
        self.assertEqual((a.abs_on, a.tc_on, a.lock), (True, False, True))
        self.assertEqual((b.abs_on, b.tc_on, b.lock), (False, False, False))


class WheelOptionsTest(unittest.TestCase):
    def test_style_defaults_and_validation(self):
        self.assertEqual(get_wheel_style({}), "classic")
        self.assertEqual(get_wheel_style({"wheel_style": "gt"}), "gt")
        self.assertEqual(get_wheel_style({"wheel_style": "xx"}), "classic")
        self.assertEqual(get_wheel_image({"wheel_image": 3}), "")

    def test_image_validation(self):
        with tempfile.TemporaryDirectory() as d:
            ok = os.path.join(d, "v.png")
            open(ok, "wb").write(b"x")
            bad = os.path.join(d, "v.exe")
            open(bad, "wb").write(b"x")
            big = os.path.join(d, "big.jpg")
            with open(big, "wb") as f:
                f.truncate(9 * 1024 * 1024)
            self.assertTrue(valid_image(ok))
            self.assertFalse(valid_image(bad))   # só imagens
            self.assertFalse(valid_image(big))   # grande demais
            self.assertFalse(valid_image(os.path.join(d, "nao-existe.png")))
            self.assertFalse(valid_image(""))


class LmuInputsTest(unittest.TestCase):
    def test_lmu_reads_abs_tc_and_derives_lockup(self):
        from types import SimpleNamespace as NS
        from kerbhud.providers.lmu import LmuProvider

        def tele(abs_on, tc_on, patch, brake=0.9):
            return NS(mLocalVel=NS(x=0.0, y=0.0, z=-50.0), mEngineMaxRPM=8000.0, mEngineRPM=6000.0,
                      mPhysicalSteeringWheelRange=540.0, mUnfilteredSteering=0.1, mUnfilteredThrottle=0.0,
                      mUnfilteredBrake=brake, mUnfilteredClutch=0.0, mGear=3, mABSActive=abs_on, mTCActive=tc_on,
                      mWheels=[NS(mLongitudinalPatchVel=v) for v in patch])
        i = LmuProvider._inputs(tele(True, False, [1, 1, 1, 1]))
        self.assertEqual((i.abs_active, i.tc_active, i.lockup), (True, False, False))
        i = LmuProvider._inputs(tele(False, True, [0, 0, 30, 0]))
        self.assertEqual((i.abs_active, i.tc_active, i.lockup), (False, True, True))


if __name__ == "__main__":
    unittest.main()
