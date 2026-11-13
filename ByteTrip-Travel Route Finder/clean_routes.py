from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
RAW_PATH = BASE_DIR / "route_infos.csv"
CLEAN_PATH = BASE_DIR / "route_infos_clean.csv"

NUMERIC_COLUMNS = ["cost", "distance_km", "time_minutes"]
DISTRICT_RENAMES = {
    "Borguna": "Barguna",
    "Coxsbazar": "Cox's Bazar",
    "Comilla": "Cumilla",
    "Jessore": "Jashore",
    "Jhalokathi": "Jhalokati",
    "Laksmipur": "Lakshmipur",
    "Lalmonir": "Lalmonirhat",
    "Narshingdi": "Narsingdi",
    "Panchagar": "Panchagarh",
    "Shariyatpur": "Shariatpur",
}


def clean_routes(source_path=RAW_PATH, output_path=CLEAN_PATH):
    routes = pd.read_csv(source_path)
    required_columns = {"from", "to", *NUMERIC_COLUMNS}
    missing_columns = required_columns.difference(routes.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    routes = routes[["from", "to", *NUMERIC_COLUMNS]].copy()
    routes["from"] = routes["from"].replace(DISTRICT_RENAMES)
    routes["to"] = routes["to"].replace(DISTRICT_RENAMES)
    routes[NUMERIC_COLUMNS] = routes[NUMERIC_COLUMNS].apply(pd.to_numeric)

    if routes.isna().any().any():
        raise ValueError("Route data contains missing values")
    if (routes["from"] == routes["to"]).any():
        raise ValueError("Route data contains a self-loop")
    if (routes[NUMERIC_COLUMNS] < 0).any().any():
        raise ValueError("Route data contains a negative number")

    for column in NUMERIC_COLUMNS:
        if not (routes[column] % 1 == 0).all():
            raise ValueError(f"{column} contains a non-integer value")
        routes[column] = routes[column].astype(int)

    high_costs = routes["cost"] >= 500
    routes.loc[high_costs, "cost"] //= 10

    routes["pair"] = routes.apply(
        lambda row: tuple(sorted((row["from"], row["to"]))), axis=1
    )
    cleaned = (
        routes.groupby("pair", sort=True)[NUMERIC_COLUMNS]
        .max()
        .reset_index()
    )
    cleaned[["from", "to"]] = pd.DataFrame(
        cleaned.pop("pair").tolist(), index=cleaned.index
    )
    cleaned = cleaned[["from", "to", *NUMERIC_COLUMNS]]

    output_path = Path(output_path)
    cleaned.to_csv(output_path, index=False)
    suspicious = cleaned[cleaned["cost"] > 500]
    print(f"Wrote {len(cleaned)} routes to {output_path}")
    if suspicious.empty:
        print("Suspicious costs above 500 Tk remaining: none")
    else:
        print("Suspicious costs above 500 Tk remaining:")
        print(suspicious.to_string(index=False))
    return cleaned


if __name__ == "__main__":
    clean_routes()