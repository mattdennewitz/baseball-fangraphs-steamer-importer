# Fangraphs/Steamer Projections Scraper

Here's a quick and dirty Scrapy spider for crawling Fangraphs
player pages for:

1. Player name and Fangraphs ID
2. *All* available Steamer component projections
3. Positions-played tally for previous season

... and that's it.

----

## Installation

Clone this repo and install requirements via `pip`:

```shell
$ pip install -r requirements.txt
```

## Usage

1. Visit Fangraphs' Steamer projections page and export CSV files
    for one or both of pitching and batting. These files, rather than
    fangraphs.com, are what informs the spider of where to crawl.
2. Once you've downloaded at least one Steamer CSV export, start crawling:

```shell
$ cd path/to/checkout/steamer
$ scrapy crawl steamerpro <-a batting_file=path/to/csv> <-a pitching_file=path/to/csv> [-o output.json]
```

----

# Notes

### Why so few fields?

I hammered this out during a layover. Submit a PR if you'd like more fields!

### Responsibility

Please do not abuse or overwhelm Fangraphs' servers. They're good people,
and don't need that in their lives. Please respect their Terms of Service.

While Fangraphs hasn't published the license under which Steamer is available,
let's assume this data isn't for anything but research and fun, yeah?
