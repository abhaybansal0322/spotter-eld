"""Pure mile-to-coordinate lookup, bisect over cumulative distance."""
import math
from bisect import bisect_right

EARTH_RADIUS_MI = 3958.8


def _haversine_mi(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


class RouteIndex:
    """Mile positions along a route polyline, built once, answered by binary search."""

    def __init__(self, geometry, total_miles):
        """geometry is an ordered list of (lat, lng). The haversine lengths are scaled so the last vertex sits
        at total_miles, because ORS reports road distance and the polyline is a simplification of the road."""
        if not geometry:
            raise ValueError("geometry must contain at least one vertex")
        self._points = [tuple(point) for point in geometry]

        cumulative = [0.0]
        for a, b in zip(self._points, self._points[1:]):
            cumulative.append(cumulative[-1] + _haversine_mi(a, b))

        length = cumulative[-1]
        if length > 0:
            scale = total_miles / length
            cumulative = [mile * scale for mile in cumulative]
            cumulative[-1] = float(total_miles)
        self._miles = cumulative

    def coordinate_at(self, mile):
        """(lat, lng) at a road mile, linearly interpolated between the bracketing vertices, clamped to the route."""
        mile = min(max(mile, 0.0), self._miles[-1])
        upper = bisect_right(self._miles, mile)
        if upper == len(self._miles):
            return self._points[-1]
        # miles[upper - 1] <= mile < miles[upper], so the span is never zero, even across duplicate vertices.
        low_mile, high_mile = self._miles[upper - 1], self._miles[upper]
        fraction = (mile - low_mile) / (high_mile - low_mile)
        (lat1, lng1), (lat2, lng2) = self._points[upper - 1], self._points[upper]
        return (lat1 + (lat2 - lat1) * fraction, lng1 + (lng2 - lng1) * fraction)


def road_at(mile, named_points):
    """The road the driver is on at mile: the last (mile, road) step starting at or before it.

    A containment lookup with no distance threshold, because one interstate step can run hundreds of miles.
    None only when mile precedes the first named step. named_points must be sorted by mile, as ORS steps are.
    """
    position = bisect_right(named_points, mile, key=lambda point: point[0])
    return named_points[position - 1][1] if position else None


def simplify(points, epsilon):
    """Douglas-Peucker in coordinate space: the subset of points, first and last always kept, that stays within
    epsilon of the original line. Iterative with an explicit stack, so a 50,000-point route cannot exhaust recursion."""
    points = list(points)
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    spans = [(0, len(points) - 1)]
    while spans:
        first, last = spans.pop()
        farthest, farthest_distance = None, epsilon
        for index in range(first + 1, last):
            distance = _distance_to_segment(points[index], points[first], points[last])
            if distance > farthest_distance:
                farthest, farthest_distance = index, distance
        if farthest is not None:
            keep[farthest] = True
            spans.append((first, farthest))
            spans.append((farthest, last))
    return [point for point, kept in zip(points, keep) if kept]


def _distance_to_segment(point, start, end):
    (py, px), (ay, ax), (by, bx) = point, start, end
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_squared))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
