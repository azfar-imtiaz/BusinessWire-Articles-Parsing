# BusinessWire Articles Parsing

This project (originally a demo for a project that didn't go through) loads all English articles from BusinessWire on a single page, and applies a variety of scraping and NLP techniques to extract various kinds of data from it. 

These articles are related to mergers or acquisitions happening between companies, and the purpose of this script was to extract all required information such as the nature of the action, which company acquired or merged with which company, company and contact details, article title, any attached images, date and time of the article being published etc.

The script saves all extracted information for each article in individual JSON files, the path to which has been specified in the start of the script.

The following techniques have been made use of for the extraction:

## Scraping articles from a page
The initial webpage contains a list of articles talking about mergers and acquisitions happening between different companies. The script loads all articles on the page one by one, scrapes the text from that article, and then extracts various entities from that article. Some of the articles are not in English; however, there is always a link to the English version of that article on that article web page. If the loaded article itself is not in English, the English version is loaded and scraped.
The following modules were used for above mentioned purposes:

- PhantomJS (for loading the page in a headless web browser)
- Beautiful Soup
- HTML2Text
- Urllib

## Extracting relevant information from the article
The use of the following concepts was exhibited for extraction of various entities:

- Scraping
- Regular Expressions
- Named Entity Recognition
- Dependency Parsing (to figure out which company was acquired and which company did the acquiring)

## NLP Modules used
The following NLP modules were used in the development of this project:

- NLTK
- Spacy
- Newspaper3k