# -*- coding: utf-8 -*-

import collections
import os
import unicodecsv as csv
import urlparse

import scrapy

from ..items import Projection


PROFILE_URL = 'http://www.fangraphs.com/statss.aspx?playerid={player_id}'
GAMELOG_URL = 'http://www.fangraphs.com/statsd.aspx?playerid={player_id}'


def parse_player_ids(value):
    if value:
        return [v.strip() for v in value.split(',')]
    return value


def get_player_url(player_id):
    return PROFILE_URL.format(player_id=player_id)


def get_gamelog_url(player_id):
    return GAMELOG_URL.format(player_id=player_id)


def urls_from_datafiles(*files):
    paths = filter(lambda p: p is not None and os.path.exists(p),
                   files)
    for path in paths:
        reader = csv.DictReader(open(path, 'r'))
        for row in reader:
            yield get_player_url(row['playerid'])


class SteamerSpider(scrapy.Spider):
    name = 'steamerpro'
    allowed_domains = ('fangraphs.com', )

    def __init__(self, batting_file=None, pitching_file=None, player_ids=None,
                 *a, **kw):
        super(SteamerSpider, self).__init__(*a, **kw)

        self.player_ids = parse_player_ids(player_ids)

        if not self.player_ids and not any((batting_file, pitching_file)):
            raise scrapy.exceptions.CloseSpider(
                reason="""Please provide a path to one or both of
                Fangraphs batting or pitching projection
                CSV exports via `-a {pitching,batting}_file=...` arguments.
                """)

        if self.player_ids:
            self.start_urls = (
                PROFILE_URL.format(player_id=pid)
                for pid in self.player_ids
            )
        else:
            self.start_urls = urls_from_datafiles(batting_file, pitching_file)

    def parse(self, response):
        """Extract Steamer stats from player pages
        """

        url_bits = urlparse.urlparse(response.url)
        qs_bits = urlparse.parse_qs(url_bits.query)
        player_id = qs_bits['playerid'][0]

        player_name = (response.css('div#content table:first-of-type table'
                                    '  tr:first-of-type span strong::text')
                       .extract_first()
                       .strip())

        self.logger.debug('Fetching projections for {} ({})'.format(
                          player_name, player_id))

        components = {}

        # extract Steamer projections row from each table on page
        tables = response.xpath("""
            //table[
                @class="rgMasterTable"
                and tbody[
                    tr/td[contains(., "2016")]
                    and tr/td[contains(., "Steamer")]
                ]
            ]
        """)

        for table in tables:
            keys = table.xpath('./thead/tr/th//text()').extract()
            values = []

            for cell in table.xpath('tbody/tr[td[contains(.,"Steamer")]]/td'):
                value = cell.xpath('text()').extract_first() or ''
                values.append(value.strip())

            components.update(**dict(zip(keys, values)))

        # remove "Team" column, which should always be "Steamer"
        components.pop('Team', None)

        # pass combined projections to gamelog extraction
        req = scrapy.Request(get_gamelog_url(player_id),
                             dont_filter=True,
                             callback=self.parse_previous_year_gamelog)
        req.meta.update(player_id=player_id,
                        player_name=player_name,
                        components=components)
        yield req

    def parse_previous_year_gamelog(self, response):
        """Extract game log for previous season and count games per position
        """

        self.logger.debug('Fetching gamelog for {} ({})'.format(
                          response.meta['player_name'],
                          response.meta['player_id']))

        tally = collections.Counter()

        for cell in response.xpath(
            '//table[@class="rgMasterTable"]/tbody/'
            'tr[@class="rgRow" or @class="rgAltRow"]/td[5]'):
            positions = cell.xpath('text()').extract_first() or ''
            positions = [pos.strip() for pos in positions.split('-')]
            for pos in positions:
                if pos:
                    tally[pos] += 1

        yield Projection(player_id=response.meta['player_id'],
                         player_name=response.meta['player_name'],
                         components=response.meta['components'],
                         positions=dict(tally))
