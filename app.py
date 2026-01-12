from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openelectricity import AsyncOEClient
from openelectricity.models.timeseries import TimeSeriesResponse
from openelectricity.types import MarketMetric
from network_charge import calculate_local_price

NETWORK_REGION = "NSW1"
INTERVAL = "5m"
MIN_POINTS = 3

load_dotenv(".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The OpenElectricity client reads OPENELECTRICITY_API_KEY (and optionally
    # OPENELECTRICITY_API_URL) from the environment. Keep a single client session
    # for the app lifetime.
    app.state.oe = AsyncOEClient()
    try:
        yield
    finally:
        client: AsyncOEClient | None = getattr(app.state, "oe", None)
        if client:
            await client.close()


app = FastAPI(title="Open Electricity proxy", version="0.1.0", lifespan=lifespan)

def _time_window_minutes(minutes: int = 30) -> tuple[datetime, datetime]:
    """Return naive (date_start, date_end) datetimes in network local time (AEST/AEDT)."""
    tz = ZoneInfo("Australia/Sydney")
    end_dt = datetime.now(tz) - timedelta(minutes=30)
    start_dt = end_dt - timedelta(minutes=minutes)
    # API expects timezone-naive timestamps in network local time.
    end_local = end_dt.replace(tzinfo=None)
    start_local = start_dt.replace(tzinfo=None)
    return start_local, end_local


def _extract_prices(response: TimeSeriesResponse) -> list[float]:
    numeric_values: list[float] = []

    for series in response.data:
        if str(series.metric).lower() != MarketMetric.PRICE.value:
            continue

        for result in series.results:
            region = (result.columns.network_region or "").upper()
            if region and region != NETWORK_REGION:
                continue
            for point in result.data:
                if point.value is None:
                    continue
                numeric_values.append(float(point.value))

    return numeric_values


@app.get("/average-price")
async def get_average_price() -> dict[str, Any]:

    client: AsyncOEClient = app.state.oe
    date_start, date_end = _time_window_minutes(45)

    try:
        market = await client.get_market(
            network_code="NEM",
            metrics=[MarketMetric.PRICE],
            interval=INTERVAL,
            date_start=date_start,
            date_end=date_end,
            primary_grouping="network_region",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc

    values = _extract_prices(market)
    if not values:
        raise HTTPException(status_code=502, detail="Upstream response did not contain any price points")

    points_used = min(MIN_POINTS, len(values))
    last_values = values[-points_used:]
    average_price = sum(last_values) / len(last_values)

    current_network_charge = calculate_local_price(datetime.now(ZoneInfo("Australia/Sydney")))

    return {
        "network_region": NETWORK_REGION,
        "interval": INTERVAL,
        "points_used": len(last_values),
        "price_points": last_values,
        "average_price": average_price,
        "average_price_with_network_charge": average_price + current_network_charge,
        "units": "$ / MWh",
    }


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Use /average-price to fetch the latest NSW average price"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
