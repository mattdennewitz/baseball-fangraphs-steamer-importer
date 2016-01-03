# -*- coding: utf-8 -*-

import scrapy


class Projection(scrapy.Item):
    item_type = 'projection'

    player_id = scrapy.Field()
    player_name = scrapy.Field()
    components = scrapy.Field()
    positions = scrapy.Field()
    handedness = scrapy.Field()
