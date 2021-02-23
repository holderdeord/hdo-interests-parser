import datetime
import json
from pathlib import Path

import pytest
from pytest import fixture

from parser import InterestParser
from utils import pdf_to_xml_dict


@fixture
def pdf_dict():
    with Path("testdata.json").open() as fp:
        return json.load(fp)


@fixture
def interest_parser(pdf_dict):
    return InterestParser(pdf_dict=pdf_dict)


@pytest.mark.skip('Too slow')
def test_pdf_to_xml_dict():
    pdf_path = Path("pdfs/interests-2020-03-23.pdf")
    pdf_dict = pdf_to_xml_dict(pdf_path)
    assert pdf_dict
    assert "23. mars" in json.dumps(pdf_dict)
    with Path("testdata.json").open() as fp:
        expected = json.load(fp)
    assert pdf_dict == expected


def test_parse_date(interest_parser):
    meta = interest_parser.parse_document_meta()
    assert meta
    assert meta.get("updated_at")
    updated_at = meta["updated_at"]
    assert isinstance(updated_at, datetime.date)
    assert updated_at.isoformat() == "2020-03-23"


def test_rep_data(interest_parser):
    data = interest_parser.parse_pdf_data()
    assert data
    assert len(data) > 0

    for rep in data:
        assert rep
        assert "first_name" in rep


def test_first_last_data(interest_parser):
    data = interest_parser.parse_pdf_data()
    assert data
    assert len(data) > 0
    last_rep = data[-1]
    assert last_rep == {
        "first_name": "Johan",
        "last_name": "Aas",
        "party": "frp",
        "by_category": {"2": "Styreleder Gamle Bæreiavegen boligsameie (lønnet)"},
    }


def test_first_rep_data(interest_parser):
    data = interest_parser.parse_pdf_data()
    assert data
    assert len(data) > 0
    first_rep = data[0]
    assert first_rep == {
        "by_category": {
            "2": "Høy & Rodum Eiendom AS, styreleder\n"
            "KomRev Trøndelag IKS, styreleder (lønnet)\n"
            "HRE Holding AS, styreleder\n"
            "Dr. Agdestein AS, styremedlem (vara)\n"
            "Steinkjer Montessoribarnehage, styremedlem\n"
            "Naboer AB, styremedlem\n"
            "Steinkjer Montessoriforening, styremedlem",
            "8": "Fyrgt 3, Steinkjer\n"
            "Kongensgt 38, Steinkjer\n"
            "Otto Sverdrups vei 50, Steinkjer\n"
            "Åsveien 57-59, Steinkjer",
            "9": "Høy & Rodum Eiendom AS\n" "HRE Holding AS",
        },
        "first_name": "Elin Rodum",
        "last_name": "Agdestein",
        "party": "h",
    }
