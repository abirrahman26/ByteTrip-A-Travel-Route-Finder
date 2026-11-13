import heapq
import os
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd
from flask import Flask, abort, render_template, request, send_file


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "route_infos_clean.csv"
df = pd.read_csv(DATA_PATH)

app = Flask(__name__)

# The cleaned data has one undirected row per pair; the graph stores both directions.
graph = defaultdict(list)
for _, row in df.iterrows():
    edge = (row["to"], int(row["cost"]), int(row["distance_km"]), int(row["time_minutes"]))
    reverse_edge = (row["from"], int(row["cost"]), int(row["distance_km"]), int(row["time_minutes"]))
    graph[row["from"]].append(edge)
    graph[row["to"]].append(reverse_edge)

districts = sorted(set(df["from"]).union(df["to"]))


def dijkstra(graph, start, end, weight_index):
    """Return the minimum weighted route for cost, distance, or time."""
    if start == end:
        return 0, [start]

    distances = {start: 0}
    parents = {start: None}
    queue = [(0, start)]

    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        if node == end:
            path = []
            current = end
            while current is not None:
                path.append(current)
                current = parents[current]
            return distance, list(reversed(path))

        for neighbor, cost, route_distance, route_time in graph[node]:
            weight = (cost, route_distance, route_time)[weight_index - 1]
            candidate = distance + weight
            if candidate < distances.get(neighbor, float("inf")):
                distances[neighbor] = candidate
                parents[neighbor] = node
                heapq.heappush(queue, (candidate, neighbor))

    return float("inf"), []


def bfs_fewest_legs(graph, start, end):
    """Return the route with the fewest legs, where each edge is one leg."""
    if start == end:
        return 0, [start]

    queue = deque([start])
    parents = {start: None}
    while queue:
        node = queue.popleft()
        for neighbor, *_ in graph[node]:
            if neighbor in parents:
                continue
            parents[neighbor] = node
            if neighbor == end:
                path = []
                current = end
                while current is not None:
                    path.append(current)
                    current = parents[current]
                path.reverse()
                return len(path) - 1, path
            queue.append(neighbor)
    return float("inf"), []


def _edges_along_path(graph, path):
    edges = []
    for start, end in zip(path, path[1:]):
        matches = [edge for edge in graph[start] if edge[0] == end]
        if len(matches) > 1:
            raise ValueError(f"Duplicate edge found for {start!r} -> {end!r}")
        if not matches:
            return None
        edges.append((start, end, *matches[0][1:]))
    return edges


def totals_along_path(graph, path):
    """Sum cost, distance, and time for a concrete route path."""
    if not path or len(path) == 1:
        return 0, 0, 0
    edges = _edges_along_path(graph, path)
    if edges is None:
        return float("inf"), float("inf"), float("inf")
    return tuple(sum(edge[index] for edge in edges) for index in (2, 3, 4))


def legs_along_path(graph, path):
    """Return display-ready per-leg records, or an empty list for no route."""
    edges = _edges_along_path(graph, path)
    if not edges:
        return []
    return [
        {"from": start, "to": end, "cost": cost, "distance": distance, "time": time}
        for start, end, cost, distance, time in edges
    ]


def safe_num(value):
    return None if value == float("inf") else value


def metric_result(value, path, unit):
    cost, distance, time = totals_along_path(graph, path)
    return {
        "value": safe_num(value),
        "unit": unit,
        "path": path,
        "legs": len(path) - 1 if path else None,
        "totals": {"cost": safe_num(cost), "distance": safe_num(distance), "time": safe_num(time)},
        "leg_rows": legs_along_path(graph, path),
    }


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html", districts=districts)

    start = request.form.get("start", "")
    end = request.form.get("end", "")
    if start not in districts or end not in districts:
        abort(400, description="Please choose valid districts from the form.")

    if start == end:
        results = {
            "start": start,
            "end": end,
            "same_route": True,
            "note": "Start and destination are the same; no travel is needed.",
            "comparison": [],
            "bfs": None,
        }
        return render_template("result.html", results=results)

    cheapest, cheapest_path = dijkstra(graph, start, end, 1)
    shortest_distance, shortest_distance_path = dijkstra(graph, start, end, 2)
    fastest, fastest_path = dijkstra(graph, start, end, 3)
    fewest_legs, fewest_legs_path = bfs_fewest_legs(graph, start, end)
    bfs_cost, bfs_distance, bfs_time = totals_along_path(graph, fewest_legs_path)

    comparison = [
        {"label": "Cheapest", "key": "cheapest", "result": metric_result(cheapest, cheapest_path, "Tk")},
        {"label": "Shortest distance", "key": "shortest_distance", "result": metric_result(shortest_distance, shortest_distance_path, "km")},
        {"label": "Fastest", "key": "fastest", "result": metric_result(fastest, fastest_path, "minutes")},
    ]
    reachable_legs = [row["result"]["legs"] for row in comparison if row["result"]["legs"] is not None]
    best_legs = min(reachable_legs) if reachable_legs else None
    for row in comparison:
        row["best_legs"] = row["result"]["legs"] == best_legs

    return render_template(
        "result.html",
        results={
            "start": start,
            "end": end,
            "same_route": False,
            "note": "Dijkstra finds the best weighted route for each metric. BFS finds the fewest-leg route; its totals are shown separately.",
            "comparison": comparison,
            "bfs": {
                "legs": safe_num(fewest_legs),
                "path": fewest_legs_path,
                "totals": {"cost": safe_num(bfs_cost), "distance": safe_num(bfs_distance), "time": safe_num(bfs_time)},
                "leg_rows": legs_along_path(graph, fewest_legs_path),
            },
        },
    )


@app.route("/readme")
def readme():
    return send_file(BASE_DIR.parent / "README.md", mimetype="text/markdown")


if __name__ == "__main__":
    app.run(debug=os.getenv("BYTETRIP_DEBUG", "0").lower() in {"1", "true", "yes", "on"})