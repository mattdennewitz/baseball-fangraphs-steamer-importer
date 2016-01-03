from collections import OrderedDict
import json

import click

import unicodecsv as csv


def parse_object(obj, path=''):
    """Borrowed from `csvkit`
    """

    if isinstance(obj, dict):
        iterator = obj.items()
    elif isinstance(obj, (list, tuple)):
        iterator = enumerate(obj)
    else:
        return { path.strip('/'): obj }

    d = {}

    for key, value in iterator:
        key = unicode(key)
        d.update(parse_object(value, path + key + '/'))

    return d


@click.command()
@click.argument('input_fp', type=click.File('rb'), required=True)
@click.argument('output_fp', type=click.File('w'), required=True)
def convert(input_fp, output_fp):
    data = json.load(input_fp, object_pairs_hook=OrderedDict)

    if not isinstance(data, list):
        raise click.BadParameter('JSON input object must be a list')

    keys = set()
    rows = []

    # headers = sorted(parse_object(data[0]).keys())
    # writer = csv.DictWriter(output_fp, headers)

    for projection in data:
        projection = parse_object(projection)
        for key in projection:
            keys.add(key)
        rows.append(projection)

    headers = sorted(keys)
    writer = csv.DictWriter(output_fp, headers)
    writer.writeheader()

    for row in rows:
        writer.writerow(row)


if __name__ == '__main__':
    convert()
