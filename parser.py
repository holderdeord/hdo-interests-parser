#!/usr/bin/python3
# -*- coding: utf-8 -*-
import argparse
import re
from pprint import pprint

import requests
import tempfile
import shutil

from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from utils import write_csv, write_json, file_checksum, pdf_to_xml_dict


class InterestParser:
    """
        Fetch, parse and archive representative interests from stortinget.no.

        https://www.stortinget.no/no/Stortinget-og-demokratiet/Representantene/Okonomiske-interesser/
    """

    REP_URL = "https://www.stortinget.no/globalassets/pdf/verv_oekonomiske_interesser_register/verv_ok_interesser.pdf"
    PDF_DIR = Path("pdfs")
    DATA_DIR = Path("data")

    NO_REP_TEXTS = ["Ingen registrerte opplysninger", "Ingen mottatte opplysninger"]

    INTEREST_CATS = OrderedDict(
        {
            "1": "Har ingen registreringspliktige interesser",
            "2": "Styreverv mv.",
            "3": "Selvstendig næring",
            "4": "Lønnet stilling mv.",
            "5": "Tidligere arbeidsgiver",
            "6": "Framtidig arbeidsgiver",
            "7": "Økonomisk støtte",
            "8": "Eiendom i næring",
            "9": "Aksjer mv.",
            "10": "Utenlandsreiser",
            "11": "Gaver",
            "12": "Opplysninger om selskapsgjeld",
            "98": "Andre forhold",
        }
    )
    pdf_dict = {}

    def __init__(self, pdf_dict=None, verbose=False):
        self.verbose = verbose
        self.pdf_dict = pdf_dict

    def download_new_pdf(self, url, path: Path):
        """ Download new file, if checksum changed then overwrite if not do nothing"""
        if not self.PDF_DIR.exists():
            self.PDF_DIR.mkdir()

        r = requests.get(url, stream=True)
        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            for chunk in r.iter_content(chunk_size=4096):
                if chunk:
                    f.write(chunk)

        tmp_file_path = Path(f.name)

        if path.exists() and file_checksum(tmp_file_path) == file_checksum(path):
            tmp_file_path.unlink()
            return False

        # Move/overwrite
        tmp_file_path.rename(path)

        return True

    def parse_document_meta(self):
        first_page_texts = self.pdf_dict["pdf2xml"]["page"][0]["text"]
        marker = "Ajourført"
        updated_at = [text for text in first_page_texts if marker in text.get("#text", "")][0]["#text"]
        return {"updated_at": self.last_updated_date(updated_at)}

    def first_page_with_rep_data(self):
        for i, page in enumerate(self.pdf_dict["pdf2xml"]["page"]):
            texts = page["text"]
            for text in texts:
                if "Representanter" in text.get("b", ""):
                    return i
        return -1

    def parse_pdf_data(self):
        """Parse meta data, reps and their interest table"""
        rep_start = self.first_page_with_rep_data()
        pages = self.pdf_dict["pdf2xml"]["page"]
        assert rep_start != -1
        rep_pages = pages[rep_start:]

        non_rep_headers = [
            "Representanter",
            "Regjeringsmedlemmer",
            "Vararepresentanter",
        ]
        left_col_y_coord = "106"
        right_col_y_coord = "319"

        reps = []
        last_rep = None
        by_category = {}
        last_category = None
        last_text = ""
        for page in rep_pages:
            for text in page["text"]:
                # all reps are in bold (headers) with a few exceptions
                header = text.get("b", "")
                content = text.get("#text", "")

                is_rep_header = header and header not in non_rep_headers
                is_category = content and text["@left"] == left_col_y_coord and content != page["@number"]
                is_interest_text = content and text["@left"] == right_col_y_coord

                if is_rep_header:
                    if last_category and last_text:
                        # flush interest text
                        by_category[last_category] = last_text
                        last_text = ""

                    if by_category:
                        # flush category data to previous rep
                        rep_data = {**last_rep, "by_category": by_category}
                        reps.append(rep_data)
                        by_category = {}

                    rep_pattern = re.compile(
                        r"(?P<full_name>[-\w,. ]+)\(((?P<rep_number>\d+), )?(?P<party>\w+),? ?([-,\w\s]+)?\)"
                    )
                    m = rep_pattern.match(header)
                    assert m
                    last_name, first_name = m.group("full_name").split(", ")
                    last_rep = {
                        "first_name": first_name.strip(),
                        "last_name": last_name.strip(),
                        "party": m.group("party").lower(),
                    }

                elif is_category:
                    if last_category and last_text:
                        # flush interest text
                        by_category[last_category] = last_text
                        last_text = ""

                    # FIXME: NO_REP_TEXTS
                    last_category = "1"
                    if "§" in content:
                        last_category = content.replace("§", "").split(" ")[0].strip()

                elif is_interest_text:
                    last_text = f"{last_text}\n{content}" if last_text else f"{last_text}{content}"

        # flush last data
        if last_category and last_text:
            by_category[last_category] = last_text
        reps.append(
            {**last_rep, "by_category": by_category,}
        )

        return reps

    def last_updated_date(self, text):
        pattern = re.compile(r"Ajourført pr\. (.*)")
        months = {
            "januar": "01",
            "februar": "02",
            "mars": "03",
            "april": "04",
            "mai": "05",
            "juni": "06",
            "juli": "07",
            "august": "08",
            "september": "09",
            "oktober": "10",
            "november": "11",
            "desember": "12",
        }
        date_text = pattern.search(text).group(1).lower().replace(".", "").strip()
        for m, v in months.items():
            date_text = date_text.replace(m, v)

        # zero pad day
        if date_text[1] == " ":
            date_text = "0" + date_text

        return datetime.strptime(date_text, "%d %m %Y").date()

    def fetch_latest_and_parse(self):
        pdf_path = self.PDF_DIR.joinpath("interests-latest.pdf")
        is_updated = self.download_new_pdf(self.REP_URL, pdf_path)
        if not is_updated:
            pass
            # print("Did nothing, latest PDF already downloaded and parsed")
            # exit(0)

        self.parse_and_save(pdf_path)

    def parse_and_save(self, pdf_path, archive_pdf=True, seen=None):
        self.pdf_dict = pdf_to_xml_dict(pdf_path)
        meta = self.parse_document_meta()
        updated_at_str = meta["updated_at"].strftime("%Y-%m-%d")

        if seen and updated_at_str in seen:
            print("Skipping already parsed '{}'".format(pdf_path))
            return

        if archive_pdf:
            archive_path = self.PDF_DIR.joinpath("interests-{}.pdf".format(updated_at_str))
            try:
                shutil.copy(pdf_path, archive_path)
            except shutil.SameFileError:
                pass  # skip already archived

        res = self.parse_pdf_data()
        flattened = self.flatten_data(res)

        field_names = ["first_name", "last_name", "party"] + list(self.INTEREST_CATS.values()) + [self.NO_REP_TEXTS[0]]
        csv_path = self.DATA_DIR.joinpath(f"interests-{updated_at_str}.csv")
        json_path = self.DATA_DIR.joinpath(f"interests-{updated_at_str}.json")
        write_csv(csv_path, flattened, field_names)
        write_json(
            json_path, {"_meta": {"categories": self.INTEREST_CATS, "updated_at": updated_at_str,}, "reps": res,},
        )

        return updated_at_str

    def parse_existing(self):
        seen = []
        for pdf in self.PDF_DIR.glob("*.pdf"):
            if self.verbose:
                print(f"Parsing '{pdf}'")
            last_updated_str = self.parse_and_save(pdf, archive_pdf=False, seen=seen)

            if last_updated_str is not None:
                seen.append(last_updated_str)

    def flatten_data(self, data):
        flattened = []
        for rep_data in data:
            flat = {**rep_data}
            cats = flat.pop("by_category", {})
            for category_key, interest_text in cats.items():
                if category_key not in self.INTEREST_CATS:
                    pprint(cats)
                    pprint(rep_data)
                flat[self.INTEREST_CATS[category_key]] = interest_text

            flattened.append(flat)

        return flattened


def get_arguments():
    desc = InterestParser.__doc__
    p = argparse.ArgumentParser(description=desc)
    p.add_argument(
        "--parse-existing", action="store_true", default=False, help="Reparse existing PDFs",
    )
    p.add_argument("--verbose", action="store_true", default=False, help="Verbose output")

    return p.parse_args()


if __name__ == "__main__":
    args = get_arguments()
    parser = InterestParser(verbose=args.verbose)
    if args.parse_existing:
        parser.parse_existing()
    else:
        parser.fetch_latest_and_parse()
