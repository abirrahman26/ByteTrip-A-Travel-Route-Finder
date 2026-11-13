import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app, districts, graph, bfs_fewest_legs, dijkstra, totals_along_path


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
