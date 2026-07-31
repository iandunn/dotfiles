---
name: reading-pdfs
description: "Extracts text and images from PDFs with poppler instead of feeding the file to the Read tool, which renders every page as an image and wastes tokens."
when_to_use: "Use before reading any PDF, whether the user attached one, referenced a path ending in .pdf, or asked you to summarize, quote, or search a PDF. Invoke this instead of passing the PDF to the Read tool."
---

Never give a PDF to the Read tool directly. It renders every page to images and wastes tokens. Extract locally with poppler; `tesseract` handles OCR.

Write extracted files to `.claude/tmp/` inside the project, or `$TMPDIR` when the PDF isn't part of a project. A permanent artifact like a PDF-to-text conversion goes in the project's `_notes` folder if one exists, or the Relay folder when the project uses Relay. If neither exists, ask where it should go instead of picking a spot.

## Text

```bash
pdftotext -layout in.pdf .claude/tmp/out.txt
```

Then read or grep the result. For a page range straight to stdout:

```bash
pdftotext -layout -f N -l M in.pdf -
```

## Screenshots and embedded images

```bash
pdfimages -list in.pdf                      # find what's embedded
pdfimages -png -p in.pdf .claude/tmp/x      # extract as PNGs
```

Read only the relevant ones. This preserves screenshots without rendering whole pages.

## Fallback for vector or complex pages

```bash
pdftoppm -png -r 150 -f N -l N in.pdf .claude/tmp/x
```

Renders a single page. Use only when the text and image extractors both come up short.
