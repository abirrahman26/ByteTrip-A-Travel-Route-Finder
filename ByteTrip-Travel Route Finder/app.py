"""ByteTrip: Travel Route Finder web application.

Optimizes inter-district travel paths across Bangladesh using Dijkstra's Algorithm
for weighted metrics (fare, distance, duration) and Breadth-First Search (BFS)
for minimum transfer hops.
"""

from __future__ import annotations

import heapq
import os
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from flask import Flask, abort, jsonify, render_template, request, send_file

try:
    from district_data import DISTRICT_COORDINATES, POPULAR_ROUTES
except ImportError:
    from .district_data import DISTRICT_COORDINATES, POPULAR_ROUTES


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "route_infos_clean.csv"


class Metric(str, Enum):
    """Routing optimization metrics."""
    COST = "cost"
    DISTANCE = "distance"
    TIME = "time"


METRIC_INDEX_MAP = {
    1: 0,
    2: 1,
    3: 2,
    "cost": 0,
    "distance": 1,
    "time": 2,
    Metric.COST: 0,
    Metric.DISTANCE: 1,
    Metric.TIME: 2,
}


def load_route_data(csv_path: Path = DATA_PATH) -> Tuple[pd.DataFrame, Dict[str, List[Tuple[str, int, int, int]]], List[str]]:
    """Load cleaned route data and construct an undirected adjacency list."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Cleaned route dataset not found at {csv_path}")

    dataframe = pd.read_csv(csv_path)
    adjacency_graph: Dict[str, List[Tuple[str, int, int, int]]] = defaultdict(list)

    for _, row in dataframe.iterrows():
        origin = str(row["from"])
        dest = str(row["to"])
        cost = int(row["cost"])
        distance = int(row["distance_km"])
        time_mins = int(row["time_minutes"])

        # Cleaned dataset stores one row per undirected pair; graph stores both directions.
        adjacency_graph[origin].append((dest, cost, distance, time_mins))
        adjacency_graph[dest].append((origin, cost, distance, time_mins))

    all_districts = sorted(set(dataframe["from"]).union(dataframe["to"]))
    return dataframe, adjacency_graph, all_districts


# Module-level defaults for backward compatibility
df, graph, districts = load_route_data(DATA_PATH)


def dijkstra(
    graph_data: Dict[str, List[Tuple[str, int, int, int]]],
    start: str,
    end: str,
    weight_metric: Union[int, str, Metric],
) -> Tuple[float, List[str]]:
    """Find the optimal weighted path between start and end nodes.

    Args:
        graph_data: Adjacency list mapping node to list of (neighbor, cost, distance, time).
        start: Origin district name.
        end: Destination district name.
        weight_metric: 1 / 'cost', 2 / 'distance', or 3 / 'time'.

    Returns:
        Tuple of (minimum total weight, list of district names along the optimal path).
    """
    if start not in graph_data or end not in graph_data:
        return float("inf"), []

    if start == end:
        return 0, [start]

    metric_idx = METRIC_INDEX_MAP.get(weight_metric)
    if metric_idx is None:
        raise ValueError(f"Invalid weight_metric: {weight_metric!r}. Expected 1, 2, 3 or 'cost', 'distance', 'time'.")

    distances: Dict[str, float] = {start: 0}
    parents: Dict[str, Optional[str]] = {start: None}
    priority_queue: List[Tuple[float, str]] = [(0, start)]

    while priority_queue:
        current_distance, current_node = heapq.heappop(priority_queue)

        if current_distance != distances[current_node]:
            continue

        if current_node == end:
            path: List[str] = []
            curr: Optional[str] = end
            while curr is not None:
                path.append(curr)
                curr = parents[curr]
            return current_distance, list(reversed(path))

        for neighbor, cost, route_dist, route_time in graph_data[current_node]:
            weight = (cost, route_dist, route_time)[metric_idx]
            candidate_distance = current_distance + weight

            if candidate_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = candidate_distance
                parents[neighbor] = current_node
                heapq.heappush(priority_queue, (candidate_distance, neighbor))

    return float("inf"), []


def bfs_fewest_legs(
    graph_data: Dict[str, List[Tuple[str, int, int, int]]],
    start: str,
    end: str,
) -> Tuple[Union[int, float], List[str]]:
    """Find the path with the fewest transfer hops (direct legs) using BFS.

    Returns:
        Tuple of (number of legs, list of district names along path).
    """
    if start not in graph_data or end not in graph_data:
        return float("inf"), []

    if start == end:
        return 0, [start]

    queue = deque([start])
    parents: Dict[str, Optional[str]] = {start: None}

    while queue:
        current_node = queue.popleft()
        for neighbor, *_ in graph_data[current_node]:
            if neighbor in parents:
                continue
            parents[neighbor] = current_node

            if neighbor == end:
                path: List[str] = []
                curr: Optional[str] = end
                while curr is not None:
                    path.append(curr)
                    curr = parents[curr]
                path.reverse()
                return len(path) - 1, path

            queue.append(neighbor)

    return float("inf"), []


def _edges_along_path(
    graph_data: Dict[str, List[Tuple[str, int, int, int]]],
    path: List[str],
) -> Optional[List[Tuple[str, str, int, int, int]]]:
    """Extract concrete edge tuples along a sequence of districts."""
    edges: List[Tuple[str, str, int, int, int]] = []
    for u, v in zip(path, path[1:]):
        matches = [edge for edge in graph_data.get(u, []) if edge[0] == v]
        if len(matches) > 1:
            raise ValueError(f"Duplicate edge found for {u!r} -> {v!r}")
        if not matches:
            return None
        edges.append((u, v, *matches[0][1:]))
    return edges


def totals_along_path(
    graph_data: Dict[str, List[Tuple[str, int, int, int]]],
    path: List[str],
) -> Tuple[Union[int, float], Union[int, float], Union[int, float]]:
    """Sum total cost (Tk), distance (km), and time (minutes) along a route path.

    Returns:
        Tuple of (total_cost, total_distance, total_time).
        Returns (0, 0, 0) for a 1-node path (same start & end).
        Returns (inf, inf, inf) for empty or disconnected paths.
    """
    if not path:
        return float("inf"), float("inf"), float("inf")
    if len(path) == 1:
        return 0, 0, 0

    edges = _edges_along_path(graph_data, path)
    if edges is None:
        return float("inf"), float("inf"), float("inf")

    cost = sum(edge[2] for edge in edges)
    distance = sum(edge[3] for edge in edges)
    time = sum(edge[4] for edge in edges)
    return cost, distance, time


def legs_along_path(
    graph_data: Dict[str, List[Tuple[str, int, int, int]]],
    path: List[str],
) -> List[Dict[str, Any]]:
    """Return structured per-leg records suitable for tables and APIs."""
    edges = _edges_along_path(graph_data, path)
    if not edges:
        return []
    return [
        {
            "from": start,
            "to": end,
            "cost": cost,
            "distance": distance,
            "time": time,
            "from_coords": DISTRICT_COORDINATES.get(start),
            "to_coords": DISTRICT_COORDINATES.get(end),
        }
        for start, end, cost, distance, time in edges
    ]


def safe_num(value: Union[int, float, None]) -> Optional[Union[int, float]]:
    """Convert float('inf') or invalid values to None for clean JSON/Jinja output."""
    if value == float("inf") or value is None:
        return None
    return value


def build_metric_result(
    graph_data: Dict[str, List[Tuple[str, int, int, int]]],
    value: float,
    path: List[str],
    unit: str,
) -> Dict[str, Any]:
    """Construct standard dictionary representation for a route metric result."""
    cost, distance, time = totals_along_path(graph_data, path)
    path_coords = [DISTRICT_COORDINATES.get(d) for d in path if d in DISTRICT_COORDINATES]
    return {
        "value": safe_num(value),
        "unit": unit,
        "path": path,
        "path_coords": path_coords,
        "legs": len(path) - 1 if path else None,
        "totals": {
            "cost": safe_num(cost),
            "distance": safe_num(distance),
            "time": safe_num(time),
        },
        "leg_rows": legs_along_path(graph_data, path),
    }


def compute_all_routes(
    graph_data: Dict[str, List[Tuple[str, int, int, int]]],
    start: str,
    end: str,
) -> Dict[str, Any]:
    """Compute all 4 routing perspectives between start and end districts."""
    if start == end:
        return {
            "start": start,
            "end": end,
            "same_route": True,
            "note": "Start and destination are the same; no travel is needed.",
            "comparison": [],
            "bfs": None,
            "trade_offs": None,
        }

    cheapest_val, cheapest_path = dijkstra(graph_data, start, end, 1)
    shortest_val, shortest_path = dijkstra(graph_data, start, end, 2)
    fastest_val, fastest_path = dijkstra(graph_data, start, end, 3)
    fewest_legs_val, fewest_legs_path = bfs_fewest_legs(graph_data, start, end)
    bfs_cost, bfs_dist, bfs_time = totals_along_path(graph_data, fewest_legs_path)
    bfs_coords = [DISTRICT_COORDINATES.get(d) for d in fewest_legs_path if d in DISTRICT_COORDINATES]

    comparison = [
        {"label": "Cheapest", "key": "cheapest", "result": build_metric_result(graph_data, cheapest_val, cheapest_path, "Tk")},
        {"label": "Shortest distance", "key": "shortest_distance", "result": build_metric_result(graph_data, shortest_val, shortest_path, "km")},
        {"label": "Fastest", "key": "fastest", "result": build_metric_result(graph_data, fastest_val, fastest_path, "minutes")},
    ]

    reachable_legs = [row["result"]["legs"] for row in comparison if row["result"]["legs"] is not None]
    best_legs = min(reachable_legs) if reachable_legs else None
    for row in comparison:
        row["best_legs"] = (row["result"]["legs"] == best_legs) if best_legs is not None else False

    # Trade-off insights
    trade_offs = {}
    if safe_num(cheapest_val) is not None and safe_num(fastest_val) is not None:
        c_time = comparison[0]["result"]["totals"]["time"]
        f_cost = comparison[2]["result"]["totals"]["cost"]
        if c_time is not None and f_cost is not None:
            time_saved = c_time - fastest_val
            cost_diff = f_cost - cheapest_val
            trade_offs["speed_vs_cost"] = {
                "time_saved_minutes": max(0, time_saved),
                "additional_cost_tk": max(0, cost_diff),
            }

    return {
        "start": start,
        "end": end,
        "same_route": False,
        "note": "Dijkstra computes mathematically optimal paths for each specific metric. BFS identifies the route with the fewest transfer hops.",
        "comparison": comparison,
        "bfs": {
            "legs": safe_num(fewest_legs_val),
            "path": fewest_legs_path,
            "path_coords": bfs_coords,
            "totals": {
                "cost": safe_num(bfs_cost),
                "distance": safe_num(bfs_dist),
                "time": safe_num(bfs_time),
            },
            "leg_rows": legs_along_path(graph_data, fewest_legs_path),
        },
        "trade_offs": trade_offs,
    }


def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    """Application factory for ByteTrip."""
    flask_app = Flask(__name__)
    if test_config:
        flask_app.config.update(test_config)

    @flask_app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "GET":
            return render_template(
                "index.html",
                districts=districts,
                popular_routes=POPULAR_ROUTES,
                coordinates=DISTRICT_COORDINATES,
            )

        start = request.form.get("start", "").strip()
        end = request.form.get("end", "").strip()

        if not start or not end or start not in districts or end not in districts:
            abort(400, description="Please choose valid origin and destination districts from the list.")

        results = compute_all_routes(graph, start, end)
        return render_template(
            "result.html",
            results=results,
            coordinates=DISTRICT_COORDINATES,
        )

    # ------------------ REST API Endpoints ------------------

    @flask_app.route("/api/districts", methods=["GET"])
    def api_districts():
        """Return list of all available districts with geographic coordinates."""
        return jsonify({
            "status": "success",
            "total_districts": len(districts),
            "districts": districts,
            "coordinates": {d: DISTRICT_COORDINATES.get(d) for d in districts},
        })

    @flask_app.route("/api/routes", methods=["GET", "POST"])
    def api_routes():
        """Calculate and return optimal routes in JSON format.

        Accepts query params (?start=...&end=...) or JSON payload ({"start": "...", "end": "..."}).
        """
        if request.method == "POST" and request.is_json:
            payload = request.get_json() or {}
            start = payload.get("start", "").strip()
            end = payload.get("end", "").strip()
        else:
            start = request.args.get("start", "").strip()
            end = request.args.get("end", "").strip()

        if not start or not end:
            return jsonify({
                "status": "error",
                "message": "Missing required parameters: 'start' and 'end' districts are required.",
            }), 400

        if start not in districts or end not in districts:
            return jsonify({
                "status": "error",
                "message": f"Invalid districts provided. 'start'={start!r}, 'end'={end!r}. Both must be in the 64 districts list.",
            }), 400

        results = compute_all_routes(graph, start, end)
        return jsonify({
            "status": "success",
            "data": results,
        })

    @flask_app.route("/api/graph", methods=["GET"])
    def api_graph():
        """Return graph network topology metadata."""
        edge_count = len(df)
        degrees = {node: len(edges) for node, edges in graph.items()}
        avg_degree = sum(degrees.values()) / max(1, len(degrees))
        return jsonify({
            "status": "success",
            "network": {
                "nodes_count": len(districts),
                "undirected_edges_count": edge_count,
                "directed_edges_count": sum(len(edges) for edges in graph.values()),
                "average_degree": round(avg_degree, 2),
                "highest_connectivity_districts": sorted(
                    [{"district": d, "connections": deg} for d, deg in degrees.items()],
                    key=lambda x: x["connections"],
                    reverse=True,
                )[:10],
            },
        })

    @flask_app.route("/readme")
    def readme():
        return send_file(BASE_DIR.parent / "README.md", mimetype="text/markdown")

    @flask_app.errorhandler(400)
    def handle_bad_request(error):
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "message": error.description}), 400
        return (
            render_template(
                "index.html",
                districts=districts,
                popular_routes=POPULAR_ROUTES,
                coordinates=DISTRICT_COORDINATES,
                error=error.description,
            ),
            400,
        )

    @flask_app.errorhandler(404)
    def handle_not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "message": "Resource not found"}), 404
        return render_template("index.html", districts=districts, popular_routes=POPULAR_ROUTES, error="Page not found"), 404

    return flask_app


app = create_app()


if __name__ == "__main__":
    app.run(
        debug=os.getenv("BYTETRIP_DEBUG", "0").lower() in {"1", "true", "yes", "on"},
        host=os.getenv("BYTETRIP_HOST", "127.0.0.1"),
        port=int(os.getenv("BYTETRIP_PORT", "5000")),
    )
