import re
import os
import json
import spacy
import traceback
import html2text
from nltk import sent_tokenize
from newspaper import Article
from bs4 import BeautifulSoup
from selenium import webdriver
from urllib.request import urlopen
from collections import defaultdict
from commonregex import phone, email


def parse_article(url):
    article = Article(url)
    
    article.download()
    html = article.html

    article.parse()
    body = article.text
    title = article.title
    images = list(article.images)
    images_selected = []
    for img in images:
        if img.find("icon_search") >= 0 or img.find("bwlogo") >= 0:
            continue
        else:
            images_selected.append(img)
    published_date = article.publish_date

    parsed_article = {
        'url': url,
        'body': body,
        'html': html,
        'title': title,
        'images': images_selected,
        'published_date': published_date
    }
    
    if published_date is None:
        parsed_article.pop('published_date')

    return article, parsed_article


def get_html(url):
    u_client = urlopen(url)
    page_html = u_client.read()
    u_client.close()
    
    page_soup = BeautifulSoup(page_html, "lxml")
    return page_soup


def scrape_text_from_html(html_string):
    soup = BeautifulSoup(html_string)
    
    # remove all script and style elements
    for script in soup(['script', 'style']):
        script.extract()

    # get text from url
    text = soup.get_text(separator='\n')

    return text


def clean_text(text):
    # split text into lines
    lines = [line.strip() for line in text.splitlines()]
    # split lines into phrases on basis of double space
    chunks = [phrase.strip() for line in lines for phrase in line.split("  ")]
    # join text using all those chunks which aren't empty
    text = '\n'.join([chunk for chunk in chunks if chunk])
    # replace multiple \n with single \n
    text = re.sub(r'\n{2, }', '\n', text)

    return text


def get_first_sent_in_body(body_text):
    sents = sent_tokenize(body_text)
    first_sent = sents[0]
    return first_sent


def get_first_sents_all_articles(path_to_outputs):
    first_sents = []
    files = os.listdir(path_to_outputs)
    for ffile in files:
        if ffile.lower().endswith(".json"):
            full_path = os.path.join(path_to_outputs, ffile)
            data = json.load(open(full_path, 'r'))
            first_sent = get_first_sent_in_body(data['body'])
            first_sents.append({
                'first_sent': first_sent,
                'url': data['url'],
                'title': data['title']
            })

    return first_sents


def extract_companies(text, nlp):
    rg = r'\(.*?\)'
    text = re.sub(rg, '', text)
    text = text.split("--")[-1]
    # print(text)
    doc = nlp(text)
    first_company = None
    second_company = None
    title_upper_case_rg = r'(([A-Z]+|[A-Z][A-Za-z]+)(\s|$|,|\.))+'
    for chunk in doc.noun_chunks:
        # we only need the first nsubj as company
        if chunk.root.dep_ == 'nsubj' and first_company is None:
            if re.search(title_upper_case_rg, chunk.text):
            # if chunk.text.istitle() or chunk.text.isupper():
            # if chunk.root.ent_type_ == 'ORG':
            # if chunk.root.pos_ == 'PROPN':
                first_company = chunk.text
        elif chunk.root.dep_ == 'pobj' or chunk.root.dep_ == 'dobj':
            # chunk_text = ' '.join([a for a in chunk.text.split() if a != 'and'])
            # if chunk_text.istitle() or chunk_text.isupper():
            # if chunk.root.ent_type_ == 'ORG':
            if chunk.root.pos_ == 'PROPN' and chunk.root.ent_type_ != 'DATE':
                second_company = chunk.text
                break

    return first_company, second_company


def get_contact_information(text, nlp):
    # we want to get the last occurance of this regex in the text
    m = None
    matches = re.finditer(r'Contacts\n', text)
    for match in matches:
        m = match

    all_contacts_info = []
    contact_info_to_extract = {
        'phone': phone,
        'email': email
    }
    
    # ALTERNATIVELY
    # after finding Contacts, go through the text line by line
    # once we find name, check every subsequent line for things like phone, email, job title
    # once a name is found again, close info finding for previous contact person
    if m:
        start_position = m.end()
        contacts_text = text[start_position:]
        # print(contacts_text)
        # input("Should I continue?")
        lines = contacts_text.split('\n')
        name_found = False
        for index, line in enumerate(lines):
            doc = nlp(line)
            for ent in doc.ents:
                # if person name found, start accumulating contact information until we find a blank line
                if ent.label_ == 'PERSON':
                    # if name_found is True, it means that a name was found previously that wasn't added to list
                    if name_found is True:
                        all_contacts_info.append(dict(contact_info))
                    contact_info = defaultdict(lambda: [])
                    contact_info['name'] = ent.text
                    name_found = True
                    break

            # if an empty line comes up, we assume that the contact information of a person has ended
            if line.isspace() or len(line) == 0:
                if name_found is True:
                    all_contacts_info.append(dict(contact_info))
                    name_found = False
                continue

            # if name has been found, see if this line has a phone or email. If not, add this line in other information
            # other information could be things like company, job title etc.
            if name_found is True:
                # if contact_info['name'] in ['LinkedIn']
                rg_found = False
                for title, rg in contact_info_to_extract.items():
                    m = re.search(rg, line)
                    if m:
                        contact_info[title] = m.group(0)
                        rg_found = True

                # also check that we don't insert joining texts like or, and etc.
                if rg_found is False and line.strip().lower() not in ['or', 'and', 'alternatively'] and line.strip() != contact_info['name']:
                    contact_info['other_information'].append(line.strip())

    return all_contacts_info


def get_published_date(text, nlp):
    published_date = {}
    for line in text.split('\n'):
        doc = nlp(line)
        entities = {}
        for ent in doc.ents:
            entities[ent.label_] = ent.text

        if 'DATE' in entities.keys() and 'TIME' in entities.keys():
            if line.startswith(entities['DATE']):
                published_date['date'] = entities['DATE']
                published_date['time'] = entities['TIME']
                break

    return published_date


def get_companies(body_text):
    companies = []
    title_upper_case_rg = r'(([A-Z]+|[A-Z][A-Za-z]+)(\s|$|,|\.))+'
    sents = sent_tokenize(body_text)
    first_sent = sents[0]
    rg_stock_name = r'\([A-Z]+\:\s{0,1}[A-Z]+\)'
    matches = re.finditer(rg_stock_name, first_sent)
    for m in matches:
        partial_text = first_sent[:m.start()]
        partial_text_words = partial_text.split()
        partial_text_words.reverse()
        company_name = []
        for w in partial_text_words:
            # if w.istitle():
            if re.search(title_upper_case_rg, w):
                company_name.insert(0, w)
            else:
                break
        company_name = ' '.join(company_name)
        stock_name = m.group(0).replace('(', '').replace(')', '')
        companies.append({
            'company_name': company_name,
            'stock_name': stock_name
        })
    return companies


def extract_all_entities(url, handler, nlp, driver, en_status):
    article, parsed_article = parse_article(url)
    # full_text = scrape_text_from_html(parsed_article['html'])
    # cleaned_text = clean_text(full_text)

    full_text = handler.handle(parsed_article['html'])
    full_text = full_text.replace('*', '')
    cleaned_text = re.sub(r' +', ' ', full_text)

    parsed_article['text'] = cleaned_text
    parsed_article['contact_info'] = get_contact_information(parsed_article['text'], nlp)
    # if parsed_article['published_date'] is None:
    #     parsed_article['published_date'] = get_published_date(parsed_article['text'], nlp)

    # get some elements through explicit scraping
    soup = get_html(url)

    # for time
    cont = soup.findAll("div", {"class": "bw-release-timestamp"})
    if len(cont) > 0:
        published_date_time = cont[0].time.text.strip()
        doc = nlp(published_date_time)
        for ent in doc.ents:
            if ent.label_ == 'DATE':
                parsed_article['date'] = ent.text
            elif ent.label_ == 'TIME':
                parsed_article['time'] = ent.text
        # print("Published date and time: %s\n" % published_date_time)
        parsed_article['published_date_time'] = published_date_time

    # for sub-title
    cont = soup.findAll("div", {"class": "bw-release-subhead"})
    if len(cont) > 0:
        sub_title = cont[0].text.strip()
        # print("Sub-title: %s\n" % sub_title)
        parsed_article['sub_title'] = sub_title

    # for company name and stock name on the right
    # if en_status is False:
    #     driver.get(url)
    # elem = driver.find_element_by_id("companyInformation")
    # elem = elem.find_element_by_class_name("bw-release-companyinfo")
    # company_text = elem.text.split('\n')
    # if len(company_text) > 1:
    #     company_name = company_text[0]
    #     stock_name = company_text[1]
    #     parsed_article['company_name'] = company_name
    #     parsed_article['stock_name'] = stock_name
    # else:
    #     parsed_article['company_name'] = company_text

    # get company names and stock names from the first sentence in the body of the article
    parsed_article['entities'] = get_companies(parsed_article['body'])
    first_company, second_company = extract_companies(parsed_article['body'], nlp)
    parsed_article['company_1'] = first_company
    parsed_article['company_2'] = second_company

    return parsed_article


if __name__ == '__main__':
    # while 1:
        # url = input("Please enter the URL of the article: ")
        # if url.lower() == "exit":
            # break
    folder_name = "parsed_articles_demo"
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)
        
    print("Loading Spacy model...")
    nlp = spacy.load('en_core_web_lg')

    print("Loading PhantomJS driver...")
    driver = webdriver.PhantomJS()

    handler = html2text.HTML2Text()
    handler.ignore_links = True

    # get all articles on page
    url = "https://www.businesswire.com/portal/site/home/template.PAGE/news/subject/?javax.portlet.tpst=08c2aa13f2fe3d4dc1b6751ae1de75dd&javax.portlet.prp_08c2aa13f2fe3d4dc1b6751ae1de75dd_vnsId=31333&javax.portlet.prp_08c2aa13f2fe3d4dc1b6751ae1de75dd_viewID=MY_PORTAL_VIEW&javax.portlet.prp_08c2aa13f2fe3d4dc1b6751ae1de75dd_ndmHsc=v2*A1549544400000*DgroupByDate*M31333*N1000105&javax.portlet.begCacheTok=com.vignette.cachetoken&javax.portlet.endCacheTok=com.vignette.cachetoken"
    soup = get_html(url)
    cont = soup.findAll("ul", {"class": "bwNewsList"})
    if len(cont) > 0:
        in_cont = cont[0].findAll("li")
        if len(in_cont) > 0:
            counter = 1
            for elem in in_cont:
                article_en_status = False
                url = elem.meta.attrs['content']
                print(url)
                # this means that the article is not originally in English; load the English version
                if url.find("/en") == -1:
                    # this snippet is for getting link of English article if article is not originally in English
                    driver.get(url)
                    a = driver.find_element_by_id("ajaxReleaseVersions")
                    b = a.find_element_by_class_name("bw-release-versions")
                    c = b.find_elements_by_tag_name("li")
                    for elem in c:
                        # c = c[0]
                        d = elem.find_element_by_tag_name("a")
                        en_url = d.get_attribute("href")
                        if en_url.find("/en") >= 0:
                            url = en_url
                            print("Article was not in English; here is the English link")
                            print(url)
                            article_en_status = True
                            break
                else:
                    print("Article is already in English")
                    # print(url)

                # process the article
                print()
                print("Processing the article...")
                try:
                    parsed_article = extract_all_entities(url, handler, nlp, driver, article_en_status)
                    parsed_article.pop('html')
                    # browser.quit() ? Or browser.close() ???
                    # with open("parsed_articles/%s.json" % url.split("/")[-1], 'w') as wfile:
                    with open("%s/%d.json" % (folder_name, counter), 'w') as wfile:
                        json.dump(parsed_article, wfile)
                    print("Processed and dumped successfully!")
                    counter += 1
                except Exception as e:
                    print("EXCEPTION!")
                    print(e)
                    print(traceback.format_exc())
