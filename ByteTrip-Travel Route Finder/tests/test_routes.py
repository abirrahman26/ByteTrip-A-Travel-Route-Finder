import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import (
    Metric,
    app,
    bfs_fewest_legs,
    compute_all_routes,
    dijkstra,
    districts,
    graph,
    totals_along_path,
)
from clean_routes import clean_routes


def small_graph():
    return {
        "A": [("B", 5, 10, 10), ("C", 2, 2, 20)],
        "B": [("A", 5, 10, 10), ("C", 2, 3, 3), ("D", 1, 1, 1)],
        "C": [("A", 2, 2, 20), ("B", 2, 3, 3), ("D", 10, 10, 1)],
        "D": [("B", 1, 1, 1), ("C", 10, 10, 1)],
    }


def test_dijkstra_finds_each_weighted_optimum():
    graph_data = small_graph()
    assert dijkstra(graph_data, "A", "D", 1) == (5, ["A", "C", "B", "D"])
    assert dijkstra(graph_data, "A", "D", 2) == (6, ["A", "C", "B", "D"])
    assert dijkstra(graph_data, "A", "D", 3) == (11, ["A", "B", "D"])


def test_dijkstra_supports_string_and_enum_metrics():
    graph_data = small_graph()
    assert dijkstra(graph_data, "A", "D", "cost") == (5, ["A", "C", "B", "D"])
    assert dijkstra(graph_data, "A", "D", "distance") == (6, ["A", "C", "B", "D"])
    assert dijkstra(graph_data, "A", "D", "time") == (11, ["A", "B", "D"])
    assert dijkstra(graph_data, "A", "D", Metric.COST) == (5, ["A", "C", "B", "D"])


def test_bfs_returns_minimum_legs_and_totals_match_path():
    graph_data = small_graph()
    legs, path = bfs_fewest_legs(graph_data, "A", "D")
    assert legs == 2
    assert path == ["A", "B", "D"]
    assert totals_along_path(graph_data, path) == (6, 11, 11)


def test_unreachable_route_is_infinite_and_empty():
    graph_data = {"A": [], "B": []}
    assert dijkstra(graph_data, "A", "B", 1) == (float("inf"), [])
    assert bfs_fewest_legs(graph_data, "A", "B") == (float("inf"), [])
    assert totals_along_path(graph_data, []) == (float("inf"), float("inf"), float("inf"))


def test_duplicate_edge_fails_loudly_when_summing_totals():
    graph_data = {"A": [("B", 3, 5, 7), ("B", 4, 6, 8)], "B": []}
    try:
        totals_along_path(graph_data, ["A", "B"])
    except ValueError as error:
        assert "Duplicate edge" in str(error)
    else:
        raise AssertionError("duplicate edge did not raise ValueError")


def test_same_start_and_end_is_zero():
    graph_data = small_graph()
    assert dijkstra(graph_data, "A", "A", 1) == (0, ["A"])
    assert bfs_fewest_legs(graph_data, "A", "A") == (0, ["A"])
    assert totals_along_path(graph_data, ["A"]) == (0, 0, 0)


def test_graph_and_dropdown_contain_the_same_districts():
    assert set(districts) == set(graph)
    assert all(neighbor in districts for edges in graph.values() for neighbor, *_ in edges)


def test_cleaned_csv_has_unique_undirected_pairs_and_no_self_loops():
    csv_path = Path(__file__).resolve().parents[1] / "route_infos_clean.csv"
    routes = pd.read_csv(csv_path)
    pairs = routes.apply(lambda row: tuple(sorted((row["from"], row["to"]))), axis=1)
    assert not pairs.duplicated().any()
    assert not (routes["from"] == routes["to"]).any()


def test_app_uses_data_path_when_working_directory_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert app.test_client().get("/").status_code == 200


def test_post_validation_and_same_route_message():
    client = app.test_client()
    assert client.post("/", data={"start": "not-a-district", "end": districts[0]}).status_code == 400
    response = client.post("/", data={"start": districts[0], "end": districts[0]})
    assert response.status_code == 200
    assert b"no travel is needed" in response.data


def test_api_districts_endpoint():
    client = app.test_client()
    response = client.get("/api/districts")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["total_districts"] == 64
    assert len(payload["districts"]) == 64
    assert "Dhaka" in payload["coordinates"]
    assert payload["coordinates"]["Dhaka"] == [23.8103, 90.4125]


def test_api_routes_get_and_post():
    client = app.test_client()

    # GET with query params
    res_get = client.get("/api/routes?start=Dhaka&end=Rajshahi")
    assert res_get.status_code == 200
    data_get = res_get.get_json()
    assert data_get["status"] == "success"
    assert data_get["data"]["start"] == "Dhaka"
    assert data_get["data"]["end"] == "Rajshahi"
    assert len(data_get["data"]["comparison"]) == 3

    # POST with JSON body
    res_post = client.post(
        "/api/routes",
        json={"start": "Dhaka", "end": "Chattogram"},
        content_type="application/json",
    )
    assert res_post.status_code == 200
    data_post = res_post.get_json()
    assert data_post["status"] == "success"
    assert data_post["data"]["start"] == "Dhaka"
    assert data_post["data"]["end"] == "Chattogram"
    assert "trade_offs" in data_post["data"]


def test_api_routes_validation_errors():
    client = app.test_client()
    # Missing parameters
    res_missing = client.get("/api/routes?start=Dhaka")
    assert res_missing.status_code == 400

    # Non-existent district
    res_invalid = client.get("/api/routes?start=Dhaka&end=Atlantis")
    assert res_invalid.status_code == 400
    assert "Invalid districts" in res_invalid.get_json()["message"]


def test_api_graph_endpoint():
    client = app.test_client()
    res = client.get("/api/graph")
    assert res.status_code == 200
    net = res.get_json()["network"]
    assert net["nodes_count"] == 64
    assert net["undirected_edges_count"] == 148
    assert net["average_degree"] > 0
    assert len(net["highest_connectivity_districts"]) == 10


def test_clean_routes_functionality(tmp_path):
    raw_path = Path(__file__).resolve().parents[1] / "route_infos.csv"
    out_path = tmp_path / "cleaned_output.csv"
    cleaned_df = clean_routes(source_path=raw_path, output_path=out_path, quiet=True)
    assert len(cleaned_df) == 148
    assert set(cleaned_df.columns) == {"from", "to", "cost", "distance_km", "time_minutes"}
    assert out_path.exists()

