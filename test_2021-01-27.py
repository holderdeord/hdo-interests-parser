from pathlib import Path
import pytest
from pytest import fixture

from parser import InterestParser
from utils import pdf_to_xml_dict


@fixture
def interest_parser_2021_jan():
    pdf_path = Path("pdfs/interests-2021-01-27.pdf")
    pdf_dict = pdf_to_xml_dict(pdf_path)
    return InterestParser(pdf_dict=pdf_dict)


def test_kari_henriksen(interest_parser_2021_jan):
    meta = interest_parser_2021_jan.parse_document_meta()
    assert meta
    datas = interest_parser_2021_jan.parse_pdf_data()
    assert datas
    assert len(datas) == 267
    kh = list(filter(lambda rep: rep["first_name"] == "Kari" and rep["last_name"] == "Henriksen", datas))
    assert kh

    kari_henriksen = {
        "first_name": "Kari",
        "last_name": "Henriksen",
        "party": "a",
        "by_category": {
            "4": "Se merknad under andre forhold. Jurymedlem i Eilert Sund jury v\n"
            "UiA. Mars-April, ca 8000 kroner i 2017",
            "5": "Har permisjon uten lønn fra Sørlandet Sykehus HF",
            "9": "Fond:\n"
            "DnB Norge - 86,9473 andeler\n"
            "DnB Global – 0,9800 andel\n"
            "Alfred Berg Humanfond 25,5206 andeler\n"
            "Nordea Avkastning 21,2521 andeler\n"
            "Sbanken fond, bestående av:\n"
            "Skagen Kon-Tiki A\n"
            "KLP AksjeFremvoksende Markeder\n"
            "Holberg Rurik\n"
            "Odin Emerging Markets\n"
            "Aksjer:\n"
            "DnB – 10 stk.\n"
            "Storebrand – 14 stk.\n"
            "Dolphin Drilling – 211 stk.",
            "11": "Mottok et armbåndsur merke a.b.art fra OSCE i Geneve, 2. oktober\n"
            "2014.\n"
            "Gave fra Stortingsgruppa i forbindelse med min 60 års dag 2015\n"
            "Medaljong fra Mongolia i forb med OSCE s sommermøte 2017",
            "98": "Har påtatt meg å være medlem av Eilert Sund juryen, vi skal vurdere\n"
            "innkomne oppgaver fra videregående skoler i Agder til Eilert Sund\n"
            "prisen som deles ut av UiA hvert år. Avtalen fra mars- april, "
            "honoreres\n"
            "etter satser på UIA universitet. Forrige gang jeg satt i juryen, to "
            "år\n"
            "siden, var netto utbetaling rundt 8000 kroner",
        },
    }
    assert kh[0] == kari_henriksen
