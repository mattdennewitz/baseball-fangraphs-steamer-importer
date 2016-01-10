# -*- coding: utf-8 -*-

import collections
import decimal
import os
import re
import unicodecsv as csv
import urlparse

import scrapy

from ..items import Projection


PROFILE_URL = 'http://www.fangraphs.com/statss.aspx?playerid={player_id}'
GAMELOG_URL = 'http://www.fangraphs.com/statsd.aspx?playerid={player_id}&position={position}'

T_PITCHER = 'p'
T_BATTER = 'b'

PCT_RE = re.compile(r'([\.\d]+)\s+?%')


def parse_player_ids(value):
    if value:
        return [v.strip() for v in value.split(',')]
    return value


def parse_decimal(value):
    match = PCT_RE.match(value)
    if not match:
        return None
    value = decimal.Decimal(match.group(1))
    return value / decimal.Decimal('100.0')


def get_player_url(player_id):
    return PROFILE_URL.format(player_id=player_id)


def get_gamelog_url(player_id, position):
    return GAMELOG_URL.format(player_id=player_id, position=position)


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
        position = qs_bits['position'][0]
        player_type = T_PITCHER if position == 'P' else T_BATTER

        # get player name
        player_name = (response.css('div#content table:first-of-type table'
                                    '  tr:first-of-type span strong::text')
                       .extract_first()
                       .strip())

        self.logger.debug('Fetching projections for {} ({})'.format(
                          player_name, player_id))

        bats_throws = response.xpath("""
            //table//div//strong[contains(., "Bats")]/following-sibling::text()[1]
        """)
        bats_throws = bats_throws.extract_first().strip()
        bats, throws = bats_throws.split('/')

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
            # get component header keys
            keys = table.xpath('./thead/tr/th//text()').extract()

            # prefix all keys with player type const
            keys = ['{}_{}'.format(player_type, key).upper()
                    for key in keys]

            values = []

            for cell in table.xpath('tbody/tr[td[contains(.,"Steamer")]]/td'):
                value = cell.xpath('text()').extract_first() or ''
                value = value.strip()
                if value.endswith('%'):
                    value = parse_decimal(value)
                values.append(value)

            components.update(**dict(zip(keys, values)))

        # remove "Team" column, which should always be "Steamer"
        components.pop('Team', None)

        gamelog_url = get_gamelog_url(player_id, position)

        # pass combined projections to gamelog extraction
        req = scrapy.Request(gamelog_url,
                             dont_filter=True,
                             callback=self.parse_gamelog)
        req.meta.update(player_id=player_id,
                        player_name=player_name,
                        player_type=player_type,
                        handedness={
                            'bats': bats,
                            'throws': throws,
                        },
                        components=components)
        yield req

    def get_pitcher_profile(self, selector):
        tally = collections.Counter()

        for cell in selector.xpath(
            '//table[@class="rgMasterTable"]/tbody/'
            'tr[@class="rgRow" or @class="rgAltRow"]/td[4]/text()'):
            games = cell.extract()

            for gs in map(int, games):
                pos = 'RP' if gs == 0 else 'SP'
                tally[pos] += 1

        return dict(tally)

    def get_batter_profile(self, selector):
        has_positions = selector.xpath("""
            boolean(
                //table[@class="rgMasterTable"]/thead/tr/th/a[contains(., "Pos")]
            )
        """).extract_first()

        if bool(int(has_positions)) == False:
            return {}

        tally = collections.Counter()

        for cell in selector.xpath(
            '//table[@class="rgMasterTable"]/tbody/'
            'tr[@class="rgRow" or @class="rgAltRow"]/td[5]'):
            positions = cell.xpath('text()').extract_first() or ''
            positions = [pos.strip() for pos in positions.split('-')]

            for pos in positions:
                if pos:
                    tally[pos] += 1

        return dict(tally)

    def parse_gamelog(self, response):
        """Extract pitcher game log for previous season
        """

        self.logger.debug('Fetching gamelog for {} ({})'.format(
                          response.meta['player_name'],
                          response.meta['player_id']))

        if response.meta['player_type'] == T_PITCHER:
            positions = self.get_pitcher_profile(response)
        else:
            positions = self.get_batter_profile(response)

        yield Projection(player_id=response.meta['player_id'],
                         player_name=response.meta['player_name'],
                         player_type=response.meta['player_type'],
                         components=response.meta['components'],
                         handedness=response.meta['handedness'],
                         positions=positions)
