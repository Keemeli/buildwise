# Maintained product URL lists

Copy `jimms_urls.example.json` to `jimms_urls.json` and replace the placeholder
with real product-page URLs. Each item needs a supported `category` and `url`.
Run from the repository root:

```sh
python3 -m scraper collect --shop jimms --input scraper/inputs/jimms_urls.json
```

Commit reusable examples (`*.example.json`). Local JSON lists are ignored.
Automatic category discovery writes to `data/discovery/`, outside this folder.
