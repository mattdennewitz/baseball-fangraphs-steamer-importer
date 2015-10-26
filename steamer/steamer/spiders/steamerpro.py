# -*- coding: utf-8 -*-

import collections
import os
import unicodecsv as csv
import urlparse

import scrapy

from ..items import Projection


PROFILE_URL = 'http://www.fangraphs.com/statss.aspx?playerid={player_id}'
GAMELOG_URL = 'http://www.fangraphs.com/statsd.aspx?playerid={player_id}'


def get_player_id_from_url(url):
    url_bits = urlparse.urlparse(url)
    qs_bits = urlparse.parse_qs(url_bits.query)
    return qs_bits['playerid'][0]


def url_generator(*files):
    paths = filter(lambda p: p is not None and os.path.exists(p),
                   files)
    for path in paths:
        reader = csv.DictReader(open(path, 'r'))
        for row in reader:
            yield PROFILE_URL.format(player_id=row['playerid'])


class SteamerproSpider(scrapy.Spider):
    name = 'steamerpro'
    allowed_domains = ['fangraphs.com']

    def __init__(self, batting_file=None, pitching_file=None, *a, **kw):
        super(SteamerproSpider, self).__init__(*a, **kw)

        if not any((batting_file, pitching_file)):
            raise scrapy.exceptions.CloseSpider(
                reason="""Please provide a path to one or both of
                Fangraphs batting or pitching projection
                CSV exports via `-a {pitching,batting}_file=...` arguments.
                """)

        self.start_urls = url_generator(batting_file, pitching_file)

    def parse(self, response):
        """Extract Steamer stats from player pages
        """

        player_id = get_player_id_from_url(response.url)

        player_name = (response.css('div#content table:first-of-type table tr:first-of-type span strong::text')
                       .extract()[0]
                       .strip())

        components = {}

        # extract projections
        tables = response.xpath("""
            //table[@class="rgMasterTable"
                    and tbody[tr/td[contains(.,"2016")]
                    and tr/td[contains(.,"Steamer")]]]
        """)

        for table in tables:
            keys = table.xpath('thead/tr/th//text()').extract()
            values = []

            for cell in table.xpath(
                'tbody/tr[td[contains(., "Steamer")]]/td//text()'):
                values.append(cell.extract().strip())

            components.update(**dict(zip(keys, values)))

        # remove Team, which will always be "Steamer"
        components.pop('Team')

        # pass combined projections to gamelog extraction
        player_gs_url = GAMELOG_URL.format(player_id=player_id)
        req = scrapy.Request(player_gs_url, self.parse_previous_year_gamelog)
        req.meta.update(player_id=player_id,
                        player_name=player_name,
                        components=components)
        yield req

    def parse_previous_year_gamelog(self, response):
        """Extract game log for previous season
        """

        tally = collections.Counter()

        for game_positions in response.xpath(
            '//table[@class="rgMasterTable"]/tbody/'
            'tr[@class="rgRow" or @class="rgAltRow"]/td[5]/text()'):
            positions = map(lambda v: v.strip(),
                            game_positions.extract().split('-'))
            for pos in filter(lambda v: v, positions):
                tally[pos] += 1

        yield Projection(player_id=response.meta['player_id'],
                         player_name=response.meta['player_name'],
                         components=response.meta['components'],
                         positions=tally)
