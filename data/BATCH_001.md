# Batch 001

Downloaded on 18 November 2026. There are 15 restaurant menu sets, 21 original
files, and approximately 11.6 MB of source data. Receipts preserve UTC download
timestamps, HTTP response metadata, and checksums. The CSV manifest has one row
per original file. All pages for one menu share the same split.

| Restaurant | Format | Split | Sample characteristics |
| --- | --- | --- | --- |
| Restaurant DUFKE | Text PDF | Development | 18 pages including introductory and drinks pages |
| Restaurant Berg | Text PDF | Development | 10 pages, numbered dishes and comma decimal prices |
| Dishoom Manchester | Text PDF | Development | Two dense pages with columns, dietary symbols and portion options |
| Sea Breeze, Loloata Island Resort | Text PDF | Test | 10 pages, English menu and prices prefixed with K |
| The Duck on the Pond / Harvest Kitchen | Text PDF | Test | Two-page sample menu hosted in a 2022 source directory |
| SALUT Restaurant | HTML | Development | Categories, descriptions and optional additions |
| Von Bis Restaurant | HTML | Development | Size and accompaniment options, allergen codes |
| Restaurant Hollberg | HTML | Development | Burger, steak, side and dessert sections |
| FINO Cromer | HTML | Test | English sample menu with food, drinks and serving-size prices |
| Fuchsbau | HTML | Test | German menu with supplements and long descriptions |
| Mediterran Coburg | Scanned PDF | Development | One handwritten seasonal menu page, no selectable text |
| Ramen-Ya | PNG | Development | English menu, multiple columns and toppings |
| Restaurant RETRO | Six JPEG images | Development | Six menu pages, portion choices and different decimal punctuation |
| Restaurant Goldberg | Two JPEG images | Development | Two sides of a takeaway leaflet, dense text on a dark background, dated June 2024 |
| Hotel zur Post, Wiesmoor | JPEG | Test | Standalone children's menu with four dishes |

## Validation

- All 21 accepted assets downloaded successfully and have distinct SHA-256 hashes.
- Each of the five text PDFs contains extractable text. Introductory pages can
  contain little text and should be handled during extraction.
- The scanned seasonal PDF contains zero extracted text characters.
- All five HTML responses contain menu text and multiple price-like values.
- All image files decoded successfully. Image menus and representative PDF pages
  were visually reviewed for menu content and readability.
- The development/test split contains 10 and 5 restaurants respectively.

## Limitations

The batch is a deliberately varied learning sample. It includes older files,
sample menus, a seasonal menu, a children's menu, and drinks alongside food.
Download date records retrieval time. Prices and dishes can have changed since
the source documents were published.

Some image text is small, and the handwritten menu is a harder OCR case.
Extraction accuracy and completeness still need to be measured against manually
checked records. The HTML snapshots retain external resource references and
may display differently offline.

Restaurant source pages and assets were publicly accessible at collection time.
Open redistribution licenses have not been verified. Raw files and generated
outputs are excluded from Git, while the source list and manifest retain provenance.

## Replaced candidates

Mr Paul's PDF had insufficient selectable text for the text-PDF group.
Boardwalk Bagel returned HTTP 403 for the image asset. Eighteen Thirty Two and
Blue Moon asset URLs returned HTTP 404. Westerbachhalle's downloaded HTML lacked
the actual dishes and prices. These candidates are excluded from the final batch.
