#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Crude XKB layout installer."""

import argparse
import io
import sys
import tomllib
import xml.etree.ElementTree as ET

from collections.abc import Iterable, Mapping, Sequence
from typing import TypeVar

T = TypeVar('T')

class Variant:

    def __init__(self, name: str, description: str,
                 language: Sequence[str] | None, country: Sequence[str] | None):
        self.name = name
        self.description = description
        self.language = language or []
        self.country = country or []

    def xml(self) -> ET.Element:
        variant = ET.Element('variant')
        config_item = ET.SubElement(variant, 'configItem')
        e = ET.SubElement(config_item, 'name')
        e.text = self.name
        e = ET.SubElement(config_item, 'description')
        e.text = self.description
        if self.country:
            e.append(countries_to_xml(self.country))
        if self.language:
            e.append(languages_to_xml(self.language))
        ET.indent(variant, level=3)
        return variant

class Layout:

    def __init__(self, name: str, variants: Mapping[str, Variant] | None):
        self.name = name
        self.variant = variants or {}
        if variants:
            for v in variants.values():
                self.description = v.description
                break
        else:
            self.description = name

    def countries(self) -> set[str]:
        s = set()
        for v in self.variant.values():
            for c in v.country:
                s.add(c)
        return s

    def languages(self) -> set[str]:
        s = set()
        for v in self.variant.values():
            for c in v.language:
                s.add(c)
        return s

    def xml(self) -> ET.Element:
        layout = ET.Element('layout')

        config_item = ET.SubElement(layout, 'configItem')
        e = ET.SubElement(config_item, 'name')
        e.text = self.name
        e = ET.SubElement(config_item, 'shortDescription')
        e.text = self.name
        e = ET.SubElement(config_item, 'description')
        e.text = self.description
        if (t := self.countries()):
            e.append(countries_to_xml(t))
        if (t := self.languages()):
            e.append(languages_to_xml(t))

        variant_list = ET.SubElement(layout, 'variantList')
        for v in self.variant.values():
            variant_list.append(v.xml())

        ET.indent(layout, level=2)
        return layout

def countries_to_xml(items: Iterable[str]) -> ET.Element:
    return strs_to_xml('languageList', 'iso3166Id', (i.upper() for i in items))

def languages_to_xml(items: Iterable[str]) -> ET.Element:
    return strs_to_xml('languageList', 'iso639Id', (i.lower() for i in items))

def strs_to_xml(outer: str, inner: str, values: Iterable[str]) -> ET.Element:
    e = ET.Element(outer)
    for i in values:
        ee = ET.SubElement(e, inner)
        ee.text = i
    return e

def merge_rules_lst(layouts: Mapping[str, Layout], f: io.TextIOBase):
    while (line := f.readline()):
        print(line, end='')
        line = line.strip()
        if len(line) == 0 or line[0] != '!':
            continue
        if 'layout' in line:
            for layout in layouts.values():
                print(f'  {layout.name:<15} {layout.description}')
            continue
        if 'variant' in line:
            for layout in layouts.values():
                for variant in layout.variant.values():
                    print(f'  {variant.name:<15} {layout.name}:'
                          f' {variant.description}')

def merge_rules_xml(layouts: Mapping[str, Layout], f: io.TextIOBase):
    et = ET.parse(
        f, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    ll = et.find('layoutList')
    if ll is None:
        ll = ET.Element('layoutList')
        et.getroot().append(ll)
    for layout in layouts.values():
        ll.append(layout.xml())
    print('<?xml version="1.0" encoding="UTF-8"?>')
    print('<!DOCTYPE xkbConfigRegistry SYSTEM "xkb.dtd">')
    et.write(sys.stdout, encoding='unicode')

def main(argv: Sequence[str] | None = None):
    if argv is None:
        argv = sys.argv
    parser = argparse.ArgumentParser()
    parser.add_argument('--rules-lst', '-l', help='.lst rules file')
    parser.add_argument('--rules-xml', '-x', help='XML rules file')
    parser.add_argument(
        '--output-rules-lst', '-L', help='Output .lst rules file')
    parser.add_argument(
        '--output-rules-xml', '-X', help='Output XML rules file')
    parser.add_argument('file', metavar='TOML', help='input file name')
    args = parser.parse_args(argv[1 :])

    with open(args.file, 'rb') as f:
        config = tomllib.load(f)

    layouts: dict[str, Layout] = {}
    for layout, lprop in config.get('symbols', {}).items():
        variants: dict[str, Variant] = {}
        for variant, vprop in lprop.get('variant', {}).items():
            desc = vprop.get('description', lprop.get('description', variant))
            land = vprop.get('country', lprop.get('country', []))
            if isinstance(land, str):
                land = [land]
            lang = vprop.get('language', lprop.get('language', []))
            if isinstance(lang, str):
                lang = [lang]
            variants[variant] = Variant(variant, desc, lang, land)
        layouts[layout] = Layout(layout, variants)

    if args.rules_lst:
        with open(args.rules_lst, 'r', encoding='utf-8') as f:
            merge_rules_lst(layouts, f)

    if args.rules_xml:
        with open(args.rules_xml, 'r', encoding='utf-8') as f:
            merge_rules_xml(layouts, f)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
