Parse (successfully) the [PDF containing the represantatives economic interests, etc from stortinget.no](https://www.stortinget.no/no/Stortinget-og-demokratiet/Representantene/Okonomiske-interesser/) into a machine readable format and archive result.

Last updated by bot: 2021-01-05

## Setup
    sudo apt install poppler-utils  # debian/ubuntu
    brew install poppler  # macos

    pipenv --three install
    pipenv shell
    python parser.py
