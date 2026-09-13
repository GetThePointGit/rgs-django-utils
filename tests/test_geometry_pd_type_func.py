"""Tests voor ``pd_type_func`` van de geometrie-velden in ``dj_extended_models``.

Aanleiding: ``pd.read_sql`` levert PostGIS-geometrie als hex-EWKB-tekst. Alle
geometrie-velden moeten die (en al gedecodeerde shapely-objecten) naar een echte
``GeoSeries`` kunnen zetten, ongeacht het geometrietype.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from rgs_django_utils.database import dj_extended_models as models

SRID = 4326

POLY = Polygon([(4.9, 52.3), (4.91, 52.3), (4.91, 52.31), (4.9, 52.3)])
MPOLY = MultiPolygon([POLY])
LINE = LineString([(4.9, 52.3), (4.91, 52.31)])
POINT = Point(4.9, 52.3)


def _ewkb_hex(geom):
    return shapely.to_wkb(shapely.set_srid(geom, SRID), hex=True, include_srid=True)


@pytest.mark.parametrize(
    ("field_cls", "geom", "expected_type"),
    [
        (models.MultiPolygonField, MPOLY, "MultiPolygon"),
        (models.MultiPolygonField, POLY, "MultiPolygon"),  # enkelvoudig → multi
        (models.PolygonField, POLY, "Polygon"),
        (models.LineStringField, LINE, "LineString"),
        (models.PointField, POINT, "Point"),
        (models.GeometryField, MPOLY, "MultiPolygon"),
    ],
)
@pytest.mark.parametrize("encoding", ["hex", "bytes", "shapely"])
def test_pd_type_func_accepts_wkb_and_shapely(field_cls, geom, expected_type, encoding):
    """Hex-EWKB (zoals ``pd.read_sql``), ruwe WKB-bytes én shapely-objecten worden een GeoSeries."""
    if encoding == "hex":
        value = _ewkb_hex(geom)
    elif encoding == "bytes":
        value = shapely.to_wkb(geom)
    else:
        value = geom
    serie = pd.Series([value, None], dtype="object")

    result = field_cls(srid=SRID).pd_type_func(serie)

    assert isinstance(result, gpd.GeoSeries)
    assert result.crs is not None and result.crs.to_epsg() == SRID
    assert result.iloc[0].geom_type == expected_type
    assert result.iloc[0].equals(
        geom if expected_type != "MultiPolygon" or geom.geom_type == "MultiPolygon" else MPOLY
    )
    assert result.iloc[1] is None or pd.isna(result.iloc[1])


@pytest.mark.parametrize("field_cls", [models.MultiPolygonField, models.LineStringField])
def test_pd_type_func_all_null(field_cls):
    """Een kolom met alleen NULL (bv. lege calc-tabel) blijft een lege GeoSeries."""
    serie = pd.Series([None, np.nan], dtype="object")

    result = field_cls(srid=SRID).pd_type_func(serie)

    assert isinstance(result, gpd.GeoSeries)
    assert result.isna().all()
    assert len(result) == 2


def test_pd_type_func_keeps_existing_geoseries():
    """Een al gedecodeerde GeoSeries gaat er ongewijzigd (met crs) doorheen."""
    serie = gpd.GeoSeries([MPOLY], crs=SRID)

    result = models.MultiPolygonField(srid=SRID).pd_type_func(serie)

    assert isinstance(result, gpd.GeoSeries)
    assert result.crs.to_epsg() == SRID
    assert result.iloc[0].equals(MPOLY)
