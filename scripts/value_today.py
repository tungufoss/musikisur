"""Convert a historical amount in pounds to today's pounds and Icelandic krónur.

    python scripts/value_today.py 1500000 1992

Inflation: UK consumer price index (ONS series D7BT, 2015=100), the given year's annual
average against the latest month. Exchange rate: the latest ECB reference rates for GBP
and ISK (both per euro). Downloads are cached in data/raw/, so the numbers can be
reproduced; delete the cache files to refresh them.
"""
import argparse

from music_life.sources.http import CachedClient


def cpi() -> tuple[dict[str, float], str, float]:
    ons = CachedClient("ons", "https://www.ons.gov.uk")
    data = ons.get_json("economy/inflationandpriceindices/timeseries/d7bt/mm23/data", "cpi-d7bt")
    latest = data["months"][-1]
    return {y["date"]: float(y["value"]) for y in data["years"]}, latest["date"], float(latest["value"])


def ecb_rate(currency: str) -> tuple[str, float]:
    """Latest reference rate: units of ``currency`` per euro, with its date."""
    ecb = CachedClient("ecb", "https://data-api.ecb.europa.eu")
    data = ecb.get_json(
        f"service/data/EXR/D.{currency}.EUR.SP00.A", f"exr-{currency.lower()}",
        {"lastNObservations": 1, "format": "jsondata"},
    )
    series = next(iter(data["dataSets"][0]["series"].values()))
    value = float(next(iter(series["observations"].values()))[0])
    day = data["structure"]["dimensions"]["observation"][0]["values"][-1]["id"]
    return day, value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("amount", type=float, help="amount in pounds")
    parser.add_argument("year", help="year the amount refers to")
    args = parser.parse_args()

    years, month, latest = cpi()
    then = years[args.year]
    pounds_today = args.amount * latest / then
    day, gbp = ecb_rate("GBP")
    _, isk = ecb_rate("ISK")
    kr_per_pound = isk / gbp
    print(f"£{args.amount:,.0f} ({args.year}) ≈ £{pounds_today:,.0f} ({month}) ≈ {pounds_today * kr_per_pound:,.0f} kr.")
    print(f"UK CPI D7BT {args.year}: {then}, {month}: {latest} (×{latest / then:.3f}); "
          f"{kr_per_pound:.2f} kr./£ (ECB, {day})")


if __name__ == "__main__":
    main()
