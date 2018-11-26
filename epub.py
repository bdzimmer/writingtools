"""

Generate EPUB files.

"""
# Copyright (c) 2018 Ben Zimmer. All rights reserved.
# Based on examples from: https://en.wikipedia.org/wiki/EPUB

from __future__ import print_function

import os
import sys
import zipfile

import attr


@attr.s
class SectionInfo:
    id = attr.ib()
    name = attr.ib()
    content = attr.ib()


MIMETYPE = "application/epub+zip"

CONTAINER_XML = (
"""
<?xml version="1.0" encoding="UTF-8" ?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""")


def format_content_opf(
        unique_identifier,
        title,
        firstname,
        lastname,
        sections
    ):
    """format contents of content.opf file"""

    manifest_items = [
        """<item id="{id}" href="{filename}" media-type="application/xhtml+xml"/>""".format(id=section.id, filename=section.id + ".xhtml")
        for section in sections
    ]

    manifest = (
        "<manifest>" +
        "".join(manifest_items) +
        """<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>""" +
        "</manifest>")

    spine_items = [
        """<itemref idref="{id}" />""".format(id=section.id)
        for section in sections
    ]

    spine = (
        """<spine toc="ncx">""" +
        "".join(spine_items) +
        """</spine>"""
    )

    res = (
"""
<?xml version="1.0"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="{unique_identifier}">

  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{title}</dc:title>
    <dc:language>en</dc:language>
    <dc:identifier id="{unique_identifier}" opf:scheme="NotISBN">{unique_identifier}</dc:identifier>
    <dc:creator opf:file-as="{lastname}, {firstname}" opf:role="aut">{firstname} {lastname}</dc:creator>
  </metadata>

  {manifest}

  {spine}

</package>
""").format(
        unique_identifier=unique_identifier,
        title=title,
        firstname=firstname,
        lastname=lastname,
        manifest=manifest,
        spine=spine
    )

    return res


def format_toc_ncx(
        unique_identifier,
        title,
        firstname,
        lastname,
        sections):

    """format contents of toc.ncx file"""

    navmap_items = [
        (
            """<navPoint class="chapter" id="{id}" playOrder="{idx}">""" +
            """<navLabel><text>{name}</text></navLabel>""" +
            """<content src="{filename}"/>""" +
            """</navPoint>"""
        ).format(
            id=section.id,
            idx=str(idx + 1),
            name=section.name,
            filename=section.id + ".xhtml"
        )
        for idx, section in enumerate(sections)
    ]

    navmap = (
        "<navMap>" +
        "".join(navmap_items) +
        "</navMap>"
    )

    res = (
"""
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">

<ncx version="2005-1" xml:lang="en" xmlns="http://www.daisy.org/z3986/2005/ncx/">

  <head>
<!-- The following four metadata items are required for all NCX documents,
including those that conform to the relaxed constraints of OPS 2.0 -->

    <meta name="dtb:uid" content="{unique_identifier}"/> <!-- same as in .opf -->
    <meta name="dtb:depth" content="1"/> <!-- 1 or higher -->
    <meta name="dtb:totalPageCount" content="0"/> <!-- must be 0 -->
    <meta name="dtb:maxPageNumber" content="0"/> <!-- must be 0 -->
  </head>

  <docTitle>
    <text>{title}</text>
  </docTitle>

  <docAuthor>
    <text>{lastname}, {firstname}</text>
  </docAuthor>

  {navmap}

</ncx>
""").format(
        unique_identifier=unique_identifier,
        title=title,
        firstname=firstname,
        lastname=lastname,
        navmap=navmap
    )

    return res


def main(argv):
    """main program"""

    output_filename = os.path.join("test.epub")

    unique_identifier = "123456789"
    title = "Test Book"
    firstname = "B"
    lastname = "Z"
    sections = [
        SectionInfo("0", "Title Page", "<body>Test Book<br>B Z</body>"),
        SectionInfo("1", "Chapter 1", "<body>This is the content of chapter 1.</body>")
    ]

    content_opf = format_content_opf(
        unique_identifier,
        title,
        firstname,
        lastname,
        sections)

    toc_ncx = format_toc_ncx(
        unique_identifier,
        title,
        firstname,
        lastname,
        sections)

    # create and write everything to archive
    with zipfile.ZipFile(output_filename, "w") as zf:
        zf.writestr("mimetype", MIMETYPE, compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("OEBPS/content.opf", content_opf)
        zf.writestr("OEBPS/toc.ncx", toc_ncx)
        for section in sections:
            zf.writestr("OEBPS/" + section.id + ".xhtml", section.content)

    print(output_filename)


if __name__ == "__main__":
    main(sys.argv)
