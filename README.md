# Wikipedia and WikiNews Revision Crawler

The code is based on the web crawler used in this [project](https://github.com/vipulraheja/iterater).

## Dependencies

```bash
pip install -r requirements.txt
```

## Usage

```bash
>>> import nltk
>>> nltk.download('punkt_tab')
```

### Data Collection

```bash
python crawl_wiki_data.py --domain wikipedia --main_category philosophy --years_back 1
```

### Revision Extraction

```bash
python filter_and_merge_crawled_wiki_data.py --domain wikipedia
```

```bash
python create_latexdiffs.py --domain wikipedia
```

```bash
python parse_latex_diffs.py --domain wikipedia
```
