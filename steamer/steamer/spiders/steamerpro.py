# -*- coding: utf-8 -*-

import collections
import csv
import decimal
import os
import re
from urllib import parse

import scrapy

from ..items import Projection


PROFILE_URL = 'http://www.fangraphs.com/statss.aspx?playerid={player_id}'

T_PITCHER = 'p'
T_BATTER = 'b'

PCT_RE = re.compile(r'([\.\d]+)\s+?%')

BATTING_POSITIONS = {
    'C':  0,
    '1B': 0,
    '2B': 0,
    'SS': 0,
    '3B': 0,
    'LF': 0,
    'CF': 0,
    'RF': 0,
    'DH': 0,
    'PH': 0,
    'PR': 0,
    'P':  0,
}

PITCHING_POSITIONS = {'SP': 0, 'RP': 0, 'P': 0}


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

    def __init__(self, player_ids_file, *a, **kw):
        super(SteamerSpider, self).__init__(*a, **kw)

        if (not os.path.exists(player_ids_file)
            or not os.path.isfile(player_ids_file)):
            raise Exception(
                reason='Path to file ({player_ids_file}) invalid or not file'
                    .format(player_ids_file=player_ids_file))

        self.start_urls = urls_from_datafiles(player_ids_file)

    def parse(self, response):
        """Extract Steamer stats from player pages
        """

        url_bits = parse.urlparse(response.url)
        qs_bits = parse.parse_qs(url_bits.query)
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
                    tr/td[contains(., "2018")]
                    and tr/td[contains(., "Steamer")]
                ]
            ]
        """)

        tables = list(tables)

        if len(tables) == 0:
            self.logger.warning('Skipping unprojected player: {}'
                                .format(player_id))
            return

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

        # find positions fielded in previous year
        positions = []
        fielding_rows = response.xpath(
            '//table[@id="SeasonStats1_dgSeason8_ctl00"]//tr/td/a[contains(., 2017)]/../..')

        for row in fielding_rows:
            team = row.xpath('td[2]/a/text()').extract_first()
            pos = row.xpath('td[3]//text()').extract_first()
            g = row.xpath('td[4]//text()').extract_first()
            gs = row.xpath('td[5]//text()').extract_first()

            positions.append({
                'team': team,
                'pos': pos,
                'g': g,
                'gs': gs,
            })

        handedness = {
            'bats': bats,
            'throws': throws,
        }

        yield Projection(
            player_id=player_id,
            player_name=player_name,
            player_type=player_type,
            components=components,
            handedness=handedness,
            positions=positions)
