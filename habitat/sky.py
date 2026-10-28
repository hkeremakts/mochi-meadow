"""The real sky over the meadow: where the sun and moon are, the moon's
phase, and the season, all worked out offline from the date, the time and
a rough location.

A screensaver can't ask for Location Services, so the location is a guess
from the computer's time zone: the zone's main city, or failing that a
longitude from the UTC offset.  That is close enough for sunrise to land
within a few minutes of the real one.

Accuracy is about a degree for the sun and two for the moon: plenty for
light and shadow, not for navigation.
"""

import datetime
import math
import os

RAD = math.pi / 180
J2000 = datetime.datetime(2000, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)

# Main city of common time zones: (latitude, longitude).
ZONES = {
    "Europe/Istanbul": (41.0, 29.0), "Europe/London": (51.5, -0.1), "Europe/Dublin": (53.3, -6.3),
    "Europe/Lisbon": (38.7, -9.1), "Europe/Madrid": (40.4, -3.7), "Europe/Paris": (48.9, 2.4),
    "Europe/Brussels": (50.8, 4.4), "Europe/Amsterdam": (52.4, 4.9), "Europe/Berlin": (52.5, 13.4),
    "Europe/Zurich": (47.4, 8.5), "Europe/Rome": (41.9, 12.5), "Europe/Vienna": (48.2, 16.4),
    "Europe/Prague": (50.1, 14.4), "Europe/Warsaw": (52.2, 21.0), "Europe/Budapest": (47.5, 19.0),
    "Europe/Copenhagen": (55.7, 12.6), "Europe/Oslo": (59.9, 10.8), "Europe/Stockholm": (59.3, 18.1),
    "Europe/Helsinki": (60.2, 24.9), "Europe/Tallinn": (59.4, 24.8), "Europe/Riga": (56.9, 24.1),
    "Europe/Vilnius": (54.7, 25.3), "Europe/Athens": (38.0, 23.7), "Europe/Sofia": (42.7, 23.3),
    "Europe/Bucharest": (44.4, 26.1), "Europe/Belgrade": (44.8, 20.5), "Europe/Kiev": (50.5, 30.5),
    "Europe/Kyiv": (50.5, 30.5), "Europe/Minsk": (53.9, 27.6), "Europe/Moscow": (55.8, 37.6),
    "Asia/Nicosia": (35.2, 33.4), "Asia/Jerusalem": (31.8, 35.2), "Asia/Beirut": (33.9, 35.5),
    "Asia/Amman": (32.0, 35.9), "Asia/Baghdad": (33.3, 44.4), "Asia/Tehran": (35.7, 51.4),
    "Asia/Riyadh": (24.7, 46.7), "Asia/Dubai": (25.2, 55.3), "Asia/Baku": (40.4, 49.9),
    "Asia/Tbilisi": (41.7, 44.8), "Asia/Yerevan": (40.2, 44.5), "Asia/Karachi": (24.9, 67.0),
    "Asia/Kolkata": (22.6, 88.4), "Asia/Calcutta": (22.6, 88.4), "Asia/Kathmandu": (27.7, 85.3),
    "Asia/Dhaka": (23.8, 90.4), "Asia/Bangkok": (13.8, 100.5), "Asia/Jakarta": (-6.2, 106.8),
    "Asia/Singapore": (1.3, 103.8), "Asia/Kuala_Lumpur": (3.1, 101.7), "Asia/Manila": (14.6, 121.0),
    "Asia/Ho_Chi_Minh": (10.8, 106.7), "Asia/Hong_Kong": (22.3, 114.2), "Asia/Shanghai": (31.2, 121.5),
    "Asia/Taipei": (25.0, 121.6), "Asia/Seoul": (37.6, 127.0), "Asia/Tokyo": (35.7, 139.7),
    "Asia/Almaty": (43.2, 76.9), "Asia/Tashkent": (41.3, 69.3), "Australia/Perth": (-31.9, 115.9),
    "Australia/Adelaide": (-34.9, 138.6), "Australia/Darwin": (-12.5, 130.8),
    "Australia/Brisbane": (-27.5, 153.0), "Australia/Sydney": (-33.9, 151.2),
    "Australia/Melbourne": (-37.8, 145.0), "Australia/Hobart": (-42.9, 147.3),
    "Pacific/Auckland": (-36.8, 174.8), "Pacific/Honolulu": (21.3, -157.9), "Africa/Cairo": (30.0, 31.2),
    "Africa/Casablanca": (33.6, -7.6), "Africa/Algiers": (36.8, 3.1), "Africa/Tunis": (36.8, 10.2),
    "Africa/Lagos": (6.5, 3.4), "Africa/Nairobi": (-1.3, 36.8), "Africa/Johannesburg": (-26.2, 28.0),
    "Atlantic/Reykjavik": (64.1, -21.9), "America/St_Johns": (47.6, -52.7),
    "America/Halifax": (44.6, -63.6), "America/Toronto": (43.7, -79.4), "America/Montreal": (45.5, -73.6),
    "America/New_York": (40.7, -74.0), "America/Detroit": (42.3, -83.0), "America/Chicago": (41.9, -87.6),
    "America/Winnipeg": (49.9, -97.1), "America/Denver": (39.7, -105.0), "America/Phoenix": (33.4, -112.1),
    "America/Edmonton": (53.5, -113.5), "America/Vancouver": (49.3, -123.1),
    "America/Los_Angeles": (34.1, -118.2), "America/Anchorage": (61.2, -149.9),
    "America/Mexico_City": (19.4, -99.1), "America/Bogota": (4.7, -74.1), "America/Lima": (-12.0, -77.0),
    "America/Caracas": (10.5, -66.9), "America/Santiago": (-33.4, -70.7),
    "America/Argentina/Buenos_Aires": (-34.6, -58.4), "America/Buenos_Aires": (-34.6, -58.4),
    "America/Sao_Paulo": (-23.6, -46.6), "America/Montevideo": (-34.9, -56.2),
}
SOUTHERN_PREFIXES = ("Australia/", "Pacific/Auckland", "America/Argentina", "America/Santiago",
                     "America/Sao_Paulo", "America/Montevideo", "Africa/Johannesburg")


def system_zone():
    """The IANA name of the computer's time zone, or None."""
    name = os.environ.get("TZ", "").lstrip(":")
    if "/" in name and not name.startswith("/"):
        return name
    try:
        target = os.path.realpath("/etc/localtime")
    except OSError:
        return None
    marker = "zoneinfo/"
    if marker in target:
        return target.split(marker, 1)[1]
    return None


def guess_place(zone=None, utc_offset_hours=None):
    """(latitude, longitude) for a time zone name; a longitude from the UTC
    offset when the zone is unknown."""
    zone = zone if zone is not None else system_zone()
    if zone in ZONES:
        return ZONES[zone]
    if utc_offset_hours is None:
        off = datetime.datetime.now().astimezone().utcoffset()
        utc_offset_hours = off.total_seconds() / 3600 if off else 0.0
    south = bool(zone) and zone.startswith(SOUTHERN_PREFIXES)
    return (-35.0 if south else 45.0), max(-180.0, min(180.0, utc_offset_hours * 15.0))


def parse_place(text):
    """'41.0,29.0' -> (41.0, 29.0)."""
    lat, lon = (float(part) for part in text.split(","))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"not a latitude,longitude: {text}")
    return lat, lon


# --------------------------------------------------------------------------
# Positions

def _days(utc):
    return (utc - J2000).total_seconds() / 86400.0


def _obliquity(d):
    return (23.439 - 0.00000036 * d) * RAD


def _sun_ecliptic(d):
    g = (357.529 + 0.98560028 * d) * RAD
    q = 280.459 + 0.98564736 * d
    return (q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360.0


def _moon_ecliptic(d):
    L = 218.316 + 13.176396 * d
    M = (134.963 + 13.064993 * d) * RAD
    F = (93.272 + 13.229350 * d) * RAD
    return (L + 6.289 * math.sin(M)) % 360.0, 5.128 * math.sin(F)


def _altaz(d, ecl_lon, ecl_lat, lat, lon):
    """Ecliptic coordinates (degrees) -> (altitude, azimuth) in degrees.
    Azimuth runs from north through east."""
    e = _obliquity(d)
    lam, beta = ecl_lon * RAD, ecl_lat * RAD
    ra = math.atan2(math.sin(lam) * math.cos(e) - math.tan(beta) * math.sin(e), math.cos(lam))
    dec = math.asin(math.sin(beta) * math.cos(e) + math.cos(beta) * math.sin(e) * math.sin(lam))
    gmst = (280.46061837 + 360.98564736629 * d) % 360.0
    ha = (gmst + lon) * RAD - ra
    phi = lat * RAD
    alt = math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha), math.tan(dec) * math.cos(phi) - math.sin(phi) * math.cos(ha))
    return alt / RAD, (az / RAD) % 360.0


def sun_altaz(utc, lat, lon):
    d = _days(utc)
    return _altaz(d, _sun_ecliptic(d), 0.0, lat, lon)


def moon_altaz(utc, lat, lon):
    d = _days(utc)
    mlon, mlat = _moon_ecliptic(d)
    return _altaz(d, mlon, mlat, lat, lon)


# Venus, from mean orbital elements (Standish, JPL; good to a degree or so
# for centuries around now): a, e, inclination, mean longitude and its rate
# per century, longitude of perihelion, of the ascending node (degrees).
_ELEMENTS = {
    "venus": (0.72333566, 0.00677672, 3.39467605, 181.97909950, 58517.81538729, 131.60246718, 76.67984255),
    "earth": (1.00000261, 0.01671123, 0.0, 100.46457166, 35999.37244981, 102.93768193, 0.0),
}


def _heliocentric(name, T):
    a, e, inc, L0, rate, peri, node = _ELEMENTS[name]
    M = math.radians((L0 + rate * T - peri) % 360.0)
    E = M
    for _ in range(6):
        E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    x, y = a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
    w, n, i = math.radians(peri - node), math.radians(node), math.radians(inc)
    cw, sw, cn, sn, ci, si = math.cos(w), math.sin(w), math.cos(n), math.sin(n), math.cos(i), math.sin(i)
    return ((cw * cn - sw * sn * ci) * x + (-sw * cn - cw * sn * ci) * y,
            (cw * sn + sw * cn * ci) * x + (-sw * sn + cw * cn * ci) * y,
            sw * si * x + cw * si * y)


def _venus_ecliptic(d):
    T = d / 36525.0
    vx, vy, vz = _heliocentric("venus", T)
    ex, ey, ez = _heliocentric("earth", T)
    x, y, z = vx - ex, vy - ey, vz - ez
    return math.degrees(math.atan2(y, x)) % 360.0, math.degrees(math.atan2(z, math.hypot(x, y)))


def venus_altaz(utc, lat, lon):
    d = _days(utc)
    vlon, vlat = _venus_ecliptic(d)
    return _altaz(d, vlon, vlat, lat, lon)


def venus_elongation(utc):
    """Degrees from the sun along the ecliptic: east (+) is the evening
    star, west (-) the morning star."""
    d = _days(utc)
    return (_venus_ecliptic(d)[0] - _sun_ecliptic(d) + 180.0) % 360.0 - 180.0


# Lunar eclipses (NASA, eclipse.gsfc.nasa.gov): greatest eclipse (TD, within
# a minute or so of UT), umbral magnitude, and how many minutes the partial
# and the total phases last.  Penumbral eclipses, and partials too shallow to
# see, are left out.
ECLIPSES = [
    ("2026-03-03 11:35", 1.151, 207, 58), ("2026-08-28 04:14", 0.930, 198, 0),
    ("2028-07-06 18:21", 0.389, 141, 0), ("2028-12-31 16:53", 1.246, 209, 71),
    ("2029-06-26 03:23", 1.844, 220, 102), ("2029-12-20 22:43", 1.117, 213, 54),
    ("2030-06-15 18:35", 0.502, 144, 0), ("2032-04-25 15:15", 1.191, 211, 66),
    ("2032-10-18 19:04", 1.103, 196, 47), ("2033-04-14 19:14", 1.094, 215, 49),
    ("2033-10-08 10:56", 1.350, 202, 79), ("2036-02-11 22:13", 1.299, 202, 74),
    ("2036-08-07 02:53", 1.454, 231, 95), ("2037-01-31 14:02", 1.207, 197, 64),
    ("2037-07-27 04:10", 0.809, 192, 0), ("2039-06-06 18:54", 0.885, 179, 0),
    ("2039-11-30 16:56", 0.943, 206, 0), ("2040-05-26 11:46", 1.535, 211, 92),
    ("2040-11-18 19:05", 1.397, 220, 88),
]
_ECLIPSE_TIMES = [(datetime.datetime.fromisoformat(t).replace(tzinfo=datetime.timezone.utc), m, p, tot)
                  for t, m, p, tot in ECLIPSES]


def eclipse_at(utc):
    """(shadow, total): how much of the moon the earth's shadow covers now
    (0..1), and whether it is wholly inside it."""
    for when, mag, partial, total in _ECLIPSE_TIMES:
        minutes = abs((utc - when).total_seconds()) / 60.0
        if minutes < partial / 2:
            if minutes < total / 2:
                return 1.0, True
            edge = partial / 2
            inner = total / 2
            return min(1.0, mag) * (edge - minutes) / (edge - inner), False
    return 0.0, False


def moon_phase(utc):
    """(age, lit): age 0 = new, 0.5 = full, back to 1; lit is the
    illuminated fraction of the disc."""
    d = _days(utc)
    elong = (_moon_ecliptic(d)[0] - _sun_ecliptic(d)) % 360.0
    return elong / 360.0, (1.0 - math.cos(elong * RAD)) / 2.0


# --------------------------------------------------------------------------
# The day's shape

# Behaviour throughout the meadow is written against one "standard" day:
# first light at 4.4, sunrise 6.2, noon 12.8, sunset 19.4, full dark at
# 21.2.  The real day is mapped onto it, so a December evening at 17:00
# already counts as dusk, and fireflies wait for a late June dark.
STANDARD = (0.8, 4.4, 6.2, 12.8, 19.4, 21.2, 24.8)
SUNRISE_ALT = -0.833   # refraction and the sun's radius
DARK_ALT = -18.0


def _crossings(samples, level):
    """Times at which the sampled altitude crosses ``level`` going up and
    going down, or None."""
    up = down = None
    for (h0, a0), (h1, a1) in zip(samples, samples[1:]):
        if a0 < level <= a1 and up is None:
            up = h0 + (h1 - h0) * (level - a0) / (a1 - a0)
        elif a0 >= level > a1 and down is None:
            down = h0 + (h1 - h0) * (a0 - level) / (a0 - a1)
    return up, down


class DayShape:
    """Sunrise, sunset, noon and dark on one local date."""

    STEP = 0.1  # hours between samples

    def __init__(self, date, lat, lon, utc_offset):
        self.date = date
        start = datetime.datetime.combine(date, datetime.time()) - datetime.timedelta(hours=utc_offset)
        start = start.replace(tzinfo=datetime.timezone.utc)
        n = int(24 / self.STEP) + 1
        samples = [(i * self.STEP, sun_altaz(start + datetime.timedelta(hours=i * self.STEP), lat, lon)[0])
                   for i in range(n)]
        self.noon = max(samples, key=lambda s: s[1])[0]
        self.high = max(a for _, a in samples)
        self.low = min(a for _, a in samples)
        self.sunrise, self.sunset = _crossings(samples, SUNRISE_ALT)
        self.dawn, self.dusk = _crossings(samples, DARK_ALT)
        rise = self.sunrise if self.sunrise is not None else self.noon - 6.6
        sset = self.sunset if self.sunset is not None else self.noon + 6.6
        if rise > self.noon or sset < self.noon:
            rise, sset = self.noon - 6.6, self.noon + 6.6
        dawn = self.dawn if self.dawn is not None and self.dawn < rise else rise - 1.8
        dusk = self.dusk if self.dusk is not None and self.dusk > sset else sset + 1.8
        real = [self.noon - 12, dawn, rise, self.noon, sset, dusk, self.noon + 12]
        for i in range(1, len(real)):
            real[i] = max(real[i], real[i - 1] + 0.05)
        self.anchors = real

    def standard_hour(self, hour):
        """Map a real local hour onto the standard day."""
        real = self.anchors
        h = hour
        if h < real[0]:
            h += 24
        elif h >= real[-1]:
            h -= 24
        for (r0, s0), (r1, s1) in zip(zip(real, STANDARD), zip(real[1:], STANDARD[1:])):
            if r0 <= h <= r1:
                return (s0 + (s1 - s0) * (h - r0) / (r1 - r0)) % 24.0
        return hour % 24.0


# --------------------------------------------------------------------------
# Seasons

SEASONS = ("winter", "spring", "summer", "autumn")


def year_phase(date, lat):
    """0..1 through the year, starting on 1 January in the north and on
    1 July in the south, so the same phase means the same season."""
    doy = date.timetuple().tm_yday - 1
    if lat < 0:
        doy = (doy + 182) % 365
    return (doy % 365) / 365.0


def season_of(date, lat):
    """Meteorological season: winter is Dec-Feb in the north."""
    month = date.month if lat >= 0 else (date.month + 5) % 12 + 1
    return SEASONS[(month % 12) // 3]


def mean_temperature(date, lat):
    """A rough daily mean (Celsius) for the latitude and the date: coldest
    in mid-January, warmest in mid-July (flipped in the south)."""
    a = abs(lat)
    mean = 30.0 - 0.4 * a
    swing = max(1.5, min(16.0, a / 4.0))
    p = year_phase(date, lat)
    return mean - swing * math.cos(2 * math.pi * (p - 0.04))


class Sky:
    """The sky at the clock's moment, recomputed as the clock moves."""

    def __init__(self, place=None, utc_offset=None):
        self.place = tuple(place) if place is not None else guess_place()
        self._fixed_offset = utc_offset   # hours; None = the system's offset
        self._shape = None
        self.sun_alt = 0.0
        self.sun_az = 0.0
        self.rising = True
        self.moon_alt = -10.0
        self.moon_az = 0.0
        self.moon_age = 0.0
        self.moon_lit = 0.0
        self.venus_alt = -10.0
        self.venus_az = 0.0
        self.venus_elong = 0.0
        self.eclipse = 0.0        # 0..1 of the moon in the earth's shadow
        self.eclipse_total = False
        self.standard_hour = 0.0
        self.date = None
        self.season = "spring"
        self.year_phase = 0.0
        self._last = None

    @property
    def lat(self):
        return self.place[0]

    def offset_at(self, moment):
        if self._fixed_offset is not None:
            return self._fixed_offset
        off = moment.astimezone().utcoffset()
        return off.total_seconds() / 3600 if off else 0.0

    def shape(self, date, offset):
        if self._shape is None or self._shape.date != date:
            self._shape = DayShape(date, self.place[0], self.place[1], offset)
        return self._shape

    def update(self, moment):
        """``moment`` is a naive local datetime."""
        if self._last is not None and abs((moment - self._last).total_seconds()) < 20:
            return  # nothing in the sky moves visibly in 20 seconds
        self._last = moment
        offset = self.offset_at(moment)
        utc = (moment - datetime.timedelta(hours=offset)).replace(tzinfo=datetime.timezone.utc)
        lat, lon = self.place
        alt, az = sun_altaz(utc, lat, lon)
        later, _ = sun_altaz(utc + datetime.timedelta(minutes=10), lat, lon)
        self.sun_alt, self.sun_az, self.rising = alt, az, later >= alt
        self.moon_alt, self.moon_az = moon_altaz(utc, lat, lon)
        self.moon_age, self.moon_lit = moon_phase(utc)
        self.venus_alt, self.venus_az = venus_altaz(utc, lat, lon)
        self.venus_elong = venus_elongation(utc)
        self.eclipse, self.eclipse_total = eclipse_at(utc)
        date = moment.date()
        hour = moment.hour + moment.minute / 60 + moment.second / 3600
        self.standard_hour = self.shape(date, offset).standard_hour(hour)
        if date != self.date:
            self.date = date
            self.season = season_of(date, lat)
            self.year_phase = year_phase(date, lat)

    def invalidate(self):
        self._last = None

    @property
    def day(self):
        return self._shape

    @property
    def moonlight(self):
        """0..1: how much the moon lights the meadow (before clouds)."""
        if self.moon_alt <= 0:
            return 0.0
        return self.moon_lit * min(1.0, self.moon_alt / 25.0) ** 0.7 * (1.0 - 0.85 * self.eclipse)

    @property
    def venus_shows(self):
        """Venus as the evening or morning star: up, clear of the sun's
        glare, and the sky dark enough."""
        return self.venus_alt > 3 and self.sun_alt < -4 and abs(self.venus_elong) > 10

    @property
    def full_moon(self):
        return self.moon_lit > 0.97
