# Fangraphs/Steamer Projections Scraper

This spider collects and exports 2016 Steamer projections
and previous-year field positions for some or all projected players.

## Installation

Clone this repo and install requirements via `pip`:

```shell
$ pip install -r requirements.txt
```

## Usage

This spider has two modes of operation:

1. Collecting all players (:heavy_check_mark: default - see notes below)
2. Collecting one or more specific players by their Fangraphs IDs
    (via `-a player_ids=<player id>[,player id...]

### Collecting all players

This method requires a little legwork. Fangraphs' pagination is not
easily manipulated, so this spider more explicit instructions.
These instructions come in the form of the downloadable Steamer CSV exports,
which this spider ingests before starting its crawl.

1. Visit Fangraphs' [Steamer projections page](http://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type=steamer&team=0&lg=all&players=0) and export CSV files
    for one or both of pitching and batting via the "Export Data" link above
    projection stats tables.
2. Once you've downloaded at least one Steamer CSV export, define
    where the spider can find each file (batting, pitching) and
    then start crawling.

```shell
$ cd path/to/checkout/steamer
$ scrapy crawl steamerpro <-a batting_file=path/to/csv> <-a pitching_file=path/to/csv> [-o output.json]
```

You may crawl with one or both files, but in this mode
you must have at least one.

### Collecting specific players by FG ID

Alternatively, this spider can limit its crawling to a user-defined list of players.
To collect projections for only a subset of players, pass in a comma-separated
list of Fangraphs IDs using the `player_ids` flag.

In this example, we collect projections for Mike Trout and Kris Bryant
and write the output to a JSOn file called "trout-bryant.json"

```shell
$ scrapy crawl steamerpro -a player_ids=10155,15429 -o trout-bryant.json
```

## Support Steamer and Fangraphs

Without their combined efforts, this effort would not be possible.
Your fantasy drafts would be unmitigated disasters, and Earth
might even shift off its axis. Dunno, don't want to know.

Please do not abuse or overwhelm Fangraphs' servers. They're good people,
and don't need that in their lives. Please respect their Terms of Service.

While Fangraphs and the Steamer folks have not published the license under
which Steamer is available, let's assume this data isn't for anything
but research and fun.
