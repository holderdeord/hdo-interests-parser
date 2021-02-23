from pathlib import Path
# from pprint import pprint

import pytest
from pytest import fixture

from parser import InterestParser
from utils import pdf_to_xml_dict


@fixture
def interest_parser_2014_09_24():
    pdf_path = Path("pdfs/interests-2014-09-24.pdf")
    pdf_dict = pdf_to_xml_dict(pdf_path)
    return InterestParser(pdf_dict=pdf_dict)


def test_dont_crash(interest_parser_2014_09_24):
    meta = interest_parser_2014_09_24.parse_document_meta()
    assert meta
    datas = interest_parser_2014_09_24.parse_pdf_data()
    assert datas
