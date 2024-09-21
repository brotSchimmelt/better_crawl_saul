# Wikipedia and WikiNews Revision Crawler

This project aims to crawl revision histories from Wikipedia and WikiNews, identify differences between document versions using `latexdiff`, and extract changes at the sentence level.

The code is based on the web crawler used in this [IteraTeR project](https://github.com/vipulraheja/iterater).

## Dependencies

The crawler was tested with python 3.10.

To install the required dependencies, run:

```bash
pip install -r requirements.txt
```

Additionally, you need to download NLTK’s `punkt_tab` package for sentence tokenization. You can do this by running the following Python commands:

```bash
>>> import nltk
>>> nltk.download('punkt_tab')
```

You also need to have `latexdiff` installed on your system. To do this, you must install LaTeX (see the instructions [here](https://www.latex-project.org/get/)).

To check if it’s installed, run:

```bash
which latexdiff
```

## Usage

To extract revision data at the sentence level, follow these steps:

## Data Collection

You can crawl revision data from either Wikipedia or WikiNews. The main categories for each domain are specified in the `src/settings.py` file. Note that Wikipedia and WikiNews have distinct category lists.

To start crawling data, run the following command:

```bash
python crawl_wiki_data.py --domain wikipedia --main_category philosophy --years_back 1
```

### Revision Extraction

After crawling the data, follow these steps to extract and process revision changes:

1. Filter and merge the crawled data:

```bash
python filter_and_merge_crawled_wiki_data.py --domain wikipedia
```

2. Create latexdiff files:

```bash
python create_latexdiffs.py --domain wikipedia
```

3. Parse the latexdiff output to extract sentence-level differences:

```bash
python parse_latex_diffs.py --domain wikipedia
```
