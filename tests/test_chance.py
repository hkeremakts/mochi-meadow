"""The shapes of chance behave as they should."""
import datetime
import random
import statistics
import unittest

from habitat import chance


def draws(spec, n=4000, seed=1):
    rng = random.Random(seed)
    return [chance.sample(rng, spec) for _ in range(n)]


class Shapes(unittest.TestCase):
    def test_lognormal_is_skewed_with_the_typical_value_in_the_middle(self):
        xs = draws({"typical": 20, "spread": 0.6})
        self.assertAlmostEqual(statistics.median(xs), 20, delta=1.5)
        self.assertGreater(statistics.mean(xs), statistics.median(xs))      # a long tail of long ones
        self.assertTrue(all(x > 0 for x in xs))

    def test_limits_hold(self):
        xs = draws({"typical": 20, "spread": 1.5, "min": 5, "max": 60})
        self.assertGreaterEqual(min(xs), 5)
        self.assertLessEqual(max(xs), 60)

    def test_normal_is_even_either_side(self):
        xs = draws({"mean": 7.5, "sd": 0.25})
        self.assertAlmostEqual(statistics.mean(xs), 7.5, delta=0.02)
        self.assertAlmostEqual(statistics.stdev(xs), 0.25, delta=0.02)

    def test_exponential_waits(self):
        xs = draws({"mean_wait": 30})
        self.assertAlmostEqual(statistics.mean(xs), 30, delta=2)
        self.assertGreater(sum(x < 30 for x in xs), len(xs) / 2)          # mostly short waits

    def test_weibull_boredom_builds(self):
        # With shape > 1 very short stays are rare: she doesn't give up at once.
        xs = draws({"scale": 40, "shape": 2.2})
        self.assertLess(sum(x < 8 for x in xs) / len(xs), 0.05)

    def test_a_mixture_has_both_kinds(self):
        xs = draws({"mix": [{"weight": 0.65, "typical": 4, "spread": 0.3},
                            {"weight": 0.35, "typical": 16, "spread": 0.3}]})
        short = sum(x < 8 for x in xs) / len(xs)
        self.assertAlmostEqual(short, 0.65, delta=0.05)

    def test_beta_poisson_pareto(self):
        self.assertTrue(all(0 <= x <= 1 for x in draws({"a": 9, "b": 1.2})))
        counts = [chance.count(random.Random(i), {"poisson": 4.5}) for i in range(3000)]
        self.assertAlmostEqual(statistics.mean(counts), 4.5, delta=0.2)
        tail = draws({"pareto": 2.2, "scale": 5, "max": 40})
        self.assertGreaterEqual(min(tail), 5)
        self.assertLessEqual(max(tail), 40)

    def test_old_style_ranges_still_work(self):
        xs = draws([4, 10])
        self.assertTrue(all(4 <= x <= 10 for x in xs))
        self.assertEqual(chance.sample(random.Random(), 7), 7)

    def test_spec_recognition(self):
        self.assertTrue(chance.is_spec({"typical": 3}))
        self.assertTrue(chance.is_spec([1, 2]))
        self.assertFalse(chance.is_spec({"cloud": 0.4}))
        self.assertFalse(chance.is_spec(True))


class Clock(unittest.TestCase):
    def test_a_peak_is_smooth_and_wraps_past_midnight(self):
        self.assertAlmostEqual(chance.peak(23.5, 23.5, 2.0), 1.0)
        self.assertAlmostEqual(chance.peak(1.5, 23.5, 2.0), chance.peak(21.5, 23.5, 2.0))
        self.assertLess(chance.peak(12.0, 23.5, 2.0), 0.01)
        steps = [chance.peak(19 + i / 10, 20.6, 0.8) for i in range(30)]
        jumps = [abs(b - a) for a, b in zip(steps, steps[1:])]
        self.assertLess(max(jumps), 0.15, "no switch flicking on")

    def test_two_peaks_dawn_and_dusk(self):
        spec = [{"peak": 6.0, "width": 1.0}, {"peak": 20.0, "width": 1.0}]
        self.assertGreater(chance.peaks(6.0, spec), 0.9)
        self.assertGreater(chance.peaks(20.0, spec), 0.9)
        self.assertLess(chance.peaks(13.0, spec), 0.05)


class Processes(unittest.TestCase):
    def test_hawkes_arrivals_cluster(self):
        """Gaps between arrivals vary far more than a steady process's."""
        rng = random.Random(4)
        h = chance.Hawkes(rng, mean_wait=100, excite=0.02, memory=60)
        times, t = [], 0.0
        while len(times) < 400:
            t += 1.0
            if h.step(1.0):
                times.append(t)
        gaps = [b - a for a, b in zip(times, times[1:])]
        cv = statistics.stdev(gaps) / statistics.mean(gaps)
        self.assertGreater(cv, 1.2)        # a steady (Poisson) process gives about 1

    def test_drift_wanders_but_comes_home(self):
        d = chance.Drift(random.Random(2), mean=0.0, sd=0.3, timescale=60, value=2.0)
        for _ in range(600):
            d.step(1.0)
        values = [d.step(1.0) for _ in range(3000)]
        self.assertAlmostEqual(statistics.mean(values), 0.0, delta=0.1)
        self.assertAlmostEqual(statistics.pstdev(values), 0.3, delta=0.08)
        steps = [abs(b - a) for a, b in zip(values, values[1:])]
        self.assertLess(statistics.mean(steps), 0.1, "smooth, not jumpy")


class Days(unittest.TestCase):
    SPEC = {"volatility": {"typical": 1.0, "spread": 0.4}, "busyness": {"typical": 1.0, "spread": 0.3},
            "energy": {"mean": 1.0, "sd": 0.08}, "spread": {"typical": 1.0, "spread": 0.25}}

    def test_a_day_keeps_its_character_and_days_differ(self):
        a, b = chance.Day(5, self.SPEC), chance.Day(5, self.SPEC)
        a.update(datetime.date(2026, 10, 20))
        b.update(datetime.date(2026, 10, 20))
        self.assertEqual((a.volatility, a.busyness, a.energy), (b.volatility, b.busyness, b.energy))
        vols = set()
        for i in range(20):
            a.update(datetime.date(2026, 10, 1) + datetime.timedelta(days=i))
            vols.add(round(a.volatility, 3))
        self.assertGreater(len(vols), 15)
        self.assertIn(a.describe().split(" day")[0].split()[-1], ("changeable", "settled", "ordinary"))


if __name__ == "__main__":
    unittest.main()
