Parse (successfully) the [PDF containing the represantatives economic interests, etc from stortinget.no](https://www.stortinget.no/no/Stortinget-og-demokratiet/Representantene/Okonomiske-interesser/) into a machine readable format and archive result.

Last updated by bot: 2020-02-28

## Setup
```shell script
sudo apt install poppler-utils  # debian/ubuntu
brew install poppler  # macos

pipenv install --dev
pipenv shell
python parser.py
```

## Tests
```shell script
pytest -vv --diff-type=split
```