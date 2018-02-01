# -*- coding: utf-8 -*-

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


def parse_player_ids(value):
    """Splits a list of player ids by comma

    Args:
        value: String of comma-separated player ids

    Returns:
        List of player ids
    """

    if value:
        return [v.strip() for v in value.split(',')]

    return value


def parse_decimal(value):
    """Extracts a numerical value from percentage representation

    Args:
        value: String percentage value (e.g., "100%")

    Returns:
        Percentage as decimal value (decimal.Decimal instance)
    """

    match = PCT_RE.match(value)

    if not match:
        return None

    value = decimal.Decimal(match.group(1))

    return value / decimal.Decimal('100.0')


def get_player_url(player_id):
    """Returns a Fangraphs player URL for given id

    Args:
        player_id: Fangraphs player id

    Returns:
        Player stats page URL (string)
    """

    return PROFILE_URL.format(player_id=player_id)


def urls_from_datafile(path):
    """Creates player URLs from player ids in a CSV file

    Args:
        path: Absolute path to player ids CSV file

    Returns:
        Player URLs (generator)
    """

    reader = csv.DictReader(open(path, 'r'))

    for row in reader:
        yield get_player_url(row['playerid'])


class SteamerSpider(scrapy.Spider):
    name = 'steamerpro'
    allowed_domains = ('fangraphs.com', )

    def __init__(self, player_ids_file=None, player_ids=None, *a, **kw):
        super(SteamerSpider, self).__init__(*a, **kw)

        if player_ids is not None:
            ids = parse_player_ids(player_ids)
            self.start_urls = (get_player_url(id) for id in ids)
        elif player_ids_file is not None:
            player_ids_file = os.path.abspath(player_ids_file)
            if (not os.path.exists(os.path.abspath(player_ids_file))
                or not os.path.isfile(player_ids_file)):
                raise Exception(
                    f'Path to file ({player_ids_file}) invalid or not file')
            self.start_urls = urls_from_datafile(player_ids_file)
        else:
            raise Exception('Cannot parse without player ids')

    def parse(self, response):
        """Extract Steamer stats from player pages

        Args:
            response: Scrapy response

        Returns:
            Full `Projection` if player is projected, else `None`
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

        return Projection(
            player_id=player_id,
            player_name=player_name,
            player_type=player_type,
            components=components,
            handedness=handedness,
            positions=positions)
