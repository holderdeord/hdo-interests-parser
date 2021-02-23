#!/usr/bin/python3
# -*- coding: utf-8 -*-
import argparse
import re
from pathlib import Path
from pprint import pprint

import shutil

from collections import OrderedDict
from datetime import datetime

from settings import PDF_DIR, DATA_DIR
from utils import write_csv, write_json, pdf_to_xml_dict, MONTHS_NB


class InterestParser:
    """
    Fetch, parse and archive representative interests from stortinget.no.

    https://www.stortinget.no/no/Stortinget-og-demokratiet/Representantene/Okonomiske-interesser/
    """

    REP_URL = "https://www.stortinget.no/globalassets/pdf/verv_oekonomiske_interesser_register/verv_ok_interesser.pdf"

    NO_REP_TEXTS = ["Ingen registrerte opplysninger", "Ingen mottatte opplysninger"]
    PAGE_SEPARATOR = "_______________"

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

    def parse_document_meta(self):
        first_page_texts = self.pdf_dict["pdf2xml"]["page"][0]["text"]
        marker = "Ajourført"
        updated_at = [text for text in first_page_texts if marker in text.get("#text", "")][0]["#text"]
        return {"updated_at": self.last_updated_date(updated_at)}

    def first_page_with_rep_data(self):
        for i, page in enumerate(self.pdf_dict["pdf2xml"]["page"]):
            texts = page["text"]
            for text in texts:
                bold_text = (text.get("b", "") or "").strip()
                text_plain = (text.get("#text", "") or "").strip()
                if bold_text == "Representanter":
                    return i
                elif text_plain == "Representanter":
                    return i
        raise ValueError("Could not find page with representative heading")

    def find_y_coords(self, first_page):
        category_coord = "106"  # Defaults needed?
        interest_coord = "319"
        for text in first_page["text"]:
            if text.get("#text", "") in self.INTEREST_CATS.values():
                category_coord = text.get("@left")
                break

        for text in first_page["text"]:
            content = text.get("#text", "")
            y_coord = text.get("@left")
            if content and int(y_coord) > int(category_coord) and content != self.PAGE_SEPARATOR and len(content) > 1:
                interest_coord = y_coord

        return category_coord, interest_coord

    def parse_pdf_data(self):
        """Parse meta data, reps and their interest table"""

        rep_start = self.first_page_with_rep_data()
        pages = self.pdf_dict["pdf2xml"]["page"]
        rep_pages = pages[rep_start:]

        non_rep_headers = [
            "Representanter",
            "Regjeringsmedlemmer",
            "Vararepresentanter",
        ]
        split_headers = ["Abrahamsen,", "Amundsen,"]
        category_col_y_coord, interest_col_y_coord = self.find_y_coords(rep_pages[0])

        reps = []
        last_rep = None
        by_category = {}
        last_category = None
        last_text = ""
        swallowed_next = False
        num_reps = 0

        for page in rep_pages:
            texts = page["text"]
            for text_idx, text in enumerate(texts):
                # all reps are in bold (headers) with a few exceptions
                header = text.get("b", "")
                content = text.get("#text", "")

                is_rep_header = bool(header and header not in non_rep_headers)
                is_category = content and text["@left"] == category_col_y_coord and content != page["@number"]
                is_interest_text = content and text["@left"] == interest_col_y_coord

                if is_rep_header:
                    # Should we swallow next?
                    # Representative name header on same line or continues on next line
                    should_swallow_next = header in split_headers or header[-1] == "-"
                    if should_swallow_next:
                        header = f'{header} {texts[text_idx + 1].get("b")}'
                        swallowed_next = True
                    elif swallowed_next:
                        swallowed_next = False
                        continue  # skip

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
                    if not m:
                        raise ValueError(f"No representative matched in representative header: {header}")

                    last_name, first_name = m.group("full_name").split(", ")
                    last_rep = {
                        "first_name": first_name.strip(),
                        "last_name": last_name.strip(),
                        "party": m.group("party").lower(),
                    }
                    num_reps += 1

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
            {
                **last_rep,
                "by_category": by_category,
            }
        )

        if num_reps != len(reps):
            ValueError(f"Number of representatives {num_reps} does not match output {len(reps)}")

        return reps

    def last_updated_date(self, text):
        pattern = re.compile(r"Ajourført pr\. (.*)")
        date_text = pattern.search(text).group(1).lower().replace(".", "").strip()
        for m, v in MONTHS_NB.items():
            date_text = date_text.replace(m, v)

        # zero pad day
        if date_text[1] == " ":
            date_text = "0" + date_text

        return datetime.strptime(date_text, "%d %m %Y").date()

    def parse_and_save(self, pdf_path, archive_pdf=True, seen=None):
        self.pdf_dict = pdf_to_xml_dict(pdf_path)
        meta = self.parse_document_meta()
        updated_at_str = meta["updated_at"].strftime("%Y-%m-%d")

        if seen and updated_at_str in seen:
            print("Skipping already parsed '{}'".format(pdf_path))
            return

        if archive_pdf:
            archive_path = PDF_DIR.joinpath("interests-{}.pdf".format(updated_at_str))
            try:
                shutil.copy(pdf_path, archive_path)
            except shutil.SameFileError:
                pass  # skip already archived

        res = self.parse_pdf_data()
        flattened = self.flatten_data(res)

        field_names = ["first_name", "last_name", "party"] + list(self.INTEREST_CATS.values()) + [self.NO_REP_TEXTS[0]]
        csv_path = DATA_DIR.joinpath(f"interests-{updated_at_str}.csv")
        json_path = DATA_DIR.joinpath(f"interests-{updated_at_str}.json")
        write_csv(csv_path, flattened, field_names)
        write_json(
            json_path,
            {
                "_meta": {
                    "categories": self.INTEREST_CATS,
                    "updated_at": updated_at_str,
                },
                "reps": res,
            },
        )

        return updated_at_str

    def parse_all(self):
        seen = []
        for pdf in PDF_DIR.glob("*.pdf"):
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


def parse_cli_args():
    desc = InterestParser.__doc__
    p = argparse.ArgumentParser(description=desc)
    p.add_argument(
        "--file",
        help="Parse given PDF by filename",
    )
    p.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Parse PDFs in PDF_DIR",
    )
    p.add_argument("--verbose", action="store_true", default=False, help="Verbose output")

    _args = p.parse_args()

    if (not _args.all and not _args.file) or (_args.all and _args.file):
        p.error("Provide either --all or --file")
    return _args


if __name__ == "__main__":
    args = parse_cli_args()
    parser = InterestParser(verbose=args.verbose)
    if args.all:
        parser.parse_all()
    else:
        parser.parse_and_save(Path(args.file))
