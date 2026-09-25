from __future__ import annotations

import math

import pytest

from fca.concept.brief import Brief, resolve
from fca.concept.layout import build_layout
from fca.concept.mep import build_mep
from fca.concept.program import build_program, load_template


@pytest.fixture(scope="module")
def mep():
    values, _ = resolve(
        Brief(
            plant_type="industrial",
            built_up_area_m2=4000,
            lines_now=2,
            lines_future=1,
            staff_per_shift=70,
        )
    )
    tpl = load_template("industrial")
    lay = build_layout(values, build_program(values, tpl), tpl)
    return build_mep(lay, values, "industrial"), lay


def _near_route(point, routes, tol=0.35):
    """True if a point lies on (or at a vertex of) one of the routes, in plan."""
    x, y = point[0], point[1]
    for r in routes:
        for a, b in zip(r.points, r.points[1:], strict=False):
            ax, ay, bx, by = a[0], a[1], b[0], b[1]
            L = math.hypot(bx - ax, by - ay)
            if L < 1e-9:
                if math.hypot(x - ax, y - ay) <= tol:
                    return True
                continue
            t = max(0, min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L**2))
            if math.hypot(x - (ax + t * (bx - ax)), y - (ay + t * (by - ay))) <= tol:
                return True
    return False


def test_every_luminaire_is_on_a_lighting_circuit(mep):
    m, _ = mep
    circuits = [r for r in m.routes if r.kind == "Lighting circuit"]
    lights = [i for i in m.items if i.kind.startswith("LED")]
    assert circuits and all(_near_route(i.at, circuits) for i in lights)


def test_every_sprinkler_head_is_piped(mep):
    m, _ = mep
    pipes = [r for r in m.routes if r.kind.startswith("Sprinkler")]
    heads = [i for i in m.items if i.kind == "Sprinkler"]
    assert heads and all(_near_route(i.at, pipes) for i in heads)


def test_every_outlet_has_cold_water_and_wet_rooms_have_hot(mep):
    m, _ = mep
    cold = [r for r in m.routes if r.kind == "Cold water branch"]
    outlets = [i for i in m.items if i.kind == "Outlet"]
    assert all(_near_route(i.at, cold) for i in outlets)
    assert any(r.kind == "Hot water" for r in m.routes)
    assert sum(1 for i in m.items if i.kind == "Water heater") >= 4


def test_fire_alarm_loop_visits_every_detector(mep):
    m, _ = mep
    loop = next(r for r in m.routes if r.kind == "Fire alarm loop")
    detectors = [i for i in m.items if i.kind == "Fire detector"]
    assert loop.points[0] == loop.points[-1]  # closed loop back to the panel
    assert all(_near_route(d.at, [loop], tol=0.01) for d in detectors)


def test_lines_get_power_air_and_gas(mep):
    m, _ = mep
    kinds = [r.kind for r in m.routes]
    assert kinds.count("Process power feeder") == 3  # 2 now + 1 future
    assert kinds.count("Air drop") == 3 and kinds.count("Gas branch to oven") == 3


def test_routed_quantities_are_measured(mep):
    m, _ = mep
    q = {x.description: x for x in m.quantities}
    lighting = sum(r.length for r in m.routes if r.kind == "Lighting circuit")
    assert q["Lighting circuits, 3 × 2.5 mm² in containment"].qty == pytest.approx(
        lighting, abs=0.1
    )
    assert q["Supply air ductwork (galvanised)"].qty > 50
    assert "Sprinkler pipework (feed, cross mains, ranges)" in q


def test_runs_are_orthogonal(mep):
    m, _ = mep
    diagonal = [
        (r.kind, a, b)
        for r in m.routes
        for a, b in zip(r.points, r.points[1:], strict=False)
        if abs(a[0] - b[0]) > 1e-3 and abs(a[1] - b[1]) > 1e-3
    ]
    assert diagonal == []  # services run along x and y, like on site
