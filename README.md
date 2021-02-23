Parse (successfully) the [PDF containing the represantatives economic interests, etc from stortinget.no](https://www.stortinget.no/no/Stortinget-og-demokratiet/Representantene/Okonomiske-interesser/) into a machine readable format and archive result.

stortinget.no now publish historical versions from 2017 to date. There is some data from 2013 to 2014 only available here.

## Setup
    sudo apt install poppler-utils  # debian/ubuntu
    brew install poppler  # macos

    pipenv install --dev
    pipenv run python parser.py --help
    pipenv run python scraper.py --help
